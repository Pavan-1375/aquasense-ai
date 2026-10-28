"""Baseline the existing AquaSense schema without deleting data.

The project historically bootstrapped local SQLite with SQLAlchemy metadata.
This first Alembic revision preserves that upgrade path by applying the same
additive metadata operation once, then records the database revision for future
per-table migrations.
"""

from alembic import op

from app.db import Base
from app import models  # noqa: F401


revision = "20261027_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # The baseline is intentionally non-destructive. Future revisions should
    # provide explicit reversible operations for individual schema changes.
    pass
