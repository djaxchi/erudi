"""Health check endpoint for service monitoring and uptime verification.

This module provides a simple HTTP GET endpoint to verify the backend is
running and responsive. Used by:
- Load balancers for health checks
- Monitoring tools (Prometheus, Datadog)
- Frontend to verify backend availability before making API calls

Endpoint:
    GET /erudi/health/

    Response (200 OK)::

        {
          "status": "ok",
          "message": "Backend is running"
        }

Example:
    Check backend health from command line::

        curl http://127.0.0.1:27182/erudi/health/
        # {"status": "ok", "message": "Backend is running"}

    Use in frontend before API calls::

        const response = await fetch('http://127.0.0.1:27182/erudi/health/');
        if (response.ok) {
            // Backend available, proceed with API calls
        }

Note:
    This endpoint does NOT check:
    - Database connectivity
    - Engine status (model loaded/available)
    - Disk space or memory usage

    For detailed system metrics, use /erudi/hardware/static endpoints.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


def _db_state() -> str:
    """Embedded-Postgres health as tracked by the DB watchdog (#162).

    Imported lazily and defensively: the watchdog may not be started (unit
    tests, partial boots, plain uvicorn without the lifespan), and health must
    never crash. Defaults to "ok" when the watchdog is absent.
    """
    try:
        from src.launcher.db_watchdog import get_db_state

        return get_db_state()
    except Exception:
        return "ok"


@router.get("/")
async def health():
    """Health check endpoint returning basic service status.

    The HTTP status is ALWAYS 200 (Electron's boot readiness must not confuse
    a dead database with a dead backend); the ``db`` field carries the truth --
    ``"ok" | "recovering" | "failed"`` as seen by the DB watchdog (#162).

    Returns:
        dict: Status object with "ok" indicator, descriptive message, and the
        current database state.

    Example:
        ::

            import requests

            response = requests.get("http://127.0.0.1:27182/erudi/health/")
            assert response.json()["status"] == "ok"
    """
    return {"status": "ok", "message": "Backend is running", "db": _db_state()}