import sys, json, socket, time, threading, logging, os, shutil, platform, sqlite3
from pathlib import Path

# ---------- Tame noisy libs ----------
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("PYTHONNOUSERSITE", "1")

# ---------- Line-buffered logs ----------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

APP_NAME = "erudi"
HOST, PORT = "127.0.0.1", 8000

def is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

def backend_root_dir() -> Path:
    # dev: repo/backend ; frozen: .../Contents/Resources/backend
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

BACKEND_DIR = backend_root_dir()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
try:
    os.chdir(BACKEND_DIR)
except Exception:
    pass

# ---------- Data location rules ----------
# DEV: use real folder repo/backend/data (no symlink)
# PROD (frozen): create App Support dir and symlink backend/data -> that dir
def prod_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME / "backend" / "prod" / "data"

DATA_LINK = BACKEND_DIR / "data"

def ensure_dev_data_dir():
    if DATA_LINK.exists():
        if DATA_LINK.is_symlink():
            target = None
            try:
                target = Path(os.readlink(DATA_LINK))
            except OSError:
                pass
            DATA_LINK.unlink(missing_ok=True)
    DATA_LINK.mkdir(parents=True, exist_ok=True)

def ensure_prod_symlink():
    real_data = prod_data_dir()
    real_data.mkdir(parents=True, exist_ok=True)

    if DATA_LINK.exists() or DATA_LINK.is_symlink():
        if DATA_LINK.is_dir() and not DATA_LINK.is_symlink():
            for p in DATA_LINK.iterdir():
                tgt = real_data / p.name
                if not tgt.exists():
                    if p.is_dir():
                        shutil.copytree(p, tgt)
                    else:
                        shutil.copy2(p, tgt)
            shutil.rmtree(DATA_LINK)
        elif DATA_LINK.is_symlink():
            try:
                target = Path(os.readlink(DATA_LINK)).resolve()
            except OSError:
                target = None
            if target and target != real_data:
                DATA_LINK.unlink()
        else:
            DATA_LINK.unlink()

    if not DATA_LINK.exists():
        os.symlink(real_data, DATA_LINK)

    db_path = real_data / "erudi.db"
    if not db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.close()
        except Exception as e:
            print(json.dumps({
                "event": "startup_error",
                "code": "SQLITE_PREP_ERROR",
                "message": f"Failed to prepare sqlite file: {e}"
            }), flush=True)

# ---------- Multiprocessing safety before heavy imports ----------
def force_mp_spawn():
    try:
        import multiprocessing as mp
        mp.freeze_support()
        try:
            mp.set_start_method("spawn", force=True)
        except RuntimeError:
            pass
        try:
            import torch.multiprocessing as tmp
            tmp.set_start_method("spawn", force=True)
        except Exception:
            pass
    except Exception:
        pass

force_mp_spawn()

# ---------- Import the FastAPI app AFTER env/path setup ----------
from src.main import app as fastapi_app  # noqa: E402
import uvicorn  # noqa: E402

def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def run_server():
    try:
        uvicorn.run(
            fastapi_app,
            host=HOST,
            port=PORT,
            log_level="info",
            workers=1,      
            reload=False
        )
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

if __name__ == "__main__":
    force_mp_spawn()

    mode = "prod" if is_frozen() else "dev"
    try:
        if is_frozen():
            ensure_prod_symlink()
        else:
            ensure_dev_data_dir()
    except Exception as e:
        print(json.dumps({
            "event": "startup_error",
            "code": "DATA_PREP_ERROR",
            "message": f"Failed to prepare data dir: {e}"
        }), flush=True)

    print(json.dumps({
        "event": "starting",
        "arch": platform.machine(),
        "mode": mode,
        "data_path": str(DATA_LINK.resolve() if DATA_LINK.exists() else DATA_LINK)
    }), flush=True)

    if port_open(HOST, PORT):
        print(json.dumps({
            "event": "startup_error",
            "code": "PORT_IN_USE",
            "message": f"Port {PORT} already in use"
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
