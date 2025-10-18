# TO COMPLETE WITH BUILDTIME VARS


from dotenv import load_dotenv
import os
from pathlib import Path
from datetime import datetime
from src.engines.base_engine import BaseEngine

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

LLM_Engine = BaseEngine.get_engine()

# ----------------------------
# LOGGING CONFIG
# ----------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"backend_{datetime.now().strftime('%Y-%m-%d')}.log"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 10  # Keep 10 rotated files