from alembic import op
import sqlalchemy as sa

revision = "0002_soft_delete"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("transactions", sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("transactions", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    # optional: index to speed up filtered reads
    op.create_index("ix_transactions_account_not_deleted", "transactions", ["account_id", "is_deleted"])

def downgrade():
    op.drop_index("ix_transactions_account_not_deleted", table_name="transactions")
    op.drop_column("transactions", "deleted_at")
    op.drop_column("transactions", "is_deleted")
