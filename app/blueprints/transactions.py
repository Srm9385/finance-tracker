from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import desc
from ..extensions import db
from ..models import Account, Transaction, Import
from ..forms import CSRFOnlyForm  # add this import

bp = Blueprint("transactions", __name__, url_prefix="/transactions")

@bp.route("/account/<int:account_id>")
def list_for_account(account_id):
    account = Account.query.get_or_404(account_id)

    # Query params
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 50)), 10), 200)
    sort = request.args.get("sort", "date_desc")
    q = (request.args.get("q") or "").strip()

    query = Transaction.query.filter(
        Transaction.account_id == account.id,
        Transaction.is_deleted == False,
    )

    if q:
        # Basic substring filter on description
        query = query.filter(Transaction.description_raw.ilike(f"%{q}%"))

    # Sorting
    if sort == "date_asc":
        query = query.order_by(Transaction.txn_date.asc(), Transaction.id.asc())
    elif sort == "amount_desc":
        query = query.order_by(Transaction.amount_cents.desc(), Transaction.id.desc())
    elif sort == "amount_asc":
        query = query.order_by(Transaction.amount_cents.asc(), Transaction.id.asc())
    else:  # default date_desc
        query = query.order_by(Transaction.txn_date.desc(), Transaction.id.desc())

    items = query.paginate(page=page, per_page=per_page, error_out=False)

    csrf_form = CSRFOnlyForm()  # NEW
    return render_template(
        "transactions/list.html",
        account=account,
        items=items,
        q=q,
        sort=sort,
        per_page=per_page,
        csrf_form=csrf_form,   # NEW
    )

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
    # preserve minimal context if present
    page = request.args.get("page")
    sort = request.args.get("sort")
    q = request.args.get("q")
    return url_for("transactions.list_for_account", account_id=account_id, page=page, sort=sort, q=q)
