"""add_car_and_build_list_votes_and_reports

Revision ID: 25_car_votes_reports
Revises: 7243343ef978
Create Date: 2025-01-27 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "25_car_votes_reports"
down_revision: Union[str, None] = "7243343ef978"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create car_votes table
    op.create_table(
        "car_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("car_id", sa.Integer(), nullable=False),
        sa.Column("vote_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["car_id"],
            ["cars.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "car_id", name="unique_user_car_vote"),
    )
    op.create_index(op.f("ix_car_votes_id"), "car_votes", ["id"], unique=False)

    # Create car_reports table
    op.create_table(
        "car_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("car_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("admin_notes", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["car_id"],
            ["cars.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_car_reports_id"), "car_reports", ["id"], unique=False)

    # Create build_list_votes table
    op.create_table(
        "build_list_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("build_list_id", sa.Integer(), nullable=False),
        sa.Column("vote_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["build_list_id"],
            ["build_lists.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "build_list_id", name="unique_user_build_list_vote"
        ),
    )
    op.create_index(
        op.f("ix_build_list_votes_id"), "build_list_votes", ["id"], unique=False
    )

    # Create build_list_reports table
    op.create_table(
        "build_list_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("build_list_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("admin_notes", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["build_list_id"],
            ["build_lists.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_build_list_reports_id"), "build_list_reports", ["id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop build_list_reports table
    op.drop_index(op.f("ix_build_list_reports_id"), table_name="build_list_reports")
    op.drop_table("build_list_reports")

    # Drop build_list_votes table
    op.drop_index(op.f("ix_build_list_votes_id"), table_name="build_list_votes")
    op.drop_table("build_list_votes")

    # Drop car_reports table
    op.drop_index(op.f("ix_car_reports_id"), table_name="car_reports")
    op.drop_table("car_reports")

    # Drop car_votes table
    op.drop_index(op.f("ix_car_votes_id"), table_name="car_votes")
    op.drop_table("car_votes")
