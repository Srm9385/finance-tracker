from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..services.mapping import create_mapper, latest_mapper_for
from ..models import (
    Institution,
    Account,
    Category,
    Transaction,
    Rule,
    TransferKeyword,
    RefundKeyword,
    Mapper,
    Import,
)
from ..forms import (InstitutionForm, AccountForm, MappingWizardForm,
                     CSRFOnlyForm, CategoryForm, RuleForm, TransferKeywordForm, RefundKeywordForm)
import json

bp = Blueprint("admin", __name__)


def _delete_account_with_dependencies(account):
    """Remove an account and clean up related records to avoid FK issues."""
    transactions_deleted = Transaction.query.filter(
        Transaction.account_id == account.id
    ).delete(synchronize_session=False)
    imports_deleted = Import.query.filter(
        Import.account_id == account.id
    ).delete(synchronize_session=False)
    mappers_deleted = Mapper.query.filter(
        Mapper.account_id == account.id
    ).delete(synchronize_session=False)
    db.session.delete(account)
    return {
        "transactions": transactions_deleted,
        "imports": imports_deleted,
        "mappers": mappers_deleted,
    }


@bp.route("/", methods=["GET", "POST"])
def index():
    inst_form = InstitutionForm(prefix="inst")
    acct_form = AccountForm(prefix="acct")
    csrf_form = CSRFOnlyForm()

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
        csrf_form=csrf_form
    )


@bp.route("/mappers/edit/<int:institution_id>/<int:account_id>", methods=["GET", "POST"])
def mapper_edit(institution_id, account_id):
    """
    Handles both creating a new mapper and editing the latest existing one.
    A new version is always created upon saving.
    """
    account = Account.query.get_or_404(account_id)
    institution = Institution.query.get_or_404(institution_id)
    latest_mapper = latest_mapper_for(account_id, institution_id)

    form = MappingWizardForm()

    if form.validate_on_submit():
        schema = {
            "date_col": form.date_col.data, "date_fmt": form.date_fmt.data,
            "desc_col": form.desc_col.data, "amount_col": form.amount_col.data or None,
            "debit_col": form.debit_col.data or None, "credit_col": form.credit_col.data or None,
            "balance_col": form.balance_col.data or None, "exclude_pending": form.exclude_pending.data,
            "indicator_col": form.indicator_col.data or None
        }
        # This always creates a new version, preserving history
        mapper = create_mapper(institution_id, account_id, schema)
        flash(f"Mapping v{mapper.version} saved.", "success")
        return redirect(url_for("admin.index"))

    # On GET request, populate form with the latest mapper's data if it exists
    if not form.is_submitted() and latest_mapper:
        form = MappingWizardForm(data=latest_mapper.schema_json)

    return render_template("admin/mapper_edit.html", form=form, account=account, institution=institution)

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
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        institution = Institution.query.get_or_404(institution_id)
        institution.is_active = not institution.is_active
        db.session.commit()
        flash(f"Institution '{institution.name}' {'activated' if institution.is_active else 'deactivated'}.", "success")
    else:
        flash("CSRF validation failed.", "error")
    return redirect(url_for(".index"))


@bp.route("/institution/<int:institution_id>/delete", methods=["POST"])
def institution_delete(institution_id):
    form = CSRFOnlyForm()
    anchor = url_for(".index") + "#institutions"
    if not form.validate_on_submit():
        flash("CSRF validation failed.", "error")
        return redirect(anchor)

    institution = Institution.query.get_or_404(institution_id)
    institution_name = institution.name

    try:
        total_accounts = 0
        total_transactions = 0
        total_imports = 0
        total_mappers = 0

        for account in list(institution.accounts):
            stats = _delete_account_with_dependencies(account)
            total_accounts += 1
            total_transactions += stats["transactions"]
            total_imports += stats["imports"]
            total_mappers += stats["mappers"]

        # Clean up institution-level artifacts that may not be tied to a specific account.
        inst_imports_deleted = Import.query.filter(
            Import.institution_id == institution.id
        ).delete(synchronize_session=False)
        inst_mappers_deleted = Mapper.query.filter(
            Mapper.institution_id == institution.id,
            Mapper.account_id.is_(None),
        ).delete(synchronize_session=False)

        total_imports += inst_imports_deleted
        total_mappers += inst_mappers_deleted

        db.session.delete(institution)
        db.session.commit()
        flash(
            f"Institution '{institution_name}' deleted "
            f"(removed {total_accounts} accounts, {total_transactions} transactions, "
            f"{total_imports} imports, {total_mappers} mappers).",
            "success",
        )
    except IntegrityError:
        db.session.rollback()
        flash(
            f"Failed to delete institution '{institution_name}'. "
            "Please ensure related data is removed and try again.",
            "error",
        )

    return redirect(anchor)


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


@bp.route("/account/<int:account_id>/delete", methods=["POST"])
def account_delete(account_id):
    form = CSRFOnlyForm()
    anchor = url_for(".index") + "#accounts"
    if not form.validate_on_submit():
        flash("CSRF validation failed.", "error")
        return redirect(anchor)

    account = Account.query.get_or_404(account_id)
    account_name = account.name

    try:
        stats = _delete_account_with_dependencies(account)
        db.session.commit()
        flash(
            f"Account '{account_name}' deleted "
            f"(removed {stats['transactions']} transactions, "
            f"{stats['imports']} imports, {stats['mappers']} mappers).",
            "success",
        )
    except IntegrityError:
        db.session.rollback()
        flash(
            f"Failed to delete account '{account_name}'. "
            "Please ensure related data is removed and try again.",
            "error",
        )

    return redirect(anchor)

@bp.route("/categories", methods=["GET", "POST"])
def categories():
    """Route for listing, creating, and exporting categories."""
    form = CategoryForm()
    csrf_form = CSRFOnlyForm()
    if form.validate_on_submit():
        new_cat = Category(group=form.group.data, name=form.name.data)
        db.session.add(new_cat)
        db.session.commit()
        flash(f"Category '{new_cat.name}' created.", "success")
        return redirect(url_for(".categories"))

    all_categories = Category.query.order_by(Category.group, Category.name).all()

    # --- START MODIFICATION ---
    # Generate the JSON string for export
    categories_export_list = [
        {'group': c.group, 'name': c.name} for c in all_categories
    ]
    # Use single quotes for the outer JSON string to work well in a .env file
    categories_json_string = f"DEFAULT_CATEGORIES_JSON='{json.dumps(categories_export_list)}'"
    # --- END MODIFICATION ---

    return render_template(
        "admin/categories.html",
        form=form,
        categories=all_categories,
        csrf_form=csrf_form,
        categories_json_string=categories_json_string # Pass the string to the template
    )


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
    """Route for listing, creating, and exporting rules."""
    form = RuleForm()
    form.category_id.choices = [
        (c.id, f"{c.name} / {c.group}") for c in Category.query.order_by(Category.name, Category.group).all()
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
    csrf_form = CSRFOnlyForm()

    # Generate the JSON string for export
    rules_export_dict = {}
    for rule in all_rules:
        category_name = rule.category.name
        if category_name not in rules_export_dict:
            rules_export_dict[category_name] = []
        rules_export_dict[category_name].append(rule.keyword)

    rules_json_string = f"DEFAULT_RULES_JSON='{json.dumps(rules_export_dict)}'"

    return render_template(
        "admin/rules.html",
        form=form,
        rules=all_rules,
        csrf_form=csrf_form,
        rules_json_string=rules_json_string  # Pass the string to the template
    )

@bp.route("/rule/<int:rule_id>/edit", methods=["GET", "POST"])
def rule_edit(rule_id):
    """Route for editing a rule."""
    rule = Rule.query.get_or_404(rule_id)
    form = RuleForm(obj=rule)
    form.category_id.choices = [
        (c.id, f"{c.name} / {c.group}") for c in Category.query.order_by(Category.name, Category.group).all()
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

@bp.route("/transfer-keywords", methods=["GET", "POST"])
def transfer_keywords():
    """Route for listing and creating transfer keywords."""
    form = TransferKeywordForm()
    csrf_form = CSRFOnlyForm()
    if form.validate_on_submit():
        new_keyword = TransferKeyword(keyword=form.keyword.data)
        db.session.add(new_keyword)
        try:
            db.session.commit()
            flash(f"Transfer keyword '{new_keyword.keyword}' created.", "success")
            return redirect(url_for(".transfer_keywords"))
        except IntegrityError:
            db.session.rollback()
            flash(f"Error: The keyword '{form.keyword.data}' already exists.", "error")

    all_keywords = TransferKeyword.query.order_by(TransferKeyword.keyword).all()
    return render_template(
        "admin/transfer_keywords.html",
        form=form,
        keywords=all_keywords,
        csrf_form=csrf_form
    )


@bp.route("/transfer-keyword/<int:keyword_id>/delete", methods=["POST"])
def transfer_keyword_delete(keyword_id):
    """Route for deleting a transfer keyword."""
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        keyword = TransferKeyword.query.get_or_404(keyword_id)
        db.session.delete(keyword)
        db.session.commit()
        flash(f"Transfer keyword '{keyword.keyword}' deleted.", "success")
    else:
        flash("CSRF validation failed.", "error")
    return redirect(url_for(".transfer_keywords"))

@bp.route("/refund-keywords", methods=["GET", "POST"])
def refund_keywords():
    """Route for listing and creating refund keywords."""
    form = RefundKeywordForm()
    csrf_form = CSRFOnlyForm()
    if form.validate_on_submit():
        new_keyword = RefundKeyword(keyword=form.keyword.data)
        db.session.add(new_keyword)
        try:
            db.session.commit()
            flash(f"Refund keyword '{new_keyword.keyword}' created.", "success")
            return redirect(url_for(".refund_keywords"))
        except IntegrityError:
            db.session.rollback()
            flash(f"Error: The keyword '{form.keyword.data}' already exists.", "error")

    all_keywords = RefundKeyword.query.order_by(RefundKeyword.keyword).all()
    return render_template(
        "admin/refund_keywords.html",
        form=form,
        keywords=all_keywords,
        csrf_form=csrf_form
    )


@bp.route("/refund-keyword/<int:keyword_id>/delete", methods=["POST"])
def refund_keyword_delete(keyword_id):
    """Route for deleting a refund keyword."""
    form = CSRFOnlyForm()
    if form.validate_on_submit():
        keyword = RefundKeyword.query.get_or_404(keyword_id)
        db.session.delete(keyword)
        db.session.commit()
        flash(f"Refund keyword '{keyword.keyword}' deleted.", "success")
    else:
        flash("CSRF validation failed.", "error")
    return redirect(url_for(".refund_keywords"))
