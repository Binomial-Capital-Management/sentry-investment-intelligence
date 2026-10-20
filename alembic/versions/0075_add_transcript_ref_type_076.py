"""Add transcript to reference_type CHECK constraint

Revision ID: transcript_ref_001
Revises: sec_filing_ref_001
Create Date: 2026-02-04

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'transcript_ref_001'
down_revision = 'sec_filing_ref_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add transcript as valid reference_type."""
    op.execute("""
-- Drop existing constraint
ALTER TABLE chat_memory_notes 
    DROP CONSTRAINT IF EXISTS chat_memory_notes_reference_type_check;

-- Add new constraint with transcript included
ALTER TABLE chat_memory_notes 
    ADD CONSTRAINT chat_memory_notes_reference_type_check 
    CHECK (reference_type IN ('text', 'message_excerpt', 'file', 'portfolio', 'chart', 'table', 'dataset', 'web', 'sec_filing', 'transcript'));

-- Update comment
COMMENT ON COLUMN chat_memory_notes.reference_type IS 'Type of content: text, message_excerpt, file, portfolio, chart, table, dataset, web, sec_filing, or transcript';
""")


def downgrade() -> None:
    """Remove transcript from the reference_type CHECK constraint."""
    op.execute("""
-- Drop constraint with transcript
ALTER TABLE chat_memory_notes 
    DROP CONSTRAINT IF EXISTS chat_memory_notes_reference_type_check;

-- Restore previous constraint
ALTER TABLE chat_memory_notes 
    ADD CONSTRAINT chat_memory_notes_reference_type_check 
    CHECK (reference_type IN ('text', 'message_excerpt', 'file', 'portfolio', 'chart', 'table', 'dataset', 'web', 'sec_filing'));

-- Restore comment
COMMENT ON COLUMN chat_memory_notes.reference_type IS 'Type of content: text, message_excerpt, file, portfolio, chart, table, dataset, web, or sec_filing';
""")
