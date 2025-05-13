from fastapi import APIRouter, HTTPException
from ..schemas.training_schemas import TrainingInfo

router = APIRouter()

@router.post("/upload-folders", status_code=200)
async def train_llm(payload: TrainingInfo):
    """
    Endpoint to receive info for training a model.
    """
    try:
        return {"message": "Infos reçus avec succès" + str(payload)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne du serveur : {str(e)}")
