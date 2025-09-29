from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import desc
from ..extensions import db
from ..models import Account, Transaction, Import, Category
from ..forms import CSRFOnlyForm  # add this import
from ..forms import CSRFOnlyForm, ManualTransactionForm
from ..utils import to_cents

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

    csrf_form = CSRFOnlyForm()

    # NEW: Fetch all categories for the dropdown
    all_categories = Category.query.order_by(Category.group, Category.name).all()

    return render_template(
        "transactions/list.html",
        account=account,
        items=items,
        q=q,
        sort=sort,
        per_page=per_page,
        csrf_form=csrf_form,
        categories=all_categories  # NEW: Pass categories to the template
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

@bp.route("/<int:txn_id>/set_category", methods=["POST"])
def set_category(txn_id):
    t = Transaction.query.get_or_404(txn_id)
    category_id = request.form.get("category_id")

    # If "None" is selected, clear the category
    if not category_id or category_id == "None":
        t.category_id = None
        flash("Transaction category cleared.", "info")
    else:
        # Verify the category exists before assigning
        cat = Category.query.get(category_id)
        if cat:
            t.category_id = cat.id
            flash(f"Transaction category set to '{cat.name}'.", "success")
        else:
            flash("Invalid category selected.", "error")

    db.session.commit()
    return redirect(_back_to_account(t.account_id))

@bp.route("/account/<int:account_id>/add_manual", methods=["GET", "POST"])
def add_manual(account_id):
    """Display form to add a manual transaction."""
    account = Account.query.get_or_404(account_id)
    form = ManualTransactionForm()

    if form.validate_on_submit():
        # Create a new transaction from the form data
        t = Transaction(
            account_id=account.id,
            txn_date=form.txn_date.data,
            description_raw=form.description_raw.data,
            amount_cents=to_cents(form.amount.data),
            # Note: We leave running_balance_cents as None.
            # The system should ideally recalculate balances,
            # or the next import will provide an updated balance.
        )
        db.session.add(t)
        db.session.commit()
        flash("Manual transaction added successfully.", "success")
        return redirect(url_for(".list_for_account", account_id=account.id))

    return render_template("transactions/add_manual.html", form=form, account=account)


@bp.route("/toggle_transfer/<int:txn_id>", methods=["POST"])
def toggle_transfer(txn_id):
    """Toggles the is_transfer status of a single transaction."""
    t = Transaction.query.get_or_404(txn_id)

    # Flip the boolean value
    t.is_transfer = not t.is_transfer

    db.session.commit()

    status = "marked as transfer" if t.is_transfer else "unmarked as transfer"
    flash(f"Transaction '{t.description_raw}' was {status}.", "success")

    return redirect(_back_to_account(t.account_id))