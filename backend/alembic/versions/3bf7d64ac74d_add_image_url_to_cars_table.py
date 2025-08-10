"""add_image_url_to_cars_table

Revision ID: 3bf7d64ac74d
Revises: e7568d04aab3
Create Date: 2025-06-11 21:35:07.733668

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3bf7d64ac74d"
down_revision: Union[str, None] = "e7568d04aab3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
