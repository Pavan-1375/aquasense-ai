"""Allow account deletion to anonymize reviewer references."""

from alembic import op
import sqlalchemy as sa


revision = "20261119_0003"
down_revision = "20261104_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("submission_reviews") as batch_op:
        batch_op.alter_column("reviewer_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("submission_reviews") as batch_op:
        batch_op.alter_column("reviewer_id", existing_type=sa.String(length=36), nullable=False)
