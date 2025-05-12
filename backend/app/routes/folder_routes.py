from fastapi import APIRouter, HTTPException
from ..schemas.folder_schemas import FolderPaths

router = APIRouter()

@router.post("/upload-folders", status_code=200)
async def upload_folders(payload: FolderPaths):
    """
    Cette route reçoit une liste de chemins de dossiers.
    Traite ces chemins comme souhaité (par exemple, les sauvegarder ou effectuer une analyse).
    """
    try:
        # Logique pour traiter les chemins, ici on les affiche pour exemple
        print("Chemins de dossiers reçus :", payload.paths)

        # Tu peux ajouter ici de la logique pour traiter ces chemins
        # Exemple : sauvegarder dans une base de données, analyser les dossiers, etc.

        return {"message": "Chemins reçus et traités avec succès", "paths": payload.paths}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne du serveur : {str(e)}")
