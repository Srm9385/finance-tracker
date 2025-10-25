# app/blueprints/dashboard.py
from collections import defaultdict
from flask import Blueprint, render_template, jsonify, request
from sqlalchemy import func, desc, and_
from ..extensions import db
from ..models import Account, Transaction, Category
from datetime import date, datetime, timedelta
from sqlalchemy.orm import joinedload

bp = Blueprint("dashboard", __name__)


def _parse_bool(value):
    return str(value).lower() in {"1", "true", "yes", "on"}


@bp.route("/")
def index():
    # ... (existing index route)
    balances = []
    for acc in Account.query.all():
        latest_with_balance = (
            db.session.query(Transaction)
            .filter_by(account_id=acc.id)
            .filter(Transaction.running_balance_cents.isnot(None))
            .filter(Transaction.is_deleted == False)
            .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
            .first()
        )

        if latest_with_balance:
            bal_cents = latest_with_balance.running_balance_cents or 0
        else:
            bal_cents = (
                    db.session.query(func.coalesce(func.sum(Transaction.amount_cents), 0))
                    .filter(Transaction.account_id == acc.id)
                    .filter(Transaction.is_deleted == False)
                    .scalar() or 0
            )
        bal_cents = int(bal_cents)
        balances.append({"account": acc, "balance": bal_cents / 100.0})

    today = date.today()
    month_start = today.replace(day=1)
    mtd_cents = (
            db.session.query(func.coalesce(func.sum(Transaction.amount_cents), 0))
            .filter(
                Transaction.txn_date >= month_start,
                Transaction.txn_date <= today,
                Transaction.is_transfer == False,
                Transaction.is_deleted == False,
                Transaction.amount_cents < 0
            ).scalar() or 0
    )
    mtd = int(mtd_cents) / 100.0
    mtd_transactions = (
        Transaction.query
        .options(joinedload(Transaction.account))
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

    filter_options = {
        'categories': [c.name for c in Category.query.order_by(Category.name).all()],
        'groups': [g[0] for g in db.session.query(Category.group).distinct().order_by(Category.group).all()],
        'accounts': [a.name for a in Account.query.order_by(Account.name).all()],
    }

    return render_template(
        "dashboard/index.html",
        balances=balances,
        mtd=mtd,
        mtd_transactions=mtd_transactions,
        filter_options=filter_options
    )


@bp.route("/chart-data")
def chart_data():
    # ... (existing chart-data route)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    group_by = request.args.get('group_by', 'category')
    joint_only = _parse_bool(request.args.get('joint_only', ''))

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else date.min
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else date.today()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    query = db.session.query(
        func.sum(Transaction.amount_cents).label('total_spending')
    ).filter(
        Transaction.txn_date >= start_date,
        Transaction.txn_date <= end_date,
        Transaction.is_deleted == False,
        Transaction.is_transfer == False,
        Transaction.amount_cents < 0
    )

    if joint_only:
        query = query.filter(Transaction.is_joint == True)

    if group_by == 'category':
        query = query.join(Category).add_columns(Category.name.label('label')).group_by(Category.name)
    elif group_by == 'group':
        query = query.join(Category).add_columns(Category.group.label('label')).group_by(Category.group)
    elif group_by == 'account':
        query = query.join(Account).add_columns(Account.name.label('label')).group_by(Account.name)
    else:
        return jsonify({"error": "Invalid group_by parameter."}), 400

    results = query.order_by(desc('total_spending')).all()

    labels = [row.label for row in results]
    data = [abs(float(row.total_spending)) / 100.0 for row in results]

    return jsonify(labels=labels, data=data)


@bp.route("/income-over-time")
def income_over_time():
    """Endpoint for the monthly income bar chart."""
    account_name = request.args.get('account_name')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    try:
        # Set default to last year if no start date is provided
        default_start = (date.today().replace(day=1) - timedelta(days=365)).replace(day=1)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else default_start
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else date.today()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Query for monthly income
    query = db.session.query(
        func.date_trunc('month', Transaction.txn_date).label('month'),
        func.sum(Transaction.amount_cents).label('total_income')
    ).join(Category).filter(
        Transaction.is_deleted == False,
        Transaction.amount_cents > 0,
        Category.group == 'Income'
    )

    if account_name:
        query = query.join(Account).filter(Account.name == account_name)

    # Use the adjustable date range from the request
    query = query.filter(Transaction.txn_date >= start_date, Transaction.txn_date <= end_date)

    results = query.group_by('month').order_by('month').all()

    labels = [row.month.strftime('%Y-%m') for row in results]
    data = [abs(float(row.total_income)) / 100.0 for row in results]

    return jsonify(labels=labels, data=data)


@bp.route("/income-vs-spending")
def income_vs_spending():
    """Endpoint for the income vs. spending chart."""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    # --- START MODIFICATION ---
    # Use getlist to accept multiple values
    account_names = request.args.getlist('account_name')
    category_names = request.args.getlist('category_name')
    joint_only = _parse_bool(request.args.get('joint_only', ''))
    # --- END MODIFICATION ---

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else (
                    date.today().replace(day=1) - timedelta(days=365)).replace(day=1)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else date.today()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Query for income
    income_query = db.session.query(
        func.date_trunc('month', Transaction.txn_date).label('month'),
        func.sum(Transaction.amount_cents).label('total_income')
    ).join(Category).filter(
        Transaction.txn_date >= start_date,
        Transaction.txn_date <= end_date,
        Transaction.is_deleted == False,
        Transaction.is_transfer == False,
        Transaction.amount_cents > 0,
        Category.group == 'Income'
    )

    # Query for spending
    spending_query = db.session.query(
        func.date_trunc('month', Transaction.txn_date).label('month'),
        func.sum(Transaction.amount_cents).label('total_spending')
    ).filter(
        Transaction.txn_date >= start_date,
        Transaction.txn_date <= end_date,
        Transaction.is_deleted == False,
        Transaction.is_transfer == False,
        Transaction.amount_cents < 0
    )

    # --- START MODIFICATION ---
    if account_names:
        income_query = income_query.join(Account).filter(Account.name.in_(account_names))
        spending_query = spending_query.join(Account).filter(Account.name.in_(account_names))

    if category_names:
        # Spending query needs the join to filter by category name
        spending_query = spending_query.join(Category).filter(Category.name.in_(category_names))
        # Income is already joined, just add the filter
        income_query = income_query.filter(Category.name.in_(category_names))
    # --- END MODIFICATION ---

    if joint_only:
        income_query = income_query.filter(Transaction.is_joint == True)
        spending_query = spending_query.filter(Transaction.is_joint == True)

    # Combine results
    monthly_data = defaultdict(lambda: {'income': 0, 'spending': 0})
    for row in income_query.group_by('month').all():
        monthly_data[row.month.strftime('%Y-%m')]['income'] = float(row.total_income) / 100.0
    for row in spending_query.group_by('month').all():
        monthly_data[row.month.strftime('%Y-%m')]['spending'] = abs(float(row.total_spending)) / 100.0

    # ... (rest of the function remains the same)
    # Ensure all months in the range are present
    sorted_months = sorted(monthly_data.keys())
    if not sorted_months:
        return jsonify(labels=[], income_data=[], spending_data=[])

    all_months = []
    current_date = datetime.strptime(sorted_months[0], '%Y-%m').date()
    end_loop_date = datetime.strptime(sorted_months[-1], '%Y-%m').date()

    while current_date <= end_loop_date:
        all_months.append(current_date.strftime('%Y-%m'))
        # Move to the first day of the next month
        next_month = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        current_date = next_month

    labels = all_months
    income_data = [monthly_data.get(month, {}).get('income', 0) for month in all_months]
    spending_data = [monthly_data.get(month, {}).get('spending', 0) for month in all_months]

    return jsonify(labels=labels, income_data=income_data, spending_data=spending_data)


@bp.route("/spending-over-time")
def spending_over_time():
    """Endpoint for the time-series spending chart."""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    granularity = request.args.get('granularity', 'day')
    filter_type = request.args.get('filter_type')
    filter_value = request.args.get('filter_value')
    joint_only = _parse_bool(request.args.get('joint_only', ''))

    try:
        start_date = datetime.strptime(start_date_str,
                                       '%Y-%m-%d').date() if start_date_str else date.today() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else date.today()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    query = db.session.query(
        func.date_trunc(granularity, Transaction.txn_date).label('time_period'),
        func.sum(Transaction.amount_cents).label('total_spending')
    ).filter(
        Transaction.txn_date >= start_date,
        Transaction.txn_date <= end_date,
        Transaction.is_deleted == False,
        Transaction.is_transfer == False,
        Transaction.amount_cents < 0
    )

    if joint_only:
        query = query.filter(Transaction.is_joint == True)

    if filter_type and filter_value:
        if filter_type == 'category':
            query = query.join(Category).filter(Category.name == filter_value)
        elif filter_type == 'group':
            query = query.join(Category).filter(Category.group == filter_value)
        elif filter_type == 'account':
            query = query.join(Account).filter(Account.name == filter_value)

    results = query.group_by('time_period').order_by('time_period').all()

    # --- START MODIFICATION ---
    # Create a dictionary for quick lookups
    spending_map = {row.time_period.date(): abs(float(row.total_spending)) / 100.0 for row in results}

    # Generate a complete date range and fill in the gaps
    chart_data = []
    current_date = start_date
    delta = timedelta(days=1)

    while current_date <= end_date:
        # For weekly and monthly, we need to find the start of the period
        period_start = current_date
        if granularity == 'week':
            period_start = current_date - timedelta(days=current_date.weekday())
        elif granularity == 'month':
            period_start = current_date.replace(day=1)

        # Check if we have data for this period's start date
        amount = spending_map.get(period_start, 0)
        chart_data.append({'x': current_date.isoformat(), 'y': amount})

        # Increment to the next period to avoid duplicate entries for the same week/month
        if granularity == 'week':
            current_date += timedelta(weeks=1)
        elif granularity == 'month':
            # Move to the first day of the next month
            next_month = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            current_date = next_month
        else:  # Daily
            current_date += delta

    return jsonify(chart_data)
    # --- END MODIFICATION ---
