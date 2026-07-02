"""Request-scoped context shared between the HTTP middleware and the logger.

The current request id lives in a ContextVar so that every log line emitted
while handling a request (endpoints, services, engines, ingestion) is
automatically tagged with the id of the request that triggered it — without
threading the id through function signatures. ContextVars propagate through
the request's async call chain, and each request task gets its own context,
so concurrent requests never see each other's ids.

The id is either taken from the incoming ``X-Request-ID`` header (letting the
Electron frontend correlate its own log with the backend's) or generated here
with a ``be-`` prefix marking it as backend-originated.
"""

from contextvars import ContextVar
from uuid import uuid4

# "-" is the out-of-request marker (startup, shutdown, background tasks).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the id of the request being handled, or ``-`` outside a request."""
    return request_id_var.get()


def new_request_id() -> str:
    """Generate a short backend-originated request id, e.g. ``be-1f2e3d4c``."""
    return f"be-{uuid4().hex[:8]}"
