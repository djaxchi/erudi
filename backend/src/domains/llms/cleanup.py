"""Utility functions for cleaning up partial downloads and temporary files."""

import os
import shutil
from pathlib import Path
from typing import Union

from src.core.logging import logger


def cleanup_partial_download(temp_dir: Union[str, Path], final_dir: Union[str, Path]) -> None:
    """Clean up partially downloaded files and directories.
    
    Args:
        temp_dir: Path to temporary download directory
        final_dir: Path to final model directory
        
    Note:
        Ignores errors during cleanup to ensure best-effort removal
    """
    for path in [temp_dir, final_dir]:
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                logger.debug(f"Cleaned up directory: {path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {path}: {e}")