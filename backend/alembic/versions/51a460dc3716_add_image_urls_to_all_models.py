"""add_image_urls_to_all_models

Revision ID: 51a460dc3716
Revises: 3bf7d64ac74d
Create Date: 2025-06-11 21:40:58.849958

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "51a460dc3716"
down_revision: Union[str, None] = "3bf7d64ac74d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
