"""
012_workflows

Revision ID: b5965227dcb5
Revises: 4fb3dc2fca94
Create Date: 2025-12-31T16:05:17.184166

Original SQL file: 012_workflows.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b5965227dcb5"
down_revision = "4fb3dc2fca94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 012_workflows.sql."""
    op.execute("""
-- Workflow Tables with Row-Level Security (RLS)
-- Migration: 20250902_workflows.sql
-- Purpose: Create workflow persistence layer with complete user isolation

-- ===== WORKFLOW TABLES =====

-- Main workflows table
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    version INTEGER DEFAULT 1,
    
    -- Store the workflow graph as JSONB
    nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
    edges JSONB NOT NULL DEFAULT '[]'::jsonb,
    configuration JSONB DEFAULT '{}'::jsonb,
    
    -- Status management
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,  -- Soft delete
    
    -- Indexes for performance
    CONSTRAINT workflows_name_not_empty CHECK (name != '')
);

-- Workflow runs table
CREATE TABLE IF NOT EXISTS workflow_runs (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    
    -- Run configuration
    input_data JSONB DEFAULT '{}'::jsonb,
    output_data JSONB,
    configuration JSONB DEFAULT '{}'::jsonb,
    
    -- Status tracking
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    error_message TEXT,
    
    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individual step execution tracking
CREATE TABLE IF NOT EXISTS workflow_run_steps (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,  -- References node.id in the workflow graph
    user_id TEXT NOT NULL,
    
    -- Step details
    node_type TEXT NOT NULL CHECK (node_type IN ('dataset', 'agent', 'output')),
    node_label TEXT,
    
    -- Execution data
    input_data JSONB DEFAULT '{}'::jsonb,
    output_data JSONB,
    configuration JSONB DEFAULT '{}'::jsonb,
    
    -- Status and timing
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Order of execution
    execution_order INTEGER
);

-- ===== INDEXES FOR PERFORMANCE =====

CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_workflows_created_at ON workflows(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_id ON workflow_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_user_id ON workflow_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_created_at ON workflow_runs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_run_id ON workflow_run_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_user_id ON workflow_run_steps(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_node_id ON workflow_run_steps(node_id);

-- ===== ROW-LEVEL SECURITY (RLS) =====

-- Enable RLS on all workflow tables
-- FORCE makes it apply even to table owner (but not superusers)
ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_run_steps ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners
ALTER TABLE workflows FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow_run_steps FORCE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS workflows_isolation ON workflows;
DROP POLICY IF EXISTS workflow_runs_isolation ON workflow_runs;
DROP POLICY IF EXISTS workflow_run_steps_isolation ON workflow_run_steps;

-- Workflows table RLS policy (NULL-safe)
CREATE POLICY workflows_isolation ON workflows
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Workflow runs RLS policy (NULL-safe)
CREATE POLICY workflow_runs_isolation ON workflow_runs
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Workflow run steps RLS policy (uses subquery to prevent spoofing)
-- Steps are only accessible if the parent run belongs to the current user
CREATE POLICY workflow_run_steps_isolation ON workflow_run_steps
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND run_id IN (
            SELECT id FROM workflow_runs
            WHERE user_id = current_setting('app.current_user_id', true)
        )
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND run_id IN (
            SELECT id FROM workflow_runs
            WHERE user_id = current_setting('app.current_user_id', true)
        )
    );

-- ===== TRIGGERS FOR UPDATED_AT =====

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for workflows table
DROP TRIGGER IF EXISTS update_workflows_updated_at ON workflows;
CREATE TRIGGER update_workflows_updated_at
    BEFORE UPDATE ON workflows
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ===== GRANT PERMISSIONS =====

-- Grant permissions to application role if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
        GRANT ALL PRIVILEGES ON workflows TO binomial_app;
        GRANT ALL PRIVILEGES ON workflow_runs TO binomial_app;
        GRANT ALL PRIVILEGES ON workflow_run_steps TO binomial_app;
    END IF;
END $$;
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
