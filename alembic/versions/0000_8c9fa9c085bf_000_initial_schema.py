"""
000_initial_schema

Revision ID: 8c9fa9c085bf
Revises: None
Create Date: 2025-12-31T16:05:17.176894

Original SQL file: 000_initial_schema.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8c9fa9c085bf"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 000_initial_schema.sql."""
    op.execute("""
-- Initial Schema Migration for Binomial Risk Analyst V6
-- Following CODING_RULES.md: KISS, MVP first, no over-engineering
-- August 2025 best practice: Single migration file for initial setup

-- Safe UUID generator that works without extensions
-- Tries uuid_generate_v4() if available; otherwise builds a v4-like UUID
-- Drop function first to avoid conflicts
DROP FUNCTION IF EXISTS public.generate_uuid_v4_safe();

CREATE FUNCTION public.generate_uuid_v4_safe()
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  result_uuid uuid;
BEGIN
  BEGIN
    result_uuid := uuid_generate_v4();
    RETURN result_uuid;
  EXCEPTION
    WHEN undefined_function THEN
      RETURN (
        lpad(to_hex(floor(random()*4294967295)::int),8,'0') || '-' ||
        lpad(to_hex(floor(random()*65535)::int),4,'0') || '-' ||
        '4' || substr(lpad(to_hex(floor(random()*65535)::int),4,'0'),2,3) || '-' ||
        substr('89ab', floor(random()*4)::int+1, 1) || substr(lpad(to_hex(floor(random()*65535)::int),4,'0'),2,3) || '-' ||
        lpad(to_hex(floor(random()*4294967295)::int),8,'0') || lpad(to_hex(floor(random()*4294967295)::int),8,'0')
      )::uuid;
  END;
END;
$$;

-- Try to create uuid-ossp quietly; ignore permission/errors if unavailable
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp') THEN
    BEGIN
      CREATE EXTENSION "uuid-ossp";
    EXCEPTION
      WHEN insufficient_privilege THEN
        RAISE NOTICE 'Skipping uuid-ossp extension creation (insufficient privileges)';
      WHEN undefined_file THEN
        RAISE NOTICE 'uuid-ossp extension not available on this server';
      WHEN feature_not_supported THEN
        RAISE NOTICE 'uuid-ossp extension not installed on this server';
      WHEN OTHERS THEN
        RAISE NOTICE 'Could not create uuid-ossp extension: %', SQLERRM;
    END;
  END IF;
END
$$;

-- Create users table FIRST (required by other tables)
-- This will be populated by Clerk webhooks when users sign up
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    clerk_user_id VARCHAR(255) UNIQUE,
    email VARCHAR(255),
    name VARCHAR(255),
    usage_credits INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create updated_at trigger function (DRY - reusable)
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to users table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Now run the RLS migration content (portfolios, chat_sessions, etc.)
-- These tables can now safely reference the users table
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
