"""fix_null_timestamps_in_build_lists_and_parts

Revision ID: 7243343ef978
Revises: 1b17f9e4db9b
Create Date: 2025-08-27 20:44:28.129280

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7243343ef978"
down_revision: Union[str, None] = "1b17f9e4db9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fix NULL timestamp values in build_lists table
    op.execute("UPDATE build_lists SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE build_lists SET updated_at = NOW() WHERE updated_at IS NULL")

    # Check if parts table exists before trying to update it
    # This migration might run before the parts table is created
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "parts" in tables:
        # Fix NULL timestamp values in parts table
        op.execute("UPDATE parts SET created_at = NOW() WHERE created_at IS NULL")
        op.execute("UPDATE parts SET updated_at = NOW() WHERE updated_at IS NULL")

        # Fix NULL values for other required fields in parts table
        op.execute("UPDATE parts SET is_verified = false WHERE is_verified IS NULL")
        op.execute("UPDATE parts SET source = 'user_created' WHERE source IS NULL")
        op.execute("UPDATE parts SET edit_count = 0 WHERE edit_count IS NULL")

    elif "global_parts" in tables:
        # Fix NULL timestamp values in global_parts table
        op.execute(
            "UPDATE global_parts SET created_at = NOW() WHERE created_at IS NULL"
        )
        op.execute(
            "UPDATE global_parts SET updated_at = NOW() WHERE updated_at IS NULL"
        )

        # Fix NULL values for other required fields in global_parts table
        op.execute(
            "UPDATE global_parts SET is_verified = false WHERE is_verified IS NULL"
        )
        op.execute(
            "UPDATE global_parts SET source = 'user_created' WHERE source IS NULL"
        )
        op.execute("UPDATE global_parts SET edit_count = 0 WHERE edit_count IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    # This migration only fixes data, no schema changes to revert
    pass
