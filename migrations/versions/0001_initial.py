from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "institutions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("currency", sa.Text, server_default="USD"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "mappers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id")),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("schema_json", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "imports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id")),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id")),
        sa.Column("mapper_id", sa.Integer, sa.ForeignKey("mappers.id")),
        sa.Column("original_filename", sa.Text, nullable=False),
        sa.Column("original_sha256", sa.Text, nullable=False),
        sa.Column("archived_path", sa.Text),
        sa.Column("row_count", sa.Integer),
        sa.Column("added_count", sa.Integer),
        sa.Column("duplicate_count", sa.Integer),
        sa.Column("error_count", sa.Integer),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("log_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id"), index=True),
        sa.Column("import_id", sa.Integer, sa.ForeignKey("imports.id"), index=True),
        sa.Column("txn_date", sa.Date, nullable=False, index=True),
        sa.Column("description_raw", sa.Text, nullable=False),
        sa.Column("merchant_normalized", sa.Text),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("running_balance_cents", sa.BigInteger),
        sa.Column("is_transfer", sa.Boolean, server_default=sa.text("false")),
        sa.Column("transfer_group", sa.Text),
        sa.Column("explain_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_import_sha_account", "imports", ["original_sha256", "account_id"])
    op.add_column("transactions", sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("transactions", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    # optional: index to speed up filtered reads
    op.create_index("ix_transactions_account_not_deleted", "transactions", ["account_id", "is_deleted"])

def downgrade():
    op.drop_constraint("uq_import_sha_account", "imports", type_="unique")
    op.drop_index("ix_transactions_account_not_deleted", table_name="transactions")
    op.drop_column("transactions", "deleted_at")
    op.drop_column("transactions", "is_deleted")
    for tbl in ("transactions", "imports", "mappers", "accounts", "institutions", "users"):
        op.drop_table(tbl)
