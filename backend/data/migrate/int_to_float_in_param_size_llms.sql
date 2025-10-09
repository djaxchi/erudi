-- Migration: Change the type of the column param_size in the llms table from INTEGER to FLOAT.
-- Note: SQLite does not support altering column types directly so we recreate the table.

BEGIN TRANSACTION;

-- Create a new table with the updated schema.
CREATE TABLE llms_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    local INTEGER NOT NULL,
    link VARCHAR,
    type VARCHAR NOT NULL,
    description VARCHAR,
    model_metadata VARCHAR,
    quantized INTEGER DEFAULT 0,
    param_size FLOAT DEFAULT 4,
    is_attached_to_kb INTEGER DEFAULT 0,
    kb_id INTEGER,
    FOREIGN KEY (kb_id) REFERENCES knowledge_base(id) ON DELETE SET NULL
);

-- Copy all data from the old table to the new table, casting param_size to FLOAT.
INSERT INTO llms_new (id, name, local, link, type, description, model_metadata, quantized, param_size, is_attached_to_kb, kb_id)
SELECT id, name, local, link, type, description, model_metadata, quantized, CAST(param_size AS FLOAT), is_attached_to_kb, kb_id
FROM llms;

-- Remove the old table.
DROP TABLE llms;

-- Rename the new table to the original table name.
ALTER TABLE llms_new RENAME TO llms;

COMMIT;