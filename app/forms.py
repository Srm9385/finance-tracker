from wtforms import SubmitField
from wtforms import StringField, SelectField, FileField, BooleanField, TextAreaField, SubmitField, DateField, DecimalField
from wtforms.validators import DataRequired, Optional
from flask_wtf import FlaskForm

ACCOUNT_TYPES = [
    ("checking","Checking"),
    ("savings","Savings"),
    ("credit_card","Credit Card"),
    ("loan","Loan"),
    ("retirement","Retirement"),
]

class InstitutionForm(FlaskForm):
    name = StringField("Institution Name", validators=[DataRequired()])
    submit = SubmitField("Save")

class AccountForm(FlaskForm):
    institution_id = SelectField("Institution", coerce=int, validators=[DataRequired()])
    name = StringField("Account Name", validators=[DataRequired()])
    type = SelectField("Type", choices=ACCOUNT_TYPES, validators=[DataRequired()])
    submit = SubmitField("Save")

class MappingWizardForm(FlaskForm):
    date_col = StringField("Date Column", validators=[DataRequired()])
    date_fmt = StringField("Date Format (e.g. %m/%d/%Y)", validators=[DataRequired()])
    desc_col = StringField("Description Column", validators=[DataRequired()])

    # NEW: optional indicator column (e.g. "Credit Debit Indicator")
    indicator_col = StringField("Indicator Column (e.g. Credit/Debit)", render_kw={"placeholder": "Credit Debit Indicator"})

    amount_col = StringField("Amount Column (signed or net)")
    debit_col = StringField("Debit Column (optional)")
    credit_col = StringField("Credit Column (optional)")
    balance_col = StringField("Running Balance Column (optional)")
    exclude_pending = BooleanField("Exclude Pending Rows")
    submit = SubmitField("Save Mapping")


class ImportUploadForm(FlaskForm):
    institution_id = SelectField("Institution", coerce=int, validators=[DataRequired()])
    account_id = SelectField("Account", coerce=int, validators=[DataRequired()])

    # Use a sentinel value -1 to represent "no mapper / guess from CSV".
    # Using coerce=int with an empty string causes a ValueError before validators run.
    mapper_id = SelectField(
        "Mapping Version",
        coerce=int,
        default=-1,            # sentinel
    )

    file = FileField("CSV File", validators=[DataRequired()])
    submit = SubmitField("Upload")

class ReviewDecisionForm(FlaskForm):
    decisions_json = TextAreaField("Decisions JSON")
    submit = SubmitField("Commit Import")


class CSRFOnlyForm(FlaskForm):
    submit = SubmitField("Submit")

class AICategorizeForm(FlaskForm):
    institution_id = SelectField("Institution", validators=[Optional()])
    account_id = SelectField("Account", validators=[Optional()])
    scope = StringField("Scope", default="uncategorized")
    submit = SubmitField("Get Suggestions")

class CategoryForm(FlaskForm):
    group = StringField("Category Group", validators=[DataRequired()])
    name = StringField("Category Name", validators=[DataRequired()])
    submit = SubmitField("Save Category")

class ManualTransactionForm(FlaskForm):
    txn_date = DateField("Date", validators=[DataRequired()], format='%Y-%m-%d')
    description_raw = StringField("Description", validators=[DataRequired()], default="Balance Adjustment")
    amount = DecimalField("Amount", validators=[DataRequired()], places=2)
    submit = SubmitField("Add Manual Transaction")

class RuleForm(FlaskForm):
    """Form for creating and editing categorization rules."""
    keyword = StringField("Keyword", validators=[DataRequired()],
                          render_kw={"placeholder": "e.g., AMAZON"})
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Save Rule")

class TransferKeywordForm(FlaskForm):
    """Form for adding a new transfer keyword."""
    keyword = StringField("Keyword", validators=[DataRequired()],
                          render_kw={"placeholder": "e.g., VENMO"})
    submit = SubmitField("Add Keyword")

class RefundKeywordForm(FlaskForm):
    """Form for adding a new refund keyword."""
    keyword = StringField("Keyword", validators=[DataRequired()],
                          render_kw={"placeholder": "e.g., REFUND"})
    submit = SubmitField("Add Keyword")

class RestoreForm(FlaskForm):
    """Form for uploading a database backup file."""
    # --- START MODIFICATION ---
    backup_file = FileField("Backup Archive (.tar.gz)", validators=[DataRequired()])    # --- END MODIFICATION ---
    submit = SubmitField("Restore from Backup")

class RefundFinderForm(FlaskForm):
    """Form for finding potential refunds in an account."""
    account_id = SelectField("Account", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Find Refunds")