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

        curl http://localhost:8000/erudi/health/
        # {"status": "ok", "message": "Backend is running"}

    Use in frontend before API calls::

        const response = await fetch('http://localhost:8000/erudi/health/');
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


@router.get("/")
async def health():
    """Health check endpoint returning basic service status.

    Returns:
        dict: Status object with "ok" indicator and descriptive message.

    Example:
        ::

            import requests

            response = requests.get("http://localhost:8000/erudi/health/")
            assert response.json()["status"] == "ok"
    """
    return {"status": "ok", "message": "Backend is running"}