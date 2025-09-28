import io
import json
import uuid
import pandas as pd
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, abort
)
from ..models import Institution, Account, Mapper, Import, Transaction
from ..forms import ImportUploadForm, ReviewDecisionForm, MappingWizardForm
from ..services.importer import run_import
from ..services.review import commit_import
from ..services.mapping import create_mapper, guess_mapping_from_headers
from datetime import datetime
from ..extensions import db
from ..forms import CSRFOnlyForm


bp = Blueprint("imports", __name__)

@bp.route("/upload", methods=["GET", "POST"])
def upload():
    form = ImportUploadForm()

    # Populate choices
    form.institution_id.choices = [
        (i.id, i.name) for i in Institution.query.order_by(Institution.name).all()
    ]
    selected_inst = (
        form.institution_id.data
        or (form.institution_id.choices[0][0] if form.institution_id.choices else None)
    )

    form.account_id.choices = (
        [
            (a.id, f"{a.name} ({a.type})")
            for a in Account.query.filter_by(institution_id=selected_inst).order_by(Account.name)
        ]
        if selected_inst
        else []
    )
    acct_id = form.account_id.data or (
        form.account_id.choices[0][0] if form.account_id.choices else None
    )

    # Mappers (optional). First item is sentinel for "guess from CSV".
    mapper_choices = [(-1, "Guess from CSV (no mapping)")]
    if selected_inst and acct_id:
        mapper_choices += [
            (m.id, f"v{m.version}")
            for m in Mapper.query.filter_by(
                institution_id=selected_inst, account_id=acct_id
            ).order_by(Mapper.version.desc())
        ]
    form.mapper_id.choices = mapper_choices

    if request.method == "POST" and form.validate_on_submit():
        institution = Institution.query.get(form.institution_id.data)
        account = Account.query.get(form.account_id.data)
        f = request.files["file"]

        # If user selected an existing mapper → import immediately
        if form.mapper_id.data != -1:
            mapper = Mapper.query.get(form.mapper_id.data)
            imp, raw_bytes, review = run_import(None, f, institution, account, mapper, current_app.config)
            current_app.config.setdefault("_IMPORT_CACHE", {})[imp.id] = raw_bytes
            flash("Parsed file. Review decisions below.", "info")
            return redirect(url_for(".review", import_id=imp.id))

        # Otherwise, guess mapping and route to wizard
        raw = f.read()
        try:
            df = pd.read_csv(io.BytesIO(raw), nrows=5)
        except Exception as e:
            flash(f"Could not read CSV: {e}", "error")
            return redirect(url_for(".upload"))

        if df.empty and len(df.columns) == 0:
            flash("CSV appears to have no columns.", "error")
            return redirect(url_for(".upload"))

        guessed = guess_mapping_from_headers(list(df.columns))
        token = str(uuid.uuid4())
        current_app.config.setdefault("_IMPORT_CACHE", {})[token] = {
            "raw": raw,
            "institution_id": institution.id,
            "account_id": account.id,
            "original_filename": f.filename,
            "guessed": guessed,
        }
        return redirect(url_for(".wizard_from_upload", token=token))

    # If a POST happened but validation failed, surface errors
    if request.method == "POST" and not form.validate():
        errs = "; ".join(
            f"{name}: {', '.join(msgs)}" for name, msgs in form.errors.items()
        )
        if errs:
            flash(f"Upload form errors — {errs}", "error")

    return render_template("imports/upload.html", form=form)


@bp.route("/wizard/<token>", methods=["GET", "POST"])
def wizard_from_upload(token):
    cache = current_app.config.setdefault("_IMPORT_CACHE", {}).get(token)
    if not cache:
        flash("Upload session expired. Please re-upload your CSV.", "error")
        return redirect(url_for(".upload"))

    institution = Institution.query.get(cache["institution_id"])
    account = Account.query.get(cache["account_id"])
    guessed = cache["guessed"]

    form = MappingWizardForm(data={
        "date_col": guessed["date_col"],
        "date_fmt": guessed["date_fmt"],
        "desc_col": guessed["desc_col"],
        "indicator_col": guessed.get("indicator_col") or "",  # NEW
        "amount_col": guessed["amount_col"] or "",
        "debit_col": guessed["debit_col"] or "",
        "credit_col": guessed["credit_col"] or "",
        "balance_col": guessed["balance_col"] or "",
        "exclude_pending": guessed.get("exclude_pending", False),
    }
)

    if form.validate_on_submit():
        schema = dict(
            date_col=form.date_col.data,
            date_fmt=form.date_fmt.data,
            desc_col=form.desc_col.data,
            indicator_col=form.indicator_col.data or None,  # NEW
            amount_col=form.amount_col.data or None,
            debit_col=form.debit_col.data or None,
            credit_col=form.credit_col.data or None,
            balance_col=form.balance_col.data or None,
            exclude_pending=form.exclude_pending.data,
        )
        # Create a mapper version for this account/institution
        mapper = create_mapper(institution.id, account.id, schema)

        # Proceed with original raw bytes to import using the new mapper
        raw_bytes = cache["raw"]

        class _FS:
            filename = cache["original_filename"]

            def read(self_inner):
                return raw_bytes

        imp, raw_bytes, review = run_import(None, _FS(), institution, account, mapper, current_app.config)
        # swap token for import id in cache
        current_app.config["_IMPORT_CACHE"].pop(token, None)
        current_app.config["_IMPORT_CACHE"][imp.id] = raw_bytes

        flash(f"Mapping v{mapper.version} created and applied. Review import below.", "success")
        return redirect(url_for(".review", import_id=imp.id))

    return render_template(
        "admin/mapper_edit.html",
        form=form,
        institution_id=institution.id,
        account_id=account.id,
    )


@bp.route("/review/<int:import_id>", methods=["GET", "POST"])
def review(import_id):
    imp = Import.query.get_or_404(import_id)
    review = imp.log_json.get("review", {})
    form = ReviewDecisionForm()

    if form.validate_on_submit():
        try:
            decisions = json.loads(form.decisions_json.data or "{}")
        except Exception:
            decisions = {}

        raw_bytes = current_app.config.get("_IMPORT_CACHE", {}).pop(imp.id, None)
        if raw_bytes is None:
            flash("Import cache expired. Please re-upload.", "error")
            return redirect(url_for(".upload"))

        commit_import(
            imp,
            raw_bytes,
            current_app.config["ARCHIVE_DIR"],
            imp.institution.name,
            imp.account.name,
            decisions,
        )
        flash("Import committed", "success")
        return redirect(url_for("imports.log", import_id=imp.id))

    return render_template("imports/review.html", form=form, review=review, imp=imp)


@bp.route("/log/<int:import_id>")
def log(import_id):
    imp = Import.query.get_or_404(import_id)
    csrf_form = CSRFOnlyForm()
    return render_template("imports/import_log.html", imp=imp, csrf_form=csrf_form)


@bp.route("/history")
def history():
    items = Import.query.order_by(Import.created_at.desc()).limit(200).all()
    return render_template("imports/history.html", items=items)


@bp.route("/commit/<int:import_id>", methods=["POST", "GET"])
def commit(import_id):
    imp = Import.query.get_or_404(import_id)
    raw_bytes = current_app.config.get("_IMPORT_CACHE", {}).pop(imp.id, None)
    if raw_bytes is None:
        flash("Import cache expired or not found. Please re-upload the CSV.", "error")
        return redirect(url_for("imports.upload"))

    decisions = {}
    commit_import(
        imp,
        raw_bytes,
        current_app.config["ARCHIVE_DIR"],
        imp.institution.name,
        imp.account.name,
        decisions,
    )
    flash("Import committed.", "success")
    return redirect(url_for("imports.log", import_id=imp.id))

@bp.route("/delete_import_txns/<int:import_id>", methods=["POST"])
def delete_import_txns(import_id):
    imp = Import.query.get_or_404(import_id)
    q = Transaction.query.filter_by(import_id=imp.id, is_deleted=False)
    count = 0
    now = datetime.utcnow()
    for t in q:
        t.is_deleted = True
        t.deleted_at = now
        count += 1
    imp.status = "retracted"
    db.session.commit()
    flash(f"Deleted {count} transactions from import #{imp.id}.", "success")
    return redirect(url_for("imports.log", import_id=imp.id))
