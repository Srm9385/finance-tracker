
from ..services.mapping import create_mapper
from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..extensions import db
from ..models import Institution, Account
from ..forms import InstitutionForm, AccountForm, MappingWizardForm

bp = Blueprint("admin", __name__)

@bp.route("/", methods=["GET", "POST"])
def index():
    inst_form = InstitutionForm(prefix="inst")
    acct_form = AccountForm(prefix="acct")
    acct_form.institution_id.choices = [(i.id, i.name) for i in Institution.query.order_by(Institution.name).all()]

    # Determine which form was submitted (by submit button name)
    submitted = request.form.get("submitted")

    if request.method == "POST":
        if submitted == "inst":
            if inst_form.validate_on_submit():
                inst = Institution(name=inst_form.name.data)
                db.session.add(inst)
                db.session.commit()
                flash("Institution created", "success")
                return redirect(url_for(".index") + "#institutions")
            else:
                flash("Please fix the Institution form errors.", "error")

        elif submitted == "acct":
            # Rebuild choices because validate_on_submit runs validators on selected value
            acct_form.institution_id.choices = [(i.id, i.name) for i in Institution.query.order_by(Institution.name).all()]
            if acct_form.validate_on_submit():
                acc = Account(
                    institution_id=acct_form.institution_id.data,
                    name=acct_form.name.data,
                    type=acct_form.type.data,
                )
                db.session.add(acc)
                db.session.commit()
                flash("Account created", "success")
                return redirect(url_for(".index") + "#accounts")
            else:
                flash("Please fix the Account form errors.", "error")

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
    )


@bp.route("/mappers/new/<int:institution_id>/<int:account_id>", methods=["GET","POST"])
def mapper_new(institution_id, account_id):
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
        )
        mapper = create_mapper(institution_id, account_id, schema)
        flash(f"Mapping v{mapper.version} saved", "success")
        return redirect(url_for(".accounts"))
    return render_template("admin/mapper_edit.html", form=form, institution_id=institution_id, account_id=account_id)
