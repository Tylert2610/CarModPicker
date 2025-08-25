"""rename_voting_and_reporting_tables

Revision ID: 8014088c17c0
Revises: d27daf10d16a
Create Date: 2025-08-24 16:20:18.177839

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8014088c17c0"
down_revision: Union[str, None] = "d27daf10d16a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename part_votes table to global_part_votes
    op.rename_table("part_votes", "global_part_votes")

    # Rename part_reports table to global_part_reports
    op.rename_table("part_reports", "global_part_reports")


def downgrade() -> None:
    """Downgrade schema."""
    # Rename global_part_reports table back to part_reports
    op.rename_table("global_part_reports", "part_reports")

    # Rename global_part_votes table back to part_votes
    op.rename_table("global_part_votes", "part_votes")
