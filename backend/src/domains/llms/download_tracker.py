"""Thread-safe download tracking with cancellation support.

This module provides a DownloadTracker class that can be safely accessed from
multiple threads to track download progress and support cancellation.
"""
import threading
from typing import Optional
from datetime import datetime


class DownloadTracker:
    """Thread-safe download progress tracking with cancellation support.
    
    Attributes:
        percent (float): Download progress percentage (0-100)
        total_bytes (float): Total size of download in bytes
        eta_seconds (float): Estimated time remaining in seconds
        cancelled (bool): Flag indicating if download was cancelled
        _lock (threading.Lock): Thread synchronization lock
    """
    
    def __init__(self):
        """Initialize a new download tracker with cancellation support."""
        self._percent = 0.0
        self._total_bytes = 0.0
        self._eta_seconds = 0.0
        self._cancelled = False
        self._lock = threading.Lock()
        self._start_time: Optional[datetime] = None
        
    @property
    def percent(self) -> float:
        """Get current progress percentage (thread-safe)."""
        with self._lock:
            return self._percent
            
    @percent.setter 
    def percent(self, value: float):
        """Set current progress percentage (thread-safe)."""
        with self._lock:
            self._percent = value
            
    @property
    def total_bytes(self) -> float:
        """Get total download size in bytes (thread-safe)."""
        with self._lock:
            return self._total_bytes
            
    @total_bytes.setter
    def total_bytes(self, value: float):
        """Set total download size in bytes (thread-safe)."""
        with self._lock:
            self._total_bytes = value
            
    @property
    def eta_seconds(self) -> float:
        """Get estimated time remaining in seconds (thread-safe)."""
        with self._lock:
            return self._eta_seconds
            
    @eta_seconds.setter
    def eta_seconds(self, value: float):
        """Set estimated time remaining in seconds (thread-safe)."""
        with self._lock:
            self._eta_seconds = value
            
    @property
    def cancelled(self) -> bool:
        """Check if download has been cancelled (thread-safe)."""
        with self._lock:
            return self._cancelled
            
    def cancel(self):
        """Signal download cancellation (thread-safe)."""
        with self._lock:
            self._cancelled = True
            
    def should_continue(self) -> bool:
        """Check if download should continue (thread-safe).
        
        Returns:
            bool: False if cancelled, True otherwise
        """
        with self._lock:
            return not self._cancelled