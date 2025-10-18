from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Optional
from src.core.logging import logger

# === Base Business Exception ===
class AppBaseException(Exception):
    """Base class for all business exceptions."""
    def __init__(
            self,
            message: str = "An unexpected error occured.",
            status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
            erudi_code: Optional[str] = None,
            trace: Optional[str] = None,
    ):
        self.message = message + "\nPlease report the bug on the dedicted section. You are welcome to contact erudipro@gmail.com for further support."
        self.status_code = status_code
        self.erudi_code = erudi_code or "INTERNAL_SERVER_ERROR"
        logger.error(f"- Status Code: {status_code}\n- Erudi Custom Code: {erudi_code}\n- Message: {message}\n- Trace: {trace}")
        super().__init__(message)

    def __repr__(self):
        return super().__repr__()

# === Specific Business Exceptions ===
class ModelNotFoundException(AppBaseException):
    def __init__(self, model_name: str, trace: Optional[str] = None):
        super().__init__(message=f"Model '{model_name}' not found", status_code=status.HTTP_404_NOT_FOUND, erudi_code="MODEL_NOT_FOUND", trace=trace)

class InvalidInputException(AppBaseException):
    def __init__(self, field_name: str, trace: Optional[str] = None):
        super().__init__(f"Invalid input for '{field_name}'", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, erudi_code="INVALID_INPUT", trace=trace)

class CeciEstUneTemplateDException(AppBaseException):
    def __init__(self, name: str, trace: Optional[str] = None):
        super().__init__(
            message=f"xxx '{name}'",
            status_code="ICI METTRE UN STATUS CODE CONVENTIONNEL",
            erudi_code="ICI METTRE UN TRUC TAILORED TO LE PB",
            trace=trace
        )

class EngineException(AppBaseException):
    def __init__(self, message: str, trace: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            erudi_code="LLM_ENGINE_FAILURE",
            trace=trace
        )
    
# === Global Exception Handlers ===
async def app_base_exception_handler(request: Request, exc: AppBaseException):
    logger.error(f"- Path: {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": exc.erudi_code,
                "message": exc.message
            }
        }
    )