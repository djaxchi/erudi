"""Startup domain - Application startup state management.

This domain manages persistent UI state flags that survive across application restarts,
such as welcome popup display status. Uses singleton pattern for the StartupVariables entity.

Modules:
    - endpoints: FastAPI routes for startup state management.
    - repository: Data access layer for StartupVariables entity.
    - schemas: Pydantic models for request/response validation.

Example:
    from src.domains.startup.repository import Startup_Variables_Repository
    from src.domains.startup.schemas import WelcomePopupResponse

    # In FastAPI endpoint
    @router.get("/welcome-popup", response_model=WelcomePopupResponse)
    def check_popup(repo: Startup_Variables_Repository = Depends(get_startup_repository)):
        vars = repo.get_or_create()
        return WelcomePopupResponse(has_already_displayed=vars.welcome_popup_has_already_displayed)
"""
