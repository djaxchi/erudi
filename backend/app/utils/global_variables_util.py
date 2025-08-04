import os, sys, logging
from pathlib import Path
from dotenv import load_dotenv

###### BASE_PATH ######
if getattr(sys, 'frozen', False): # Mode build
    BASE_PATH = sys._MEIPASS
    JINJA_TEMPLATES_PATH = os.path.join(BASE_PATH, "jinja")
    dotenv_path = os.path.join(BASE_PATH, ".env")
else: # Mode dev
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        if parent.name == 'backend':
            BASE_PATH = str(parent)
            JINJA_TEMPLATES_PATH = os.path.join(BASE_PATH, "app", "prompting", "jinja_templates")
            dotenv_path = os.path.join(BASE_PATH, "..", ".env")
logging.info(f"BASE_PATH resolved to: {BASE_PATH}")
load_dotenv(dotenv_path)

###### VARIABLES PUBLIQUES ######
# Ces variables sont accessibles par tout le monde
# et peuvent apparaitre dans le code source de l'application
# après installation.

# CACHE_DIR : dossier de cache pour les modèles
env_cache_relatif = os.getenv("CACHE_DIR", "data/models_cache")
CACHE_DIR = os.path.normpath(os.path.join(BASE_PATH, env_cache_relatif.lstrip("./")))
os.makedirs(CACHE_DIR, exist_ok=True)
logging.info(f"CACHE_DIR resolved to: {CACHE_DIR}")

# INDEXES_DIR : dossier pour les index de recherche
env_indexes_relatif = os.getenv("INDEXES_DIR", "data/indexes")
INDEXES_DIR = os.path.normpath(os.path.join(BASE_PATH, env_indexes_relatif.lstrip("./")))
os.makedirs(INDEXES_DIR, exist_ok=True)
logging.info(f"INDEXES_DIR resolved to: {INDEXES_DIR}")

# DATABASE_URL : URL de connexion à la base de données locale
env_db_url = os.getenv("DATABASE_PATH", "data/erudi.db")
DATABASE_URL = "sqlite:///" + os.path.normpath(os.path.join(BASE_PATH, env_db_url.lstrip("./")))
logging.info(f"DATABASE_URL resolved to: {DATABASE_URL}")


###### VARIABLES SECRETES ######

#HF_TOKEN : Token Hugging Face de Erudi pour accéder aux modèles
try: # Mode build (erudi_secrets.py est automatiquement généré par CI)
    from backend.app.secrets import HF_TOKEN
    HF_TOKEN = HF_TOKEN
    _source = "build-time secrets"
except ImportError: # Mode dev (on lit le .env qui se trouve dans backend/)
    load_dotenv(os.path.normpath(os.path.join(BASE_PATH, ".env")))
    HF_TOKEN = os.getenv("HF_TOKEN")
    _source = "dev .env"
logging.info(f"HF_TOKEN loaded from {_source}")