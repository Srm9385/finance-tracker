from flask import Blueprint, render_template
from sqlalchemy import func, desc
from ..extensions import db
from ..models import Account, Transaction
from datetime import date
from sqlalchemy.orm import joinedload

bp = Blueprint("dashboard", __name__)

@bp.route("/")
def index():
    balances = []
    for acc in Account.query.all():
        latest_with_balance = (
            db.session.query(Transaction)
            .filter_by(account_id=acc.id)
            .filter(Transaction.running_balance_cents.isnot(None))
            .filter(Transaction.is_deleted == False)   # NEW
            .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
            .first()
        )

        if latest_with_balance:
            bal_cents = latest_with_balance.running_balance_cents or 0
        else:
            bal_cents = (
                db.session.query(func.coalesce(func.sum(Transaction.amount_cents), 0))
                .filter(Transaction.account_id == acc.id)
                .filter(Transaction.is_deleted == False)   # NEW
                .scalar() or 0
            )
        bal_cents = int(bal_cents)
        balances.append({"account": acc, "balance": bal_cents / 100.0})

    # MTD spend excludes transfers and deleted
    # MTD spend excludes transfers and deleted
    today = date.today()
    month_start = today.replace(day=1)
    mtd_cents = (
            db.session.query(func.coalesce(func.sum(Transaction.amount_cents), 0))
            .filter(
                Transaction.txn_date >= month_start,
                Transaction.txn_date <= today,
                Transaction.is_transfer == False,
                Transaction.is_deleted == False,
                Transaction.amount_cents < 0  # <-- ADD THIS LINE
            ).scalar() or 0
    )
    mtd = int(mtd_cents) / 100.0
    mtd_transactions = (
        Transaction.query
        .options(joinedload(Transaction.account))  # Add this line to eagerly load the account
        .filter(
            Transaction.txn_date >= month_start,
            Transaction.txn_date <= today,
            Transaction.is_transfer == False,
            Transaction.is_deleted == False,
            Transaction.amount_cents < 0
        )
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
        .all()
    )
    return render_template(
        "dashboard/index.html",
        balances=balances,
        mtd=mtd,
        mtd_transactions=mtd_transactions  # Pass the new list to the template
    )