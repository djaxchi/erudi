-- Migration SQL: Rename local_model_link to temp_local_model_link and add final_local_model_link
-- Date: 2025-09-08

-- Étape 1: Ajouter la nouvelle colonne final_local_model_link
ALTER TABLE download_jobs ADD COLUMN final_local_model_link TEXT;

-- Étape 2: Ajouter temporairement la nouvelle colonne temp_local_model_link
ALTER TABLE download_jobs ADD COLUMN temp_local_model_link_new TEXT;

-- Étape 3: Copier les données de local_model_link vers temp_local_model_link_new
UPDATE download_jobs SET temp_local_model_link_new = local_model_link;

-- Étape 4: Supprimer l'ancienne colonne local_model_link
ALTER TABLE download_jobs DROP COLUMN local_model_link;

-- Étape 5: Renommer temp_local_model_link_new en temp_local_model_link
ALTER TABLE download_jobs RENAME COLUMN temp_local_model_link_new TO temp_local_model_link;
