# srm9385/finance-tracker/finance-tracker-b6479a0b9b4b550a18703e80c76c724f6985583c/app/blueprints/ai.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from ..extensions import db
from ..models import Transaction, Category, Rule, Institution, Account, TransferKeyword  # <-- Import Rule
from ..services.ai_categorizer import get_category_suggestions, is_ai_configured
from ..forms import CSRFOnlyForm, AICategorizeForm

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
    print(f"DEBUG: Keywords being sent to template: {transfer_keywords}")
    form = CSRFOnlyForm()
    return render_template(
        "ai/review.html",
        suggestions=suggestions,
        transactions=transactions,
        all_categories=all_categories,
        transfer_keywords=transfer_keywords, # Pass keywords to template
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

    if not approved_ids and not manual_overrides and not transfer_ids:
        flash("No suggestions were approved, manually set, or marked as transfers.", "info")
        return redirect(url_for('.categorize'))

    suggestion_map = {s['id']: s['category_name'] for s in suggestions}
    category_map = {c.id: c for c in Category.query.all()}
    category_name_map = {c.name: c for c in category_map.values()}

    count = 0
    transfer_count = 0
    all_txn_ids = [s['id'] for s in suggestions]
    transactions_to_update = Transaction.query.filter(Transaction.id.in_(all_txn_ids)).all()

    for transaction in transactions_to_update:
        txn_id = transaction.id

        if str(txn_id) in transfer_ids:
            if not transaction.is_transfer:
                transaction.is_transfer = True
                transfer_count += 1

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
    if count > 0:
        flash_messages.append(f"Successfully applied categories to {count} transactions.")
    if transfer_count > 0:
        flash_messages.append(f"Marked {transfer_count} transactions as transfers.")

    if flash_messages:
        flash(" ".join(flash_messages), "success")

    return redirect(url_for('dashboard.index'))