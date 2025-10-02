from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..extensions import db
from ..services.mapping import create_mapper
from ..models import Institution, Account, Category, Transaction, Rule
from ..forms import InstitutionForm, AccountForm, MappingWizardForm, CSRFOnlyForm, CategoryForm, RuleForm
from sqlalchemy.exc import IntegrityError

# --- END: THE FIX ---

bp = Blueprint("admin", __name__)


@bp.route("/", methods=["GET", "POST"])
def index():
    inst_form = InstitutionForm(prefix="inst")
    acct_form = AccountForm(prefix="acct")

    # --- START: THE FIX ---
    # Create an instance of the CSRF-only form
    csrf_form = CSRFOnlyForm()
    # --- END: THE FIX ---

    acct_form.institution_id.choices = [(i.id, i.name) for i in Institution.query.order_by(Institution.name).all()]

    submitted = request.form.get("submitted")
    if request.method == "POST":
        if submitted == "inst" and inst_form.validate_on_submit():
            inst = Institution(name=inst_form.name.data)
            db.session.add(inst)
            db.session.commit()
            flash("Institution created", "success")
            return redirect(url_for(".index") + "#institutions")
        elif submitted == "acct" and acct_form.validate_on_submit():
            acc = Account(
                institution_id=acct_form.institution_id.data,
                name=acct_form.name.data,
                type=acct_form.type.data,
            )
            db.session.add(acc)
            db.session.commit()
            flash("Account created", "success")
            return redirect(url_for(".index") + "#accounts")

    institutions = Institution.query.order_by(Institution.created_at.desc()).all()
    accounts = (
        Account.query
        .join(Institution, Account.institution_id == Institution.id)
        .order_by(Institution.name.asc(), Account.created_at.desc())
        .all()
    )

    return render_template(
        "admin/index.html",
        inst_form=inst_form,
        acct_form=acct_form,
        institutions=institutions,
        accounts=accounts,
        # --- START: THE FIX ---
        # Pass the form to the template context
        csrf_form=csrf_form
        # --- END: THE FIX ---
    )


@bp.route("/mappers/new/<int:institution_id>/<int:account_id>", methods=["GET", "POST"])
def mapper_new(institution_id, account_id):
    # This function remains unchanged
    form = MappingWizardForm()
    if form.validate_on_submit():
        schema = dict(
            date_col=form.date_col.data,
            date_fmt=form.date_fmt.data,
            desc_col=form.desc_col.data,
            amount_col=form.amount_col.data or None,
            debit_col=form.debit_col.data or None,
            credit_col=form.credit_col.data or None,
            balance_col=form.balance_col.data or None,
            exclude_pending=form.exclude_pending.data,
            # Added from a previous refactor, ensure it's here
            indicator_col=form.indicator_col.data or None
        )
        mapper = create_mapper(institution_id, account_id, schema)
        flash(f"Mapping v{mapper.version} saved", "success")
        return redirect(url_for("admin.index"))  # Redirect to main admin page

    # Pre-populate with guessed data if available (no-op for now, but good practice)
    account = Account.query.get_or_404(account_id)
    return render_template("admin/mapper_edit.html", form=form, account=account)


# --- Add the edit/toggle routes from the previous refactor ---
@bp.route("/institution/<int:institution_id>/edit", methods=["GET", "POST"])
def institution_edit(institution_id):
    institution = Institution.query.get_or_404(institution_id)
    form = InstitutionForm(obj=institution)
    if form.validate_on_submit():
        institution.name = form.name.data
        db.session.commit()
        flash("Institution updated", "success")
        return redirect(url_for(".index"))
    return render_template("admin/institution_edit.html", form=form, institution=institution)


@bp.route("/institution/<int:institution_id>/toggle_active", methods=["POST"])
def institution_toggle_active(institution_id):
    # A simple CSRF check for this POST request
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        institution = Institution.query.get_or_404(institution_id)
        institution.is_active = not institution.is_active
        db.session.commit()
        flash(f"Institution '{institution.name}' {'activated' if institution.is_active else 'deactivated'}.", "success")
    else:
        flash("CSRF validation failed.", "error")
    return redirect(url_for(".index"))


@bp.route("/account/<int:account_id>/edit", methods=["GET", "POST"])
def account_edit(account_id):
    account = Account.query.get_or_404(account_id)
    form = AccountForm(obj=account)
    form.institution_id.choices = [(i.id, i.name) for i in Institution.query.order_by(Institution.name).all()]
    if form.validate_on_submit():
        account.name = form.name.data
        account.type = form.type.data
        account.institution_id = form.institution_id.data
        db.session.commit()
        flash("Account updated", "success")
        return redirect(url_for(".index"))
    return render_template("admin/account_edit.html", form=form, account=account)


@bp.route("/account/<int:account_id>/toggle_active", methods=["POST"])
def account_toggle_active(account_id):
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        account = Account.query.get_or_404(account_id)
        account.is_active = not account.is_active
        db.session.commit()
        flash(f"Account '{account.name}' {'activated' if account.is_active else 'deactivated'}.", "success")
    else:
        flash("CSRF validation failed.", "error")
    return redirect(url_for(".index"))

@bp.route("/categories", methods=["GET", "POST"])
def categories():
    """Route for listing and creating categories."""
    form = CategoryForm()
    csrf_form = CSRFOnlyForm()
    if form.validate_on_submit():
        new_cat = Category(group=form.group.data, name=form.name.data)
        db.session.add(new_cat)
        db.session.commit()
        flash(f"Category '{new_cat.name}' created.", "success")
        return redirect(url_for(".categories"))

    all_categories = Category.query.order_by(Category.group, Category.name).all()
    return render_template("admin/categories.html", form=form, categories=all_categories, csrf_form=csrf_form)

@bp.route("/category/<int:category_id>/edit", methods=["GET", "POST"])
def category_edit(category_id):
    """Route for editing a category."""
    category = Category.query.get_or_404(category_id)
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        category.group = form.group.data
        category.name = form.name.data
        db.session.commit()
        flash(f"Category '{category.name}' updated.", "success")
        return redirect(url_for(".categories"))
    return render_template("admin/category_edit.html", form=form, category=category)


@bp.route("/category/<int:category_id>/delete", methods=["POST"])
def category_delete(category_id):
    """Route for deleting a category."""
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        category = Category.query.get_or_404(category_id)
        # Check if any transactions are using this category
        if Transaction.query.filter_by(category_id=category.id).first():
            flash(f"Cannot delete category '{category.name}' as it is in use.", "error")
        else:
            db.session.delete(category)
            db.session.commit()
            flash(f"Category '{category.name}' deleted.", "success")
    else:
        flash("CSRF validation failed.", "error")
    return redirect(url_for(".categories"))

@bp.route("/rules", methods=["GET", "POST"])
def rules():
    """Route for listing and creating rules."""
    form = RuleForm()
    # Dynamically populate the category choices
    form.category_id.choices = [
        (c.id, f"{c.group} / {c.name}") for c in Category.query.order_by(Category.group, Category.name).all()
    ]

    if form.validate_on_submit():
        new_rule = Rule(keyword=form.keyword.data, category_id=form.category_id.data)
        db.session.add(new_rule)
        try:
            db.session.commit()
            flash(f"Rule for '{new_rule.keyword}' created.", "success")
            return redirect(url_for(".rules"))
        except IntegrityError:
            db.session.rollback()
            flash(f"Error: A rule for the keyword '{form.keyword.data}' already exists.", "error")

    all_rules = Rule.query.order_by(Rule.keyword).all()
    csrf_form = CSRFOnlyForm() # For the delete buttons
    return render_template("admin/rules.html", form=form, rules=all_rules, csrf_form=csrf_form)


@bp.route("/rule/<int:rule_id>/edit", methods=["GET", "POST"])
def rule_edit(rule_id):
    """Route for editing a rule."""
    rule = Rule.query.get_or_404(rule_id)
    form = RuleForm(obj=rule)
    form.category_id.choices = [
        (c.id, f"{c.group} / {c.name}") for c in Category.query.order_by(Category.group, Category.name).all()
    ]

    if form.validate_on_submit():
        rule.keyword = form.keyword.data
        rule.category_id = form.category_id.data
        try:
            db.session.commit()
            flash(f"Rule for '{rule.keyword}' updated.", "success")
            return redirect(url_for(".rules"))
        except IntegrityError:
            db.session.rollback()
            flash(f"Error: A rule for the keyword '{form.keyword.data}' already exists.", "error")

    return render_template("admin/rule_edit.html", form=form, rule=rule)


@bp.route("/rule/<int:rule_id>/delete", methods=["POST"])
def rule_delete(rule_id):
    """Route for deleting a rule."""
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        rule = Rule.query.get_or_404(rule_id)
        db.session.delete(rule)
        db.session.commit()
        flash(f"Rule for '{rule.keyword}' deleted.", "success")
    else:
        flash("CSRF validation failed.", "error")
    return redirect(url_for(".rules"))
