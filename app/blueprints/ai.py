# srm9385/finance-tracker/finance-tracker-b6479a0b9b4b550a18703e80c76c724f6985583c/app/blueprints/ai.py
from datetime import timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from ..extensions import db
from ..models import Transaction, Category, Rule, Institution, Account, TransferKeyword, \
    RefundKeyword  # <-- Import Rule
from ..services.ai_categorizer import get_category_suggestions, is_ai_configured
from ..forms import AICategorizeForm, RefundFinderForm,CSRFOnlyForm
from sqlalchemy import or_

bp = Blueprint("ai", __name__, url_prefix="/ai")


@bp.route("/categorize", methods=["GET", "POST"])
def categorize():
    # Use request.form for POST and request.args for GET to populate the form
    form_data = request.form if request.method == 'POST' else request.args
    form = AICategorizeForm(form_data)

    # Always populate institution choices
    form.institution_id.choices = [("", "All Institutions")] + [(str(i.id), i.name) for i in Institution.query.order_by(Institution.name).all()]

    # Get selected institution ID (will be a string or None)
    selected_institution_id_str = form.institution_id.data

    # Populate account choices based on selected institution
    if selected_institution_id_str:
        try:
            selected_institution_id = int(selected_institution_id_str)
            form.account_id.choices = [("", "All Accounts")] + [(str(a.id), a.name) for a in Account.query.filter_by(institution_id=selected_institution_id).order_by(Account.name).all()]
        except (ValueError, TypeError):
            # Handle cases where the institution ID is invalid
            form.account_id.choices = [("", "All Accounts")]
    else:
        form.account_id.choices = [("", "All Accounts")]


    if not is_ai_configured():
        flash("AI features are not configured. Please set OPENAI variables in your .env file.", "warning")
        return render_template("ai/categorize.html", suggestions=None, form=form)

    if form.validate_on_submit() and request.method == 'POST':
        scope = form.scope.data
        account_id_str = form.account_id.data
        institution_id_str = form.institution_id.data

        query = Transaction.query

        # Apply filters based on selection
        if institution_id_str:
             query = query.join(Account).filter(Account.institution_id == int(institution_id_str))
        if account_id_str:
            query = query.filter(Transaction.account_id == int(account_id_str))


        if scope == "uncategorized":
            query = query.filter(Transaction.category_id.is_(None))

        transactions_to_review = query.order_by(Transaction.id.asc()).limit(50).all()
        all_categories = Category.query.all()

        if not transactions_to_review:
            flash("No transactions found for the selected scope and account.", "info")
            return redirect(url_for(".categorize"))

        suggestions = []
        llm_batch = []

        rules = Rule.query.all()

        for t in transactions_to_review:
            matched_rule = None
            for rule in rules:
                if rule.keyword.upper() in t.description_raw.upper():
                    matched_rule = rule
                    break

            if matched_rule:
                suggestions.append({
                    "id": t.id,
                    "category_name": matched_rule.category.name,
                    "reason": f"Rule: Matched '{matched_rule.keyword}'"
                })
            else:
                llm_batch.append(t)

        if llm_batch:
            llm_suggestions, error = get_category_suggestions(llm_batch, all_categories)
            if error:
                flash(error, "error")
                return redirect(url_for(".categorize"))
            suggestions.extend(llm_suggestions)

        suggestions.sort(key=lambda x: x['id'])
        session['ai_suggestions'] = suggestions
        return redirect(url_for(".review_suggestions"))

    # For GET requests or failed POST validation, render the form template
    return render_template("ai/categorize.html", form=form)

# (The rest of the file remains unchanged)

@bp.route("/review_suggestions")
def review_suggestions():
    suggestions = session.get('ai_suggestions', [])
    if not suggestions:
        return redirect(url_for('.categorize'))

    txn_ids = [s['id'] for s in suggestions]
    transactions = {t.id: t for t in Transaction.query.filter(Transaction.id.in_(txn_ids)).all()}

    # --- START MODIFICATION ---
    # Sort by name first for consistency
    all_categories = Category.query.order_by(Category.name, Category.group).all()
    transfer_keywords = [kw.keyword for kw in TransferKeyword.query.all()]
    refund_keywords = [kw.keyword for kw in RefundKeyword.query.all()]

    form = CSRFOnlyForm()
    return render_template(
        "ai/review.html",
        suggestions=suggestions,
        transactions=transactions,
        all_categories=all_categories,
        transfer_keywords=transfer_keywords,
        refund_keywords=refund_keywords,
        form=form
    )

@bp.route("/accounts-for-institution/<int:institution_id>")
def accounts_for_institution(institution_id):
    accounts = Account.query.filter_by(institution_id=institution_id, is_active=True).order_by(Account.name).all()
    accounts_data = [{'id': acc.id, 'name': acc.name} for acc in accounts]
    return jsonify(accounts_data)

@bp.route("/apply_suggestions", methods=["POST"])
def apply_suggestions():
    approved_ids = set(request.form.getlist("approve"))
    suggestions = session.get('ai_suggestions', [])
    manual_overrides = {
        int(k.split('_')[-1]): int(v)
        for k, v in request.form.items()
        if k.startswith('manual_category_') and v
    }
    transfer_ids = set(request.form.getlist("mark_as_transfer"))
    refund_ids = set(request.form.getlist("mark_as_refund"))

    if not approved_ids and not manual_overrides and not transfer_ids and not refund_ids:
        flash("No suggestions were approved, manually set, marked as transfers, or marked as refunds.", "info")
        return redirect(url_for('.categorize'))

    suggestion_map = {s['id']: s['category_name'] for s in suggestions}
    category_map = {c.id: c for c in Category.query.all()}
    category_name_map = {c.name: c for c in category_map.values()}

    count = 0
    transfer_count = 0
    refund_count = 0
    all_txn_ids = [s['id'] for s in suggestions]
    transactions_to_update = Transaction.query.filter(Transaction.id.in_(all_txn_ids)).all()

    for transaction in transactions_to_update:
        txn_id = transaction.id

        if str(txn_id) in transfer_ids:
            if not transaction.is_transfer:
                transaction.is_transfer = True
                transfer_count += 1

        if str(txn_id) in refund_ids:
            if not transaction.is_refund:
                transaction.is_refund = True
                refund_count += 1

        if txn_id in manual_overrides:
            cat_id = manual_overrides[txn_id]
            if cat_id in category_map:
                transaction.category_id = cat_id
                count += 1
        elif str(txn_id) in approved_ids:
            suggested_cat_name = suggestion_map.get(txn_id)
            if suggested_cat_name in category_name_map:
                transaction.category_id = category_name_map[suggested_cat_name].id
                count += 1

    db.session.commit()
    session.pop('ai_suggestions', None)

    flash_messages = []
    if transfer_count > 0:
        flash_messages.append(f"Marked {transfer_count} transactions as transfers.")
    if refund_count > 0:
        flash_messages.append(f"Marked {refund_count} transactions as refunds.")

    if flash_messages:
        flash(" ".join(flash_messages), "success")

    return redirect(url_for('dashboard.index'))


@bp.route("/refund-finder", methods=["GET", "POST"])
def refund_finder():
    form = RefundFinderForm()
    form.account_id.choices = [(a.id, f"{a.institution.name} - {a.name}") for a in
                               Account.query.order_by(Account.institution_id, Account.name).all()]

    if form.validate_on_submit():
        account_id = form.account_id.data

        # Find potential refund pairs
        positive_txns = Transaction.query.filter(
            Transaction.account_id == account_id,
            Transaction.amount_cents > 0,
            Transaction.is_refund == False,
            Transaction.is_transfer == False
        ).order_by(Transaction.txn_date.desc()).all()

        refund_pairs = []
        for pos_t in positive_txns:
            # Look for a matching negative transaction within a 60-day window
            time_window = pos_t.txn_date - timedelta(days=60)

            neg_t = Transaction.query.filter(
                Transaction.account_id == account_id,
                Transaction.amount_cents == -pos_t.amount_cents,
                Transaction.txn_date >= time_window,
                Transaction.txn_date <= pos_t.txn_date,
                Transaction.is_refund == False,
                Transaction.is_transfer == False
            ).first()

            if neg_t:
                refund_pairs.append({
                    "refund_id": pos_t.id,
                    "original_id": neg_t.id
                })

        if not refund_pairs:
            flash("No potential refund pairs found in this account.", "info")
            return redirect(url_for('.refund_finder'))

        session['refund_pairs'] = refund_pairs
        return redirect(url_for('.review_refunds'))

    return render_template("ai/refund_finder.html", form=form)


@bp.route("/review-refunds")
def review_refunds():
    pairs = session.get('refund_pairs', [])
    if not pairs:
        return redirect(url_for('.refund_finder'))

    all_ids = [p['refund_id'] for p in pairs] + [p['original_id'] for p in pairs]
    transactions = {t.id: t for t in Transaction.query.filter(Transaction.id.in_(all_ids)).all()}

    form = CSRFOnlyForm()
    return render_template(
        "ai/review_refunds.html",
        pairs=pairs,
        transactions=transactions,
        form=form
    )


@bp.route("/apply-refunds", methods=["POST"])
def apply_refunds():
    approved_pairs = request.form.getlist("approve")  # List of "original_id:refund_id"

    if not approved_pairs:
        flash("No refunds were approved.", "info")
        return redirect(url_for('.categorize'))

    refund_category = Category.query.filter_by(name="Refund").first()
    if not refund_category:
        flash("A 'Refund' category must exist to apply this action. Please create one in the admin panel.", "error")
        return redirect(url_for('.review_refunds'))

    count = 0
    for pair_str in approved_pairs:
        try:
            original_id, refund_id = map(int, pair_str.split(':'))

            # Update both transactions
            Transaction.query.filter(
                or_(Transaction.id == original_id, Transaction.id == refund_id)
            ).update({
                'is_refund': True,
                'category_id': refund_category.id
            })
            count += 2  # two transactions updated per pair
        except (ValueError, IndexError):
            flash(f"Skipping invalid pair data: {pair_str}", "warning")
            continue

    db.session.commit()
    session.pop('refund_pairs', None)

    flash(f"Successfully marked {count} transactions as refunds and updated their category.", "success")
    return redirect(url_for('dashboard.index'))
