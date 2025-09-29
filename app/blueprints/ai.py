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

    cat_names = [s['category_name'] for s in suggestions]
    categories = {c.name: c for c in Category.query.filter(Category.name.in_(cat_names)).all()}

    form = CSRFOnlyForm()
    return render_template(
        "ai/review.html",
        suggestions=suggestions,
        transactions=transactions,
        categories=categories,
        form=form  # <-- AND PASS THE FORM HERE
    )

@bp.route("/apply_suggestions", methods=["POST"])
def apply_suggestions():
    approved_ids = request.form.getlist("approve")  # Gets a list of all checked transaction IDs
    suggestions = session.get('ai_suggestions', [])

    if not approved_ids or not suggestions:
        flash("No suggestions to apply.", "info")
        return redirect(url_for('.categorize'))

    # Create a mapping of transaction ID to suggested category name
    suggestion_map = {str(s['id']): s['category_name'] for s in suggestions}

    # Get all category objects from the database in one query
    all_categories = {c.name: c for c in Category.query.all()}

    count = 0
    for txn_id_str in approved_ids:
        if txn_id_str in suggestion_map:
            category_name = suggestion_map[txn_id_str]
            category = all_categories.get(category_name)
            transaction = Transaction.query.get(txn_id_str)

            if transaction and category:
                transaction.category_id = category.id
                count += 1

    db.session.commit()
    session.pop('ai_suggestions', None)  # Clear suggestions from session
    flash(f"Successfully applied categories to {count} transactions.", "success")
    return redirect(url_for('dashboard.index'))