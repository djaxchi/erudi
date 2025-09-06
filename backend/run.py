import sys, json, socket, time, threading, logging, asyncio, os, shutil, platform, subprocess
from pathlib import Path

# --- Logging ---
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- Paths ---
HERE = Path(__file__).resolve().parent
# Quand packagé, PyInstaller met le contenu dans sys._MEIPASS. Mais on veut se référer
# à <App>.app/Contents/Resources/backend quand on est packagé. On gère les deux cas.
def is_frozen():
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def resources_backend_dir() -> Path:
    if is_frozen():
        # L’exécutable est copié dans .../Resources/backend
        return Path(sys.executable).resolve().parent
    else:
        # En dev, on considère le dossier du script
        return HERE

BASE_DIR = resources_backend_dir()

# Cible réelle writable (macOS) dans Application Support
def app_support_data_dir(app_name="erudi") -> Path:
    home = Path.home()
    return home / "Library" / "Application Support" / app_name / "backend" / "data"

# Lien attendu depuis la logique de l’app : .../Resources/backend/data
DATA_LINK = BASE_DIR / "data"

def ensure_data_symlink():
    real_dir = app_support_data_dir()
    real_dir.mkdir(parents=True, exist_ok=True)
    try:
        if DATA_LINK.exists() or DATA_LINK.is_symlink():
            # Si c’est un dossier normal dans l’app (mauvais), on le remplace par un symlink.
            if DATA_LINK.is_dir() and not DATA_LINK.is_symlink():
                # Migrer ce qu’il y a dedans
                for p in DATA_LINK.iterdir():
                    tgt = real_dir / p.name
                    if not tgt.exists():
                        if p.is_dir():
                            shutil.copytree(p, tgt)
                        else:
                            shutil.copy2(p, tgt)
                shutil.rmtree(DATA_LINK)
            elif DATA_LINK.is_symlink():
                # Si déjà bon symlink : s’assurer qu’il pointe vers real_dir
                target = Path(os.readlink(DATA_LINK)).resolve() if DATA_LINK.exists() else None
                if target and target != real_dir:
                    DATA_LINK.unlink()
            else:
                DATA_LINK.unlink()
        # Créer le symlink si absent
        if not DATA_LINK.exists():
            os.symlink(real_dir, DATA_LINK)
    except Exception as e:
        print(json.dumps({
            "event": "startup_error",
            "code": "DATA_SYMLINK_ERROR",
            "message": f"Failed to prepare data dir: {e}"
        }), flush=True)
        # On continue quand même; le backend pourra échouer plus tard si écriture nécessaire.

# --- FastAPI / Uvicorn ---
from app.main import app as fastapi_app
import uvicorn

HOST, PORT = "127.0.0.1", 8000

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
            # workers=1 (par défaut)
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
    print(json.dumps({"event": "starting", "arch": platform.machine()}), flush=True)

    # Sanity ARM64
    if platform.machine() != "arm64":
        print(json.dumps({
            "event": "startup_warning",
            "code": "NON_ARM64",
            "message": f"Running on {platform.machine()}, expected arm64"
        }), flush=True)

    # Data dir ready (symlink)
    ensure_data_symlink()

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