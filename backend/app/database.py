import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

import os, sys

if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
    default_data_dir = os.path.join(base_path, "data")
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
    default_data_dir = os.path.abspath(os.path.join(base_path, "..", "data"))

data_dir = os.getenv("DATA_DIR", default_data_dir)
os.makedirs(data_dir, exist_ok=True)


env_url = os.getenv("DATABASE_URL")
if env_url:
    DATABASE_URL = env_url
else:
    db_file = os.path.join(data_dir, "database.db")
    DATABASE_URL = f"sqlite:///{db_file}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()