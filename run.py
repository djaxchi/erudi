import subprocess
import sys
import platform
from pathlib import Path
from threading import Thread

def ensure_venv_and_dependencies():
    backend_dir = Path("backend")
    venv_dir = backend_dir / "venv"
    is_windows = platform.system() == "Windows"

    # Création du venv avec le Python actuel
    if not venv_dir.exists():
        print("📦 Création de l'environnement virtuel...")
        result = subprocess.run(
            [sys.executable, "-m", "venv", "venv"],  # Utilisation de sys.executable
            cwd=backend_dir,
            check=True
        )

    # Détection des chemins spécifiques à l'OS
    bin_folder = venv_dir / ("Scripts" if is_windows else "bin")
    python_exe = "python.exe" if is_windows else "python"
    python_bin = (bin_folder / python_exe).resolve()

    # Vérification du binaire Python
    if not python_bin.exists():
        raise FileNotFoundError(f"❌ Le binaire Python est introuvable à : {python_bin}")

    # Installation des dépendances
    print("📚 Installation des dépendances backend...")
    subprocess.run(
        [str(python_bin), "-m", "pip", "install", "--break-system-packages", "-r", "requirements.txt"],
        cwd=backend_dir,
        check=True
    )

    return str(python_bin), str(backend_dir)

def run_backend(python_bin, backend_dir):
    print("🚀 Lancement du backend FastAPI...")
    subprocess.run(
        [python_bin, "-m", "uvicorn", "app.main:app", "--reload"],
        cwd=backend_dir,
        check=True
    )

def run_frontend():
    frontend_dir = Path("frontend")
    
    # Vérification de Node.js
    try:
        subprocess.run(["node", "--version"], check=True, capture_output=True)
        subprocess.run(["npm", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Node.js et npm doivent être installés !")
        raise

    print("📦 Installation des dépendances frontend...")
    subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
    print("🌐 Lancement du frontend...")
    subprocess.run(["npm", "start"], cwd=frontend_dir, check=True)

if __name__ == "__main__":
    try:
        python_bin, backend_dir = ensure_venv_and_dependencies()

        backend_thread = Thread(target=run_backend, args=(python_bin, backend_dir))
        frontend_thread = Thread(target=run_frontend)

        backend_thread.start()
        frontend_thread.start()

        backend_thread.join()
        frontend_thread.join()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur fatale : {str(e)}")
        sys.exit(1)