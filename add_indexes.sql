-- Database performance optimization indexes
-- Run this SQL script on your database to add indexes for faster queries

-- Add index on status column (if not exists)
CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);

-- Add index on created_at column (if not exists)
CREATE INDEX IF NOT EXISTS idx_episodes_created_at ON episodes(created_at);

-- Add composite index for common query pattern: user_id + status + created_at
-- This speeds up filtered and sorted list queries significantly
CREATE INDEX IF NOT EXISTS idx_user_status_created ON episodes(user_id, status, created_at);

-- Add composite index for user_id + created_at (for sorting without status filter)
CREATE INDEX IF NOT EXISTS idx_user_created ON episodes(user_id, created_at);

-- Analyze tables to update query planner statistics
ANALYZE episodes;

