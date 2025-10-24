"""
Utility module for handling file paths in both development and PyInstaller frozen environments.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def get_base_dir():
    """
    Get the base directory for the application.
    Returns the PyInstaller bundle directory when frozen, or the backend directory when in development.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - sys._MEIPASS is the _internal directory
        return Path(sys._MEIPASS)
    else:
        # Running in development - go up from app/utils to backend root
        return Path(__file__).parent.parent.parent


def init_environment():
    """
    Initialize environment variables by loading .env from the correct location.
    Must be called before accessing any environment variables.
    """
    if getattr(sys, 'frozen', False):
        # In production (frozen), .env is in the bundle directory
        base_dir = get_base_dir()
        env_path = base_dir / '.env'
    else:
        # In development, .env is in the project root (one level up from backend)
        base_dir = get_base_dir()
        env_path = base_dir.parent / '.env'
    
    load_dotenv(env_path)


def resolve_path(relative_path: str) -> Path:
    """
    Resolve a relative path to an absolute path based on the base directory.
    
    Args:
        relative_path: Path relative to the base directory (e.g., "./data/models")
    
    Returns:
        Absolute Path object
    """
    base_dir = get_base_dir()
    # Remove leading "./" if present
    if relative_path.startswith("./"):
        relative_path = relative_path[2:]
    return base_dir / relative_path


def get_database_url() -> str:
    """
    Get the absolute database URL, converting relative paths if needed.
    """
    init_environment()  # Ensure env vars are loaded
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/erudi.db")
    
    if db_url.startswith("sqlite:///./"):
        # Convert relative path to absolute
        relative_path = db_url.replace("sqlite:///./", "")
        absolute_path = resolve_path(relative_path)
        return f"sqlite:///{absolute_path}"
    
    return db_url


def get_cache_dir() -> Path:
    """Get the absolute path to the cache directory."""
    init_environment()
    cache_dir = os.getenv("CACHE_DIR", "./data/models_cache")
    return resolve_path(cache_dir)


def get_indexes_dir() -> Path:
    """Get the absolute path to the indexes directory."""
    init_environment()
    indexes_dir = os.getenv("INDEXES_DIR", "./data/indexes")
    return resolve_path(indexes_dir)
