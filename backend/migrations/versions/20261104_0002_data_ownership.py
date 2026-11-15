"""Add owner boundaries to location, measurement, quality and alert records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261104_0002"
down_revision = "20261027_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    for table in ("stations", "measurements", "quality_observations", "alerts"):
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "owner_id" not in columns:
            op.add_column(table, sa.Column("owner_id", sa.String(length=36), nullable=True))
        indexes = {index["name"] for index in inspector.get_indexes(table)}
        if f"ix_{table}_owner_id" not in indexes:
            op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])


def downgrade() -> None:
    for table in ("alerts", "quality_observations", "measurements", "stations"):
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_column(table, "owner_id")
