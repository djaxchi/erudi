# run.py (simplified Windows-only startup launcher)
# Purpose:
#   Launch the FastAPI backend (uvicorn) and emit structured JSON lifecycle events
#   so the Electron main process can show precise startup status (starting, ready,
#   various error conditions, and shutdown) instead of hanging silently.
#
# Key behaviors:
#   1. Print a 'starting' JSON event immediately.
#   2. Check if the target port is already in use -> emit PORT_IN_USE error.
#   3. Start uvicorn in a background thread (so we can keep emitting status from main thread).
#   4. Poll the port until it opens (readiness) or timeout / early crash occurs.
#   5. Emit 'ready' once the socket is accepting connections.
#   6. When server thread ends naturally, emit 'shutdown'.
#   7. Emit specific 'startup_error' JSON events for timeout or early crash.
#
# Notes:
#   - This version assumes Windows only (uses WindowsSelectorEventLoopPolicy).
#   - All structured messages are single-line JSON (newline-delimited) so the
#     Electron launcher can parse them line-by-line without buffering issues.
#   - Line buffering is forced on stdout/stderr to flush each print immediately.

import sys, json, socket, time, threading, logging, asyncio, os
from pathlib import Path
from asyncio import WindowsSelectorEventLoopPolicy  # Windows-only event loop policy (explicit here for clarity)

# Force Windows event loop policy (selector) — avoids potential compatibility issues
# with default Proactor loop for certain libraries on older Python versions.
asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

# Ensure backend package path so 'from app.main import app' works whether run as script or frozen
BACKEND_DIR = Path(__file__).parent / "backend"
if BACKEND_DIR.exists() and str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Enable immediate flushing of prints (critical for real-time UI feedback)
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Import the FastAPI app object that uvicorn will serve
from app.main import app as fastapi_app  # noqa: E402
import uvicorn  # noqa: E402

# Target bind address for the API server
HOST, PORT = "127.0.0.1", 8000

# Helper: attempt a short TCP connect to determine if port is open (readiness or conflict)
def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

if __name__ == "__main__":    
    # 1. Signal that the launcher started.
    print(json.dumps({"event": "starting"}), flush=True)

    # 2. Fail fast if port is already claimed by another process.
    if port_open(HOST, PORT):
        print(json.dumps({
            "event": "startup_error",
            "code": "PORT_IN_USE",
            "message": f"Port {PORT} already in use"
        }), flush=True)
        sys.exit(1)

    # 3. Define thread target: run uvicorn server (blocking call inside thread).
    # Wrap in try/except to prevent thread crashes from killing the main process
    def run_server():
        try:
            uvicorn.run(fastapi_app, host=HOST, port=PORT, log_level="info")
        except SystemExit:
            # uvicorn calls sys.exit() on shutdown - this is normal
            pass
        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            pass
        except Exception as e:
            # Log any unexpected errors but don't let them kill the process
            print(json.dumps({
                "event": "startup_error",
                "code": "UNEXPECTED_ERROR",
                "message": f"Server thread crashed: {str(e)}"
            }), flush=True)
            sys.exit(1)

    # 4. Start uvicorn in a daemon thread (dies with main process for safety).
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # 5. Poll for up to N seconds until the port opens (readiness) or thread dies early.
    deadline = time.time() + 25  # 25s timeout window
    try:
        while time.time() < deadline:
            # Port open = server bound successfully => emit 'ready' then wait for natural shutdown.
            if port_open(HOST, PORT):
                print(json.dumps({"event": "ready", "port": PORT}), flush=True)
                # Block until server finishes (user or system initiated shutdown)
                # Use timeout to avoid infinite blocking if thread becomes unresponsive
                t.join(timeout=1.0)
                while t.is_alive():
                    time.sleep(1.0)  # Keep checking if thread is still alive
                    t.join(timeout=1.0)
                print(json.dumps({"event": "shutdown"}), flush=True)
                break
            # If the thread is no longer alive before binding, it's a crash / early failure.
            if not t.is_alive():
                print(json.dumps({
                    "event": "startup_error",
                    "code": "CRASH_BEFORE_READY",
                    "message": "Backend thread exited early"
                }), flush=True)
                sys.exit(1)
            time.sleep(0.25)  # Short sleep between probes to avoid busy waiting
        else:
            # 6. Timeout loop exhausted without readiness => emit timeout error.
            print(json.dumps({
                "event": "startup_error",
                "code": "PORT_TIMEOUT",
                "message": "Server did not bind in time"
            }), flush=True)
            sys.exit(1)
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        print(json.dumps({"event": "shutdown"}), flush=True)
        sys.exit(0)
    except Exception as e:
        # Catch any unexpected errors in the main polling loop
        print(json.dumps({
            "event": "startup_error", 
            "code": "POLLING_ERROR",
            "message": f"Main polling loop crashed: {str(e)}"
        }), flush=True)
        sys.exit(1)