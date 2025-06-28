import sys, json, socket, time, threading, logging, asyncio, os
from pathlib import Path
from asyncio import WindowsSelectorEventLoopPolicy

# Force Windows event loop policy (selector) — avoids potential compatibility issues
# with default Proactor loop for certain libraries on older Python versions.
asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

BACKEND_DIR = Path(__file__).parent / "backend"
if BACKEND_DIR.exists() and str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from app.main import app as fastapi_app  # noqa: E402
import uvicorn  # noqa: E402

HOST, PORT = "127.0.0.1", 8000

def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

if __name__ == "__main__":    
    print(json.dumps({"event": "starting"}), flush=True)

    if port_open(HOST, PORT):
        print(json.dumps({
            "event": "startup_error",
            "code": "PORT_IN_USE",
            "message": f"Port {PORT} already in use"
        }), flush=True)
        sys.exit(1)

    def run_server():
        try:
            uvicorn.run(fastapi_app, host=HOST, port=PORT, log_level="info")
        except SystemExit:
            pass
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(json.dumps({
                "event": "startup_error",
                "code": "UNEXPECTED_ERROR",
                "message": f"Server thread crashed: {str(e)}"
            }), flush=True)
            sys.exit(1)

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    deadline = time.time() + 120
    try:
        while time.time() < deadline:
            if port_open(HOST, PORT):
                print(json.dumps({"event": "ready", "port": PORT}), flush=True)
                t.join(timeout=1.0)
                while t.is_alive():
                    time.sleep(1.0)
                    t.join(timeout=1.0)
                print(json.dumps({"event": "shutdown"}), flush=True)
                break
            if not t.is_alive():
                print(json.dumps({
                    "event": "startup_error",
                    "code": "CRASH_BEFORE_READY",
                    "message": "Backend thread exited early"
                }), flush=True)
                sys.exit(1)
            time.sleep(0.25)  
        else:
            print(json.dumps({
                "event": "startup_error",
                "code": "PORT_TIMEOUT",
                "message": "Server did not bind in time"
            }), flush=True)
            sys.exit(1)
    except KeyboardInterrupt:
        print(json.dumps({"event": "shutdown"}), flush=True)
        sys.exit(0)
    except Exception as e:
        print(json.dumps({
            "event": "startup_error", 
            "code": "POLLING_ERROR",
            "message": f"Main polling loop crashed: {str(e)}"
        }), flush=True)
        sys.exit(1)