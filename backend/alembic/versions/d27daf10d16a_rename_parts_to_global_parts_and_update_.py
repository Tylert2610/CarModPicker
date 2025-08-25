"""rename_parts_to_global_parts_and_update_references

Revision ID: d27daf10d16a
Revises: 65b48b62e680
Create Date: 2025-08-24 16:13:18.177839

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d27daf10d16a"
down_revision: Union[str, None] = "65b48b62e680"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename the parts table to global_parts
    op.rename_table("parts", "global_parts")

    # Update foreign key references in build_list_parts table
    op.drop_constraint(
        "build_list_parts_part_id_fkey", "build_list_parts", type_="foreignkey"
    )
    op.create_foreign_key(
        "build_list_parts_global_part_id_fkey",
        "build_list_parts",
        "global_parts",
        ["part_id"],
        ["id"],
    )
    # Rename the column from part_id to global_part_id
    op.alter_column("build_list_parts", "part_id", new_column_name="global_part_id")

    # Update foreign key references in part_votes table
    op.drop_constraint("part_votes_part_id_fkey", "part_votes", type_="foreignkey")
    op.create_foreign_key(
        "part_votes_global_part_id_fkey",
        "part_votes",
        "global_parts",
        ["part_id"],
        ["id"],
    )
    # Rename the column from part_id to global_part_id
    op.alter_column("part_votes", "part_id", new_column_name="global_part_id")

    # Update foreign key references in part_reports table
    op.drop_constraint("part_reports_part_id_fkey", "part_reports", type_="foreignkey")
    op.create_foreign_key(
        "part_reports_global_part_id_fkey",
        "part_reports",
        "global_parts",
        ["part_id"],
        ["id"],
    )
    # Rename the column from part_id to global_part_id
    op.alter_column("part_reports", "part_id", new_column_name="global_part_id")

    # Update unique constraint in part_votes table
    op.drop_constraint("unique_user_part_vote", "part_votes", type_="unique")
    op.create_unique_constraint(
        "unique_user_global_part_vote", "part_votes", ["user_id", "global_part_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert unique constraint in part_votes table
    op.drop_constraint("unique_user_global_part_vote", "part_votes", type_="unique")
    op.create_unique_constraint(
        "unique_user_part_vote", "part_votes", ["user_id", "part_id"]
    )

    # Revert foreign key references in part_reports table
    op.alter_column("part_reports", "global_part_id", new_column_name="part_id")
    op.drop_constraint(
        "part_reports_global_part_id_fkey", "part_reports", type_="foreignkey"
    )
    op.create_foreign_key(
        "part_reports_part_id_fkey", "part_reports", "parts", ["part_id"], ["id"]
    )

    # Revert foreign key references in part_votes table
    op.alter_column("part_votes", "global_part_id", new_column_name="part_id")
    op.drop_constraint(
        "part_votes_global_part_id_fkey", "part_votes", type_="foreignkey"
    )
    op.create_foreign_key(
        "part_votes_part_id_fkey", "part_votes", "parts", ["part_id"], ["id"]
    )

    # Revert foreign key references in build_list_parts table
    op.alter_column("build_list_parts", "global_part_id", new_column_name="part_id")
    op.drop_constraint(
        "build_list_parts_global_part_id_fkey", "build_list_parts", type_="foreignkey"
    )
    op.create_foreign_key(
        "build_list_parts_part_id_fkey",
        "build_list_parts",
        "parts",
        ["part_id"],
        ["id"],
    )

    # Rename the global_parts table back to parts
    op.rename_table("global_parts", "parts")
