-- Add param_size column to llms table
-- This column stores the model parameter size in billions (2, 4, 8, 16, etc.)
-- Default value is 2B for existing models

ALTER TABLE llms ADD COLUMN param_size INTEGER DEFAULT 2;
