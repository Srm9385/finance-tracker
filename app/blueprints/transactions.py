import csv
import io
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Account, Transaction, Category, Institution
from ..forms import CSRFOnlyForm, ManualTransactionForm, TransactionExportForm
from ..utils import to_cents

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


#: Sentinel used in the ``category_id`` query parameter to mean "no category set".
UNCATEGORIZED = "none"


def _int_list(values):
    """Coerce a list of query-string values to ints, dropping anything unparseable."""
    out = []
    for v in values:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


@bp.route("/")
def browse():
    """Review transactions across any number of accounts, filtered by category and joint flag."""
    accounts = (
        Account.query
        .join(Institution, Account.institution_id == Institution.id)
        .options(joinedload(Account.institution))
        .order_by(Institution.name.asc(), Account.name.asc(), Account.id.asc())
        .all()
    )
    all_categories = Category.query.order_by(Category.group, Category.name).all()

    q = (request.args.get("q") or "").strip()
    joint = request.args.get("joint") or ""
    if joint not in ("yes", "no"):
        joint = ""

    valid_account_ids = {a.id for a in accounts}
    selected_account_ids = [
        a_id for a_id in _int_list(request.args.getlist("account_id"))
        if a_id in valid_account_ids
    ]

    raw_categories = request.args.getlist("category_id")
    include_uncategorized = UNCATEGORIZED in raw_categories
    valid_category_ids = {c.id for c in all_categories}
    selected_category_ids = [
        c_id for c_id in _int_list(raw_categories) if c_id in valid_category_ids
    ]

    query = (
        Transaction.query
        .options(joinedload(Transaction.account).joinedload(Account.institution))
        .filter(Transaction.is_deleted == False)
    )

    if selected_account_ids:
        query = query.filter(Transaction.account_id.in_(selected_account_ids))

    category_clauses = []
    if selected_category_ids:
        category_clauses.append(Transaction.category_id.in_(selected_category_ids))
    if include_uncategorized:
        category_clauses.append(Transaction.category_id.is_(None))
    if category_clauses:
        query = query.filter(or_(*category_clauses))

    if joint == "yes":
        query = query.filter(Transaction.is_joint == True)
    elif joint == "no":
        query = query.filter(Transaction.is_joint == False)

    if q:
        query = query.filter(Transaction.description_raw.ilike(f"%{q}%"))

    items = query.order_by(Transaction.txn_date.desc(), Transaction.id.desc()).all()

    account_labels = {
        a.id: f"{a.institution.name} — {a.name}" if a.institution else a.name
        for a in accounts
    }

    table_data = []
    for t in items:
        table_data.append({
            "id": t.id,
            "txn_date": t.txn_date.isoformat(),
            "description_raw": t.description_raw,
            "amount_cents": t.amount_cents,
            "category_id": t.category_id,
            "account_id": t.account_id,
            "account_label": account_labels.get(t.account_id, ""),
            "import_id": t.import_id,
            "is_transfer": t.is_transfer,
            "is_refund": t.is_refund,
            "is_joint": t.is_joint,
        })

    # Sort by name first, then group for a more intuitive dropdown
    categories_list = [
        {"id": c.id, "group": c.group, "name": c.name}
        for c in sorted(all_categories, key=lambda c: (c.name, c.group))
    ]

    # Accounts grouped by institution for the filter panel.
    account_groups = []
    for a in accounts:
        inst_name = a.institution.name if a.institution else "No institution"
        if not account_groups or account_groups[-1]["institution"] != inst_name:
            account_groups.append({"institution": inst_name, "accounts": []})
        account_groups[-1]["accounts"].append(a)

    # Categories grouped for the filter panel (already ordered by group, name).
    category_groups = []
    for c in all_categories:
        if not category_groups or category_groups[-1]["group"] != c.group:
            category_groups.append({"group": c.group, "categories": []})
        category_groups[-1]["categories"].append(c)

    # A single selected account keeps the old "one account" heading.
    single_account = None
    if len(selected_account_ids) == 1:
        single_account = next(
            (a for a in accounts if a.id == selected_account_ids[0]), None
        )

    return render_template(
        "transactions/list.html",
        q=q,
        joint=joint,
        table_data=table_data,
        categories=categories_list,
        account_groups=account_groups,
        category_groups=category_groups,
        selected_account_ids=selected_account_ids,
        selected_category_ids=selected_category_ids,
        include_uncategorized=include_uncategorized,
        uncategorized_value=UNCATEGORIZED,
        single_account=single_account,
        total_accounts=len(accounts),
        csrf_form=CSRFOnlyForm(),
    )


@bp.route("/account/<int:account_id>")
def list_for_account(account_id):
    """Back-compat entry point: the single-account view is the browse view pre-filtered."""
    account = Account.query.get_or_404(account_id)
    return redirect(
        url_for(
            ".browse",
            account_id=account.id,
            q=request.args.get("q") or None,
        )
    )


@bp.route("/export", methods=["GET", "POST"])
def export_transactions():
    form = TransactionExportForm()

    all_accounts = (
        Account.query
        .join(Institution, Account.institution_id == Institution.id)
        .options(joinedload(Account.institution))
        .order_by(Institution.name.asc(), Account.name.asc(), Account.id.asc())
        .all()
    )

    form.accounts.choices = [
        (account.id, f"{account.institution.name} — {account.name}")
        for account in all_accounts
    ]

    if form.validate_on_submit():
        selected_account_ids = [int(a_id) for a_id in form.accounts.data]

        txn_query = (
            Transaction.query.options(
                joinedload(Transaction.account).joinedload(Account.institution),
                joinedload(Transaction.category),
            )
            .filter(
                Transaction.account_id.in_(selected_account_ids),
                Transaction.is_deleted == False,
            )
        )

        if form.start_date.data:
            txn_query = txn_query.filter(Transaction.txn_date >= form.start_date.data)
        if form.end_date.data:
            txn_query = txn_query.filter(Transaction.txn_date <= form.end_date.data)
        if form.joint_only.data:
            txn_query = txn_query.filter(Transaction.is_joint == True)

        transactions = txn_query.order_by(
            Transaction.txn_date.asc(),
            Transaction.id.asc(),
        ).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "description", "amount", "category", "account", "institution"])

        for txn in transactions:
            account = txn.account
            institution = account.institution if account else None
            category_name = txn.category.name if txn.category else ""

            writer.writerow([
                txn.txn_date.isoformat(),
                txn.description_raw,
                f"{txn.amount_cents / 100:.2f}",
                category_name,
                account.name if account else "",
                institution.name if institution else "",
            ])

        filename = f"transactions-export-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
        )
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    return render_template("transactions/export.html", form=form)

@bp.route("/delete/<int:txn_id>", methods=["POST"])
def delete_single(txn_id):
    t = Transaction.query.get_or_404(txn_id)
    if t.is_deleted:
        flash("Transaction already deleted.", "info")
        return redirect(_back_to_account(t.account_id))
    t.is_deleted = True
    t.deleted_at = datetime.utcnow()
    db.session.commit()
    flash("Transaction deleted (soft).", "success")
    return redirect(_back_to_account(t.account_id))


def _back_to_account(account_id):
    """Return to the filtered list the action was triggered from, if we know it."""
    nxt = request.form.get("next") or request.args.get("next")
    # Only honour same-site relative paths.
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return url_for("transactions.browse", account_id=account_id, q=request.args.get("q"))


@bp.route("/<int:txn_id>/set_category", methods=["POST"])
def set_category(txn_id):
    t = Transaction.query.get_or_404(txn_id)
    category_id = request.form.get("category_id")
    # The table edits categories in place via fetch; skip the redirect (and the
    # full re-render of the list it implies) for those callers.
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not category_id or category_id == "None":
        t.category_id = None
        if not wants_json:
            flash("Transaction category cleared.", "info")
    else:
        cat = Category.query.get(category_id)
        if cat:
            t.category_id = cat.id
            if not wants_json:
                flash(f"Transaction category set to '{cat.name}'.", "success")
        elif wants_json:
            return jsonify({"status": "error", "message": "Invalid category selected."}), 400
        else:
            flash("Invalid category selected.", "error")

    db.session.commit()
    if wants_json:
        return jsonify({"status": "success", "category_id": t.category_id})
    return redirect(_back_to_account(t.account_id))


@bp.route("/account/<int:account_id>/add_manual", methods=["GET", "POST"])
def add_manual(account_id):
    account = Account.query.get_or_404(account_id)
    form = ManualTransactionForm()

    if form.validate_on_submit():
        t = Transaction(
            account_id=account.id,
            txn_date=form.txn_date.data,
            description_raw=form.description_raw.data,
            amount_cents=to_cents(form.amount.data),
        )
        db.session.add(t)
        db.session.commit()
        flash("Manual transaction added successfully.", "success")
        return redirect(url_for(".browse", account_id=account.id))

    return render_template("transactions/add_manual.html", form=form, account=account)


@bp.route("/toggle_transfer/<int:txn_id>", methods=["POST"])
def toggle_transfer(txn_id):
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        t = Transaction.query.get_or_404(txn_id)
        t.is_transfer = not t.is_transfer
        db.session.commit()
        return jsonify({'is_transfer': t.is_transfer, 'status': 'success'})
    return jsonify({'status': 'error', 'message': 'CSRF validation failed.'}), 400


@bp.route("/toggle_refund/<int:txn_id>", methods=["POST"])
def toggle_refund(txn_id):
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        t = Transaction.query.get_or_404(txn_id)
        t.is_refund = not t.is_refund
        db.session.commit()
        return jsonify({'is_refund': t.is_refund, 'status': 'success'})
    return jsonify({'status': 'error', 'message': 'CSRF validation failed.'}), 400


@bp.route("/toggle_joint/<int:txn_id>", methods=["POST"])
def toggle_joint(txn_id):
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        t = Transaction.query.get_or_404(txn_id)
        t.is_joint = not t.is_joint
        db.session.commit()
        return jsonify({'is_joint': t.is_joint, 'status': 'success'})
    return jsonify({'status': 'error', 'message': 'CSRF validation failed.'}), 400
