-- Migration: Update user_id columns to use clerk_user_id instead of UUID
-- Date: 2025-09-23
-- Purpose: Standardize on Clerk IDs throughout the system (no more UUID lookups)
--
-- IMPORTANT: Run this only ONCE after backing up your database
-- This assumes your users table has both id (UUID) and clerk_user_id (text) columns

-- Step 1: Create backup tables (safety first!)
CREATE TABLE IF NOT EXISTS chat_sessions_backup AS SELECT * FROM chat_sessions;
CREATE TABLE IF NOT EXISTS chat_messages_backup AS SELECT * FROM chat_messages;
CREATE TABLE IF NOT EXISTS portfolios_backup AS SELECT * FROM portfolios;
CREATE TABLE IF NOT EXISTS risk_analyses_backup AS SELECT * FROM risk_analyses;

-- Step 2: Update user_id to clerk_user_id in all affected tables
-- This joins with the users table to map UUID to clerk_user_id

-- Update chat_sessions
UPDATE chat_sessions
SET user_id = u.clerk_user_id
FROM users u
WHERE chat_sessions.user_id = u.id::text;

-- Update chat_messages
UPDATE chat_messages
SET user_id = u.clerk_user_id
FROM users u
WHERE chat_messages.user_id = u.id::text;

-- Update portfolios
UPDATE portfolios
SET user_id = u.clerk_user_id
FROM users u
WHERE portfolios.user_id = u.id::text;

-- Update risk_analyses (if table exists)
UPDATE risk_analyses
SET user_id = u.clerk_user_id
FROM users u
WHERE risk_analyses.user_id = u.id::text
AND EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'risk_analyses'
);

-- Step 3: Verify the migration worked
-- Run these queries to check:
-- SELECT COUNT(*) FROM chat_sessions WHERE user_id LIKE 'user_%';  -- Should return count > 0
-- SELECT COUNT(*) FROM chat_messages WHERE user_id LIKE 'user_%';  -- Should return count > 0
-- SELECT COUNT(*) FROM portfolios WHERE user_id LIKE 'user_%';     -- Should return count > 0

-- Step 4: If everything looks good, you can drop the backup tables later:
-- DROP TABLE chat_sessions_backup;
-- DROP TABLE chat_messages_backup;
-- DROP TABLE portfolios_backup;
-- DROP TABLE risk_analyses_backup;