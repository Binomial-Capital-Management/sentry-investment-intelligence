"""Add sec_filing to reference_type CHECK constraint.

Revision ID: sec_filing_ref_001
Revises: institution_universe_001
Create Date: 2026-02-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'sec_filing_ref_001'
down_revision: Union[str, None] = 'institution_universe_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sec_filing to the reference_type CHECK constraint."""
    op.execute("""
-- Drop existing constraint
ALTER TABLE chat_memory_notes 
    DROP CONSTRAINT IF EXISTS chat_memory_notes_reference_type_check;

-- Add new constraint with sec_filing and transcript included
ALTER TABLE chat_memory_notes 
    ADD CONSTRAINT chat_memory_notes_reference_type_check 
    CHECK (reference_type IN ('text', 'message_excerpt', 'file', 'portfolio', 'chart', 'table', 'dataset', 'web', 'sec_filing', 'transcript'));

-- Update comment
COMMENT ON COLUMN chat_memory_notes.reference_type IS 'Type of content: text, message_excerpt, file, portfolio, chart, table, dataset, web, or sec_filing';
""")


def downgrade() -> None:
    """Remove sec_filing from the reference_type CHECK constraint."""
    op.execute("""
-- Drop constraint with sec_filing
ALTER TABLE chat_memory_notes 
    DROP CONSTRAINT IF EXISTS chat_memory_notes_reference_type_check;

-- Restore previous constraint
ALTER TABLE chat_memory_notes 
    ADD CONSTRAINT chat_memory_notes_reference_type_check 
    CHECK (reference_type IN ('text', 'message_excerpt', 'file', 'portfolio', 'chart', 'table', 'dataset', 'web'));

-- Restore comment
COMMENT ON COLUMN chat_memory_notes.reference_type IS 'Type of content: text, message_excerpt, file, portfolio, chart, table, dataset, or web';
""")
