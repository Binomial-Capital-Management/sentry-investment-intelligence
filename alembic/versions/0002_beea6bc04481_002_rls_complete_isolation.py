"""
002_rls_complete_isolation

Revision ID: beea6bc04481
Revises: 26bdde7fd98a
Create Date: 2025-12-31T16:05:17.177902

Original SQL file: 002_rls_complete_isolation.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "beea6bc04481"
down_revision = "26bdde7fd98a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 002_rls_complete_isolation.sql."""
    op.execute("""
-- PostgreSQL Row-Level Security (RLS) Complete User Isolation
-- Migration 002: Enhancements and fixes for production-ready RLS
-- Following KISS principle and 2025 best practices

-- ===== FIXES AND IMPROVEMENTS FROM 001 =====

-- Fix the database reference in role creation
DO $$ 
DECLARE
    db_name TEXT;
    has_createrole BOOLEAN;
BEGIN
    -- Check if current user has CREATEROLE privilege
    SELECT rolcreaterole INTO has_createrole
    FROM pg_roles
    WHERE rolname = current_user;
    
    -- Only attempt role creation if we have the privilege
    IF has_createrole THEN
        -- Get current database name
        SELECT current_database() INTO db_name;
        
        -- Create application role if not exists
        IF NOT EXISTS (
            SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app'
        ) THEN
            CREATE ROLE binomial_app WITH LOGIN;
            -- Grant permissions using dynamic database name
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO binomial_app', db_name);
            GRANT USAGE ON SCHEMA public TO binomial_app;
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO binomial_app;
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO binomial_app;
        END IF;
    ELSE
        RAISE NOTICE 'Skipping role creation - current user lacks CREATEROLE privilege';
    END IF;
END $$;

-- Ensure future tables also get permissions (only if role exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
        ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT ALL ON TABLES TO binomial_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT ALL ON SEQUENCES TO binomial_app;
    ELSE
        RAISE NOTICE 'Skipping default privileges - binomial_app role does not exist';
    END IF;
END $$;

-- ===== ANONYMOUS USER SUPPORT =====

-- Add support for anonymous sessions (user_id can be NULL)
-- Update policies to handle both authenticated and anonymous users

DROP POLICY IF EXISTS chat_sessions_isolation ON chat_sessions;
CREATE POLICY chat_sessions_isolation ON chat_sessions
    FOR ALL
    USING (
        -- Allow access if user_id matches OR if anonymous (NULL user_id)
        (user_id IS NULL AND current_setting('app.current_user_id', true) IS NULL)
        OR 
        (user_id::TEXT = current_setting('app.current_user_id', true))
    );

DROP POLICY IF EXISTS chat_messages_isolation ON chat_messages;
CREATE POLICY chat_messages_isolation ON chat_messages
    FOR ALL
    USING (
        -- Allow access if user_id matches OR if anonymous
        (user_id IS NULL AND current_setting('app.current_user_id', true) IS NULL)
        OR 
        (user_id::TEXT = current_setting('app.current_user_id', true))
    );

-- ===== IMPROVED HELPER FUNCTIONS =====

-- Function to set user context with validation
CREATE OR REPLACE FUNCTION set_user_context(user_uuid UUID)
RETURNS void AS $$
BEGIN
    IF user_uuid IS NULL THEN
        -- Clear the setting for anonymous access
        PERFORM set_config('app.current_user_id', '', true);
    ELSE
        -- Set the user ID for RLS
        PERFORM set_config('app.current_user_id', user_uuid::TEXT, true);
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to clear user context (for connection pool reuse)
CREATE OR REPLACE FUNCTION clear_user_context()
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_user_id', '', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ===== PERFORMANCE OPTIMIZATIONS =====

-- Partial indexes for faster anonymous queries
CREATE INDEX IF NOT EXISTS idx_chat_sessions_anonymous 
    ON chat_sessions(id) 
    WHERE user_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_chat_messages_anonymous 
    ON chat_messages(session_id, created_at DESC) 
    WHERE user_id IS NULL;

-- ===== SECURITY ENHANCEMENTS =====

-- Create a function to safely insert a new user (bypasses RLS for Clerk webhook)
CREATE OR REPLACE FUNCTION insert_user_from_clerk(
    p_clerk_user_id VARCHAR(255),
    p_email VARCHAR(255),
    p_name VARCHAR(255)
)
RETURNS UUID AS $$
DECLARE
    v_user_id UUID;
BEGIN
    INSERT INTO users (clerk_user_id, email, name)
    VALUES (p_clerk_user_id, p_email, p_name)
    ON CONFLICT (clerk_user_id) 
    DO UPDATE SET 
        email = EXCLUDED.email,
        name = EXCLUDED.name,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id INTO v_user_id;
    
    RETURN v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to the app role (only if role exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
        GRANT EXECUTE ON FUNCTION insert_user_from_clerk TO binomial_app;
        GRANT EXECUTE ON FUNCTION set_user_context TO binomial_app;
        GRANT EXECUTE ON FUNCTION clear_user_context TO binomial_app;
    ELSE
        RAISE NOTICE 'Skipping function grants - binomial_app role does not exist';
    END IF;
END $$;

-- ===== MIGRATION STATUS TABLE =====

-- Track migration status
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Record this migration
INSERT INTO schema_migrations (version, name)
VALUES (2, '002_rls_complete_isolation')
ON CONFLICT (version) DO NOTHING;

-- ===== VERIFICATION QUERIES (commented out, for testing) =====

-- Test RLS is working:
-- SET LOCAL app.current_user_id = 'some-uuid';
-- SELECT * FROM chat_sessions; -- Should only see that user's sessions

-- Test anonymous access:
-- SET LOCAL app.current_user_id = '';
-- SELECT * FROM chat_sessions WHERE user_id IS NULL; -- Should see anonymous sessions

-- Reset context:
-- RESET app.current_user_id;
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
