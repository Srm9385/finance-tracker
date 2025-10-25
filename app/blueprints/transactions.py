from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy import desc
from ..extensions import db
from ..models import Account, Transaction, Category
from ..forms import CSRFOnlyForm, ManualTransactionForm
from ..utils import to_cents
import json

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@bp.route("/account/<int:account_id>")
def list_for_account(account_id):
    account = Account.query.get_or_404(account_id)
    q = (request.args.get("q") or "").strip()

    query = Transaction.query.filter(
        Transaction.account_id == account.id,
        Transaction.is_deleted == False,
    )

    if q:
        query = query.filter(Transaction.description_raw.ilike(f"%{q}%"))

    items = query.order_by(Transaction.txn_date.desc(), Transaction.id.desc()).all()

    table_data = []
    for t in items:
        table_data.append({
            "id": t.id,
            "txn_date": t.txn_date.isoformat(),
            "description_raw": t.description_raw,
            "amount_cents": t.amount_cents,
            "category_id": t.category_id,
            "import_id": t.import_id,
            "is_transfer": t.is_transfer,
            "is_refund": t.is_refund,
            "is_joint": t.is_joint,
        })

    # Sort by name first, then group for a more intuitive dropdown
    all_categories = Category.query.order_by(Category.name, Category.group).all()
    # --- END MODIFICATION ---

    categories_list = [
        {"id": c.id, "group": c.group, "name": c.name} for c in all_categories
    ]

    csrf_form = CSRFOnlyForm()

    return render_template(
        "transactions/list.html",
        account=account,
        q=q,
        table_data=table_data,
        categories=categories_list,
        csrf_form=csrf_form
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
    q = request.args.get("q")
    return url_for("transactions.list_for_account", account_id=account_id, q=q)


@bp.route("/<int:txn_id>/set_category", methods=["POST"])
def set_category(txn_id):
    t = Transaction.query.get_or_404(txn_id)
    category_id = request.form.get("category_id")

    if not category_id or category_id == "None":
        t.category_id = None
        flash("Transaction category cleared.", "info")
    else:
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
        return redirect(url_for(".list_for_account", account_id=account.id))

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
