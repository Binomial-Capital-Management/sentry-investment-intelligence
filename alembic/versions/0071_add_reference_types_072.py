"""
072_add_reference_types

Revision ID: add_ref_types_001
Revises: memory_chunks_001
Create Date: 2026-01-22

Add 'dataset' and 'web' to reference_type CHECK constraint for memory notes.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "add_ref_types_001"
down_revision = "memory_chunks_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add 'dataset' and 'web' to reference_type CHECK constraint."""
    op.execute("""
-- Drop the old CHECK constraint
ALTER TABLE chat_memory_notes 
    DROP CONSTRAINT IF EXISTS chat_memory_notes_reference_type_check;

-- Add new CHECK constraint with additional types
ALTER TABLE chat_memory_notes 
    ADD CONSTRAINT chat_memory_notes_reference_type_check 
    CHECK (reference_type IN ('text', 'message_excerpt', 'file', 'portfolio', 'chart', 'table', 'dataset', 'web'));

-- Update comment
COMMENT ON COLUMN chat_memory_notes.reference_type IS 'Type of content: text, message_excerpt, file, portfolio, chart, table, dataset, or web';
""")


def downgrade() -> None:
    """Revert to original reference_type CHECK constraint."""
    op.execute("""
-- Drop the new CHECK constraint
ALTER TABLE chat_memory_notes 
    DROP CONSTRAINT IF EXISTS chat_memory_notes_reference_type_check;

-- Restore original CHECK constraint
ALTER TABLE chat_memory_notes 
    ADD CONSTRAINT chat_memory_notes_reference_type_check 
    CHECK (reference_type IN ('text', 'message_excerpt', 'file', 'portfolio', 'chart', 'table'));

-- Restore original comment
COMMENT ON COLUMN chat_memory_notes.reference_type IS 'Type of content: text, message_excerpt, file, portfolio, chart, or table';
""")

