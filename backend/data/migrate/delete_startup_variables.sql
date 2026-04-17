-- Migration: Delete StartupVariables entry
-- This will force model reseeding on next app startup
-- Run with: sqlite3 data/erudi.db < data/migrate/delete_startup_variables.sql

-- Delete the StartupVariables entry (singleton table)
DELETE FROM startup_variables;

-- Verify deletion
SELECT COUNT(*) as startup_variables_count FROM startup_variables;

-- Optional: Check what was deleted
-- SELECT * FROM startup_variables;  -- Should return no rows