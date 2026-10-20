"""merge_heads_078

Revision ID: 911fd1e4ff70
Revises: transcript_ref_001, workspace_snapshot_001, archived_at_canvas_001
Create Date: 2026-04-24 13:41:00.555359

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '911fd1e4ff70'
down_revision: Union[str, None] = ('transcript_ref_001', 'workspace_snapshot_001', 'archived_at_canvas_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
