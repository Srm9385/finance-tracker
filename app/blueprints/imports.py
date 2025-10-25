import io
import json
import uuid
import pandas as pd
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, abort, jsonify
)
from ..models import Institution, Account, Mapper, Import, Transaction
from ..forms import ImportUploadForm, ReviewDecisionForm, MappingWizardForm
from ..services.importer import run_import, _normalize_frame
from ..services.review import commit_import
from ..services.mapping import create_mapper, guess_mapping_from_headers
from datetime import datetime
from ..extensions import db
from ..forms import CSRFOnlyForm


bp = Blueprint("imports", __name__)


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    form = ImportUploadForm()

    # --- START MODIFICATION ---
    # Populate choices for ALL requests to ensure validation works on POST
    form.institution_id.choices = [
        (i.id, i.name) for i in Institution.query.filter_by(is_active=True).order_by(Institution.name).all()
    ]

    # Determine the selected institution from form data on POST, or default to the first on GET
    selected_inst_id = None
    if form.institution_id.data:
        selected_inst_id = form.institution_id.data
    elif form.institution_id.choices:
        selected_inst_id = form.institution_id.choices[0][0]

    # Populate account choices based on the selected institution
    if selected_inst_id:
        form.account_id.choices = [
            (a.id, f"{a.name} ({a.type})")
            for a in Account.query.filter_by(institution_id=selected_inst_id, is_active=True).order_by(Account.name)
        ]

        # Determine the selected account
        selected_acct_id = form.account_id.data
        if not selected_acct_id and form.account_id.choices:
            selected_acct_id = form.account_id.choices[0][0]

        # Populate mapper choices based on the selected account
        if selected_acct_id:
            form.mapper_id.choices = [(-1, "Guess from CSV (no mapping)")] + [
                (m.id, f"v{m.version}")
                for m in Mapper.query.filter_by(account_id=selected_acct_id).order_by(Mapper.version.desc())
            ]
        else:
            form.mapper_id.choices = [(-1, "Guess from CSV (no mapping)")]
    # --- END MODIFICATION ---

    if form.validate_on_submit():  # This is only true for POST
        institution = Institution.query.get(form.institution_id.data)
        account = Account.query.get(form.account_id.data)
        f = request.files["file"]

        if form.mapper_id.data != -1:
            mapper = Mapper.query.get(form.mapper_id.data)
            imp, raw_bytes, review = run_import(None, f, institution, account, mapper, current_app.config)
            current_app.config.setdefault("_IMPORT_CACHE", {})[imp.id] = raw_bytes
            flash("Parsed file. Review decisions below.", "info")
            return redirect(url_for(".review", import_id=imp.id))

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
            "headers": list(df.columns),
            "guessed": guessed,
        }
        return redirect(url_for(".wizard_from_upload", token=token))

    return render_template("imports/upload.html", form=form)

@bp.route("/wizard/<token>", methods=["GET", "POST"])
def wizard_from_upload(token):
    cache = current_app.config.setdefault("_IMPORT_CACHE", {}).get(token)
    if not cache:
        flash("Upload session expired. Please re-upload your CSV.", "error")
        return redirect(url_for(".upload"))

    institution = Institution.query.get(cache["institution_id"])
    account = Account.query.get(cache["account_id"])

    # On form submission (POST), we either save and import, or just re-render to test.
    if request.method == "POST":
        form = MappingWizardForm(request.form)
        # The 'action' determines if we save or just test the mapping.
        action = request.form.get("action")

        if form.validate():
            schema = dict(
                date_col=form.date_col.data,
                date_fmt=form.date_fmt.data,
                desc_col=form.desc_col.data,
                indicator_col=form.indicator_col.data or None,
                amount_col=form.amount_col.data or None,
                debit_col=form.debit_col.data or None,
                credit_col=form.credit_col.data or None,
                balance_col=form.balance_col.data or None,
                exclude_pending=form.exclude_pending.data,
            )

            # If the action is to save, we create the mapper and run the import.
            if action == "save_and_import":
                mapper = create_mapper(institution.id, account.id, schema)
                raw_bytes = cache["raw"]

                class _FileStorageMock:
                    filename = cache["original_filename"]
                    def read(self): return raw_bytes

                imp, raw_bytes_out, review = run_import(None, _FileStorageMock(), institution, account, mapper, current_app.config)
                current_app.config["_IMPORT_CACHE"].pop(token, None)
                current_app.config["_IMPORT_CACHE"][imp.id] = raw_bytes_out

                flash(f"Mapping v{mapper.version} created and applied. Review import below.", "success")
                return redirect(url_for(".review", import_id=imp.id))

            # Otherwise (if action is 'test' or not specified), we fall through to the GET logic
            # to re-render the page with an updated preview.
    else: # GET request
        guessed = cache["guessed"]
        form = MappingWizardForm(data=guessed)

    # This part runs for both GET requests and for POST requests that aren't saving.
    # It generates the preview.
    preview_rows = []
    try:
        # Get the current schema from the form (either from 'guessed' on GET, or from user input on POST).
        current_schema = dict(
            date_col=form.date_col.data,
            date_fmt=form.date_fmt.data,
            desc_col=form.desc_col.data,
            indicator_col=form.indicator_col.data,
            amount_col=form.amount_col.data,
            debit_col=form.debit_col.data,
            credit_col=form.credit_col.data,
            balance_col=form.balance_col.data
        )
        df = pd.read_csv(io.BytesIO(cache['raw']), nrows=5)
        preview_rows = _normalize_frame(df, current_schema)
    except Exception as e:
        flash(f"Could not generate preview with current settings: {e}", "error")


    return render_template(
        "admin/mapper_edit.html",
        form=form,
        institution=institution,
        account=account,
        token=token,
        headers=cache.get("headers", []),
        preview_rows=preview_rows,
    )


@bp.route("/accounts-for-institution/<int:institution_id>")
def accounts_for_institution(institution_id):
    accounts = Account.query.filter_by(institution_id=institution_id, is_active=True).order_by(Account.name).all()

    accounts_data = []
    for acc in accounts:
        mappers = Mapper.query.filter_by(account_id=acc.id).order_by(Mapper.version.desc()).all()
        accounts_data.append({
            'id': acc.id,
            'name': f"{acc.name} ({acc.type})",
            'mappers': [{'id': m.id, 'name': f"v{m.version}"} for m in mappers]
        })

    return jsonify(accounts_data)


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
