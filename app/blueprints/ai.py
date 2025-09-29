from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..extensions import db
from ..models import Transaction, Category
from ..services.ai_categorizer import get_category_suggestions, is_ai_configured
from ..forms import CSRFOnlyForm # <-- ADD THIS IMPORT

bp = Blueprint("ai", __name__, url_prefix="/ai")


@bp.route("/categorize", methods=["GET", "POST"])
def categorize():

    form = CSRFOnlyForm()  # <-- INSTANTIATE THE FORM

    if not is_ai_configured():
        flash("AI features are not configured. Please set OPENAI variables in your .env file.", "warning")
        return render_template("ai/categorize.html", suggestions=None, form=form)  # <-- PASS THE FORM

    if request.method == "POST":
        scope = request.form.get("scope", "uncategorized")

        # Determine which transactions to query
        query = Transaction.query
        if scope == "uncategorized":
            query = query.filter(Transaction.category_id.is_(None))

        transactions_to_review = query.order_by(Transaction.txn_date.desc()).limit(50).all()  # Limit to 50 at a time
        all_categories = Category.query.all()

        if not transactions_to_review:
            flash("No transactions found for the selected scope.", "info")
            return redirect(url_for(".categorize"))

        suggestions, error = get_category_suggestions(transactions_to_review, all_categories)

        if error:
            flash(error, "error")
            return redirect(url_for(".categorize"))

        # Store suggestions in the session to use on the next step
        session['ai_suggestions'] = suggestions
        return redirect(url_for(".review_suggestions"))

    return render_template("ai/categorize.html", suggestions=None, form=form) # <-- PASS THE FORM

@bp.route("/review_suggestions")
def review_suggestions():
    suggestions = session.get('ai_suggestions', [])
    if not suggestions:
        return redirect(url_for('.categorize'))

    # For display, we need the full transaction and category objects
    txn_ids = [s['id'] for s in suggestions]
    transactions = {t.id: t for t in Transaction.query.filter(Transaction.id.in_(txn_ids)).all()}

    # Fetch all categories for the manual override dropdowns
    all_categories = Category.query.order_by(Category.group, Category.name).all()

    form = CSRFOnlyForm()
    return render_template(
        "ai/review.html",
        suggestions=suggestions,
        transactions=transactions,
        all_categories=all_categories,  # Pass all categories to the template
        form=form  # <-- AND PASS THE FORM HERE
    )

@bp.route("/apply_suggestions", methods=["POST"])
def apply_suggestions():
    approved_ids = set(request.form.getlist("approve"))
    suggestions = session.get('ai_suggestions', [])
    manual_overrides = {
        int(k.split('_')[-1]): int(v)
        for k, v in request.form.items()
        if k.startswith('manual_category_') and v
    }

    if not approved_ids and not manual_overrides:
        flash("No suggestions were approved or manually set.", "info")
        return redirect(url_for('.categorize'))

    suggestion_map = {s['id']: s['category_name'] for s in suggestions}
    category_map = {c.id: c for c in Category.query.all()}
    category_name_map = {c.name: c for c in category_map.values()}

    count = 0
    # Process all transactions that were part of the suggestion batch
    for suggestion in suggestions:
        txn_id = suggestion['id']
        transaction = Transaction.query.get(txn_id)
        if not transaction:
            continue

        # Case 1: Manual override takes highest precedence
        if txn_id in manual_overrides:
            cat_id = manual_overrides[txn_id]
            if cat_id in category_map:
                transaction.category_id = cat_id
                count += 1
        # Case 2: Approved AI suggestion
        elif str(txn_id) in approved_ids:
            suggested_cat_name = suggestion_map.get(txn_id)
            if suggested_cat_name in category_name_map:
                transaction.category_id = category_name_map[suggested_cat_name].id
                count += 1

    db.session.commit()
    session.pop('ai_suggestions', None)
    flash(f"Successfully applied categories to {count} transactions.", "success")
    return redirect(url_for('dashboard.index'))