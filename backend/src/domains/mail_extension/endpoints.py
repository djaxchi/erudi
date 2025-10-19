from fastapi import APIRouter

router = APIRouter(prefix="/mail_extension", tags=["mail_extension"])

@router.get("/extension-bridge")
async def extension_bridge():
    """
    Simple ping endpoint pour les extensions Chrome/Firefox.
    Permet de vérifier la connexion entre l'extension et Erudit backend.
    """
    return {
        "status": "ok",
        "source": "Erudit backend",
        "message": "Extension bridge actif"
    } 