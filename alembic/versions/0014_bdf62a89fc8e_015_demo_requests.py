"""
015_demo_requests

Revision ID: bdf62a89fc8e
Revises: b69b405df11a
Create Date: 2025-12-31T16:05:17.185167

Original SQL file: 015_demo_requests.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bdf62a89fc8e"
down_revision = "b69b405df11a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 015_demo_requests.sql."""
    op.execute("""
-- Migration: Create demo_requests table for contact form submissions
-- Date: 2025-09-05
-- Purpose: Support contact form backend with optional database storage

-- Create demo_requests table
CREATE TABLE IF NOT EXISTS demo_requests (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255) NOT NULL,
    company VARCHAR(200),
    title VARCHAR(200),
    message TEXT NOT NULL CHECK (length(message) <= 5000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_demo_requests_email ON demo_requests(email);
CREATE INDEX IF NOT EXISTS idx_demo_requests_created_at ON demo_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_demo_requests_company ON demo_requests(company) WHERE company IS NOT NULL;

-- Enable Row Level Security (RLS)
ALTER TABLE demo_requests ENABLE ROW LEVEL SECURITY;

-- Create RLS policy - demo requests are public submissions but admin-readable
-- Since these are contact form submissions, they don't belong to specific users
-- We'll create a policy that allows:
-- 1. Anyone to insert (for contact form submissions)
-- 2. Only admin users to read (for review purposes)

-- Policy for insertions - allow public contact form submissions
CREATE POLICY demo_requests_insert_policy ON demo_requests
    FOR INSERT
    WITH CHECK (true);

-- Policy for reading - REMOVED for CODING_RULES.md compliance
-- Contact form submissions are INSERT-only (public submissions)
-- Admin access should be handled via separate secure query methods
-- No hardcoded credentials allowed per CODING_RULES.md

-- Add trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_demo_requests_updated_at
    BEFORE UPDATE ON demo_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE demo_requests IS 'Contact form submissions from the website';
COMMENT ON COLUMN demo_requests.name IS 'Full name of the person submitting the form';
COMMENT ON COLUMN demo_requests.email IS 'Email address for follow-up contact';
COMMENT ON COLUMN demo_requests.company IS 'Optional company name';
COMMENT ON COLUMN demo_requests.title IS 'Optional job title';
COMMENT ON COLUMN demo_requests.message IS 'Message content (max 5000 characters)';
COMMENT ON COLUMN demo_requests.created_at IS 'Timestamp when the request was submitted';
COMMENT ON COLUMN demo_requests.updated_at IS 'Timestamp when the record was last updated';
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
