"""Core exception handling for Erudi.

This module defines the exception hierarchy used throughout the application.
All business exceptions inherit from AppBaseException and provide structured
error reporting with HTTP status codes and custom error codes.

Fonctionnalités:
- Structured exception hierarchy with status codes
- Automatic error logging via structured logger
- FastAPI integration with JSON response handlers
- Custom Erudi error codes for client diagnostics

Examples:
    Raising a specific exception:
        from src.core.exceptions import ModelNotFoundException
        raise ModelNotFoundException("llama-2-7b")
    
    Handling exceptions in endpoints:
        from fastapi import FastAPI
        from src.core.exceptions import app_base_exception_handler, AppBaseException
        
        app = FastAPI()
        app.add_exception_handler(AppBaseException, app_base_exception_handler)

"""

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import status
from typing import Optional
from src.core.logging import logger


class AppBaseException(Exception):
    """Base class for all Erudi business exceptions.
    
    Provides structured error handling with HTTP status codes, custom error codes,
    and automatic logging. All application-specific exceptions should inherit from
    this class to ensure consistent error reporting.
    
    Attributes:
        message: Human-readable error description with support information.
        status_code: HTTP status code for the error response.
        erudi_code: Custom error code for client-side diagnostics.

    """
    
    def __init__(
            self,
            message: str = "An unexpected error occured.",
            status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
            erudi_code: Optional[str] = None,
            trace: Optional[str] = None,
    ):
        """Initialize the exception with error details.
        
        Args:
            message: Human-readable error description.
            status_code: HTTP status code (default: 500).
            erudi_code: Custom error code for diagnostics (default: "INTERNAL_SERVER_ERROR").
            trace: Optional stack trace or additional context.
            
        Note:
            The message is automatically extended with support contact information.
            All errors are logged via the structured logger.

        """
        self.message = message + "\nPlease report the bug on the dedicted section. You are welcome to contact erudipro@gmail.com for further support."
        self.status_code = status_code
        self.erudi_code = erudi_code or "INTERNAL_SERVER_ERROR"
        logger.error(f"- Status Code: {status_code}\n- Erudi Custom Code: {erudi_code}\n- Message: {message}\n- Trace: {trace}")
        super().__init__(message)

    def __repr__(self):
        return super().__repr__()


class ModelNotFoundException(AppBaseException):
    """Exception raised when a requested model cannot be found.
    
    Raised when attempting to load, access, or operate on a model that
    doesn't exist in the models directory or database.
    
    Examples:
        from src.core.exceptions import ModelNotFoundException
        raise ModelNotFoundException("llama-2-7b")

    """
    
    def __init__(self, model_name: str, trace: Optional[str] = None):
        """Initialize exception for missing model.
        
        Args:
            model_name: Name or ID of the model that was not found.
            trace: Optional stack trace or additional context.

        """
        super().__init__(message=f"Model '{model_name}' not found", status_code=status.HTTP_404_NOT_FOUND, erudi_code="MODEL_NOT_FOUND", trace=trace)


class InvalidInputException(AppBaseException):
    """Exception raised for invalid user input or request parameters.
    
    Used when request validation fails beyond Pydantic schema validation,
    such as business logic constraints or cross-field validation.
    
    Examples:
        from src.core.exceptions import InvalidInputException
        if temperature < 0 or temperature > 2:
            raise InvalidInputException("temperature")

    """
    
    def __init__(self, field_name: str, trace: Optional[str] = None):
        """Initialize exception for invalid input field.
        
        Args:
            field_name: Name of the field that contains invalid data.
            trace: Optional stack trace or additional context.

        """
        super().__init__(f"Invalid input for '{field_name}'", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, erudi_code="INVALID_INPUT", trace=trace)


class CeciEstUneTemplateDException(AppBaseException):
    """Template exception for creating new custom exceptions.
    
    Warning:
        This is a template class. Replace with actual exception name and logic.

    """
    
    def __init__(self, name: str, trace: Optional[str] = None):
        """Initialize template exception.
        
        Args:
            name: Placeholder parameter.
            trace: Optional stack trace or additional context.

        """
        super().__init__(
            message=f"xxx '{name}'",
            status_code="ICI METTRE UN STATUS CODE CONVENTIONNEL",
            erudi_code="ICI METTRE UN TRUC TAILORED TO LE PB",
            trace=trace
        )


class EngineException(AppBaseException):
    """Exception raised for LLM engine failures during inference.
    
    Covers model loading errors, inference failures, out-of-memory conditions,
    and other runtime issues during model execution.
    
    Examples:
        from src.core.exceptions import EngineException
        try:
            model.generate(prompt)
        except RuntimeError as e:
            raise EngineException(f"Inference failed: {e}")

    """
    
    def __init__(self, message: str, trace: Optional[str] = None):
        """Initialize engine exception with error details.
        
        Args:
            message: Description of the engine failure.
            trace: Optional stack trace or additional context.

        """
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            erudi_code="LLM_ENGINE_FAILURE",
            trace=trace
        )


class EmbeddingError(AppBaseException):
    """Exception raised for embedding generation failures.
    
    Raised when sentence-transformers embedding model fails to encode text,
    including model loading errors, out-of-memory conditions, or invalid input.
    
    Examples:
        from src.core.exceptions import EmbeddingError
        try:
            embeddings = embedder.encode(text)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed text: {e}")

    """
    
    def __init__(self, message: str, trace: Optional[str] = None):
        """Initialize embedding exception with error details.
        
        Args:
            message: Description of the embedding failure.
            trace: Optional stack trace or additional context.

        """
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            erudi_code="EMBEDDING_FAILURE",
            trace=trace
        )


async def app_base_exception_handler(request: Request, exc: AppBaseException):
    """Global exception handler for AppBaseException and subclasses.
    
    Converts application exceptions into structured JSON responses with
    appropriate HTTP status codes. Logs request details for debugging.
    
    Args:
        request: Incoming FastAPI request object.
        exc: The raised AppBaseException or subclass instance.
        
    Returns:
        JSONResponse with structured error information.
        
    Examples:
        Register in FastAPI application:
            from fastapi import FastAPI
            from src.core.exceptions import app_base_exception_handler, AppBaseException
            
            app = FastAPI()
            app.add_exception_handler(AppBaseException, app_base_exception_handler)

    """
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