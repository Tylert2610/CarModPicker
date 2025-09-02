"""add_timestamp_fields_to_cars_and_users

Revision ID: 5cc5c4be1626
Revises: c9985b835f5a
Create Date: 2025-09-01 16:49:26.985078

"""

from typing import Sequence, Union
from datetime import datetime, UTC

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5cc5c4be1626"
down_revision: Union[str, None] = "c9985b835f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add timestamp fields to cars table
    op.add_column("cars", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("cars", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Set default values for existing records
    current_time = datetime.now(UTC)
    op.execute(
        f"UPDATE cars SET created_at = '{current_time}', updated_at = '{current_time}'"
    )

    # Make columns non-nullable after setting defaults
    op.alter_column("cars", "created_at", nullable=False)
    op.alter_column("cars", "updated_at", nullable=False)

    # Add timestamp fields to users table
    op.add_column("users", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Set default values for existing records
    op.execute(
        f"UPDATE users SET created_at = '{current_time}', updated_at = '{current_time}'"
    )

    # Make columns non-nullable after setting defaults
    op.alter_column("users", "created_at", nullable=False)
    op.alter_column("users", "updated_at", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove timestamp fields from cars table
    op.drop_column("cars", "updated_at")
    op.drop_column("cars", "created_at")

    # Remove timestamp fields from users table
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
