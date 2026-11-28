"""enable pgvector extension

Revision ID: 0001
Revises: 
Create Date: 2026-11-28 10:44:41.049783

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Needed from Phase 4 (document_chunks.embedding). Enabling it now means every
    # environment gets it from migrations, not from a container-specific init script.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
