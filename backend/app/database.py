import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# ─── 1) Determine where to look for our data/ folder ────────────────────────
if getattr(sys, "frozen", False):
    # PyInstaller bundle: _MEIPASS is the unpack directory
    base_path = sys._MEIPASS
else:
    # Normal dev: this file lives in backend/app/
    base_path = os.path.dirname(os.path.abspath(__file__))

# ─── 2) Resolve or create the data directory ───────────────────────────────
data_dir = os.getenv("DATA_DIR")  # optional override
if not data_dir:
    # default to a sibling “data/” next to your code
    data_dir = os.path.abspath(os.path.join(base_path, "..", "data"))
os.makedirs(data_dir, exist_ok=True)

# ─── 3) Build the DATABASE_URL ─────────────────────────────────────────────
# If you’ve set DATABASE_URL in .env, use it; otherwise point at data/database.db
env_url = os.getenv("DATABASE_URL")
if env_url:
    DATABASE_URL = env_url
else:
    db_file = os.path.join(data_dir, "database.db")
    DATABASE_URL = f"sqlite:///{db_file}"

# ─── 4) Create engine & session factory ──────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ─── 5) Optional FastAPI dependency ───────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()