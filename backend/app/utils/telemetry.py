"""
Beta Telemetry Service
Collects usage data for beta testing with offline support and Google Sheets integration.
"""

import os
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import threading
import queue
from collections import deque
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class TelemetryService:
    """
    Simple telemetry service that queues events and sends them to Google Sheets via Apps Script.
    Works offline - events are queued and sent when internet is available.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.telemetry_dir = data_dir / "telemetry"
        self.telemetry_dir.mkdir(exist_ok=True)
        
        # Queue file for offline events
        self.queue_file = self.telemetry_dir / "event_queue.jsonl"
        
        # In-memory queue for current session
        self.event_queue = deque(maxlen=1000)  # Limit to 1000 events in memory
        
        # Load any pending events from disk
        self._load_queue()
        
        # Google Apps Script configuration (simpler than Sheets API)
        self.apps_script_url = os.getenv("TELEMETRY_APPS_SCRIPT_URL")
        self.sheets_enabled = bool(self.apps_script_url)
        
        if self.sheets_enabled:
            logger.info(f"Telemetry: Apps Script integration enabled")
        else:
            logger.info("Telemetry: Not configured (set TELEMETRY_APPS_SCRIPT_URL env var)")
        
        # Background thread for sending events
        self.send_queue = queue.Queue()
        self.sender_thread = threading.Thread(target=self._event_sender, daemon=True)
        self.sender_thread.start()
    
    def _load_queue(self):
        """Load pending events from disk"""
        if not self.queue_file.exists():
            return
            
        try:
            with open(self.queue_file, 'r') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        self.event_queue.append(event)
                    except json.JSONDecodeError:
                        continue
            logger.info(f"Telemetry: Loaded {len(self.event_queue)} pending events")
        except Exception as e:
            logger.error(f"Telemetry: Failed to load event queue: {e}")
    
    def _save_queue(self):
        """Save pending events to disk"""
        try:
            with open(self.queue_file, 'w') as f:
                for event in self.event_queue:
                    f.write(json.dumps(event) + '\n')
        except Exception as e:
            logger.error(f"Telemetry: Failed to save event queue: {e}")
    
    def track_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ):
        """
        Track a telemetry event
        
        Args:
            event_type: Type of event (e.g., "model_download", "chat_message", "training_start")
            user_id: Anonymous user identifier
            properties: Additional event properties
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "user_id": user_id or "anonymous",
            "timestamp": datetime.utcnow().isoformat(),
            "properties": properties or {}
        }
        
        # Add to in-memory queue
        self.event_queue.append(event)
        
        # Queue for sending
        self.send_queue.put(event)
        
        # Persist to disk (in case app crashes)
        self._save_queue()
        
        logger.debug(f"Telemetry: Tracked event {event_type}")
    
    def _event_sender(self):
        """Background thread that sends events to Google Sheets"""
        while True:
            try:
                # Get event from queue (blocks until available)
                event = self.send_queue.get(timeout=1.0)
                
                # Try to send if sheets is enabled
                if self.sheets_enabled:
                    self._send_to_sheets(event)
                    
            except queue.Empty:
                # Also try to send any backlog periodically
                if self.sheets_enabled and len(self.event_queue) > 0:
                    self._flush_backlog()
            except Exception as e:
                logger.error(f"Telemetry sender error: {e}")
    
    def _send_to_sheets(self, event: Dict[str, Any]) -> bool:
        """
        Send a single event to Google Sheets via Apps Script
        Returns True if successful, False otherwise
        """
        if not self.sheets_enabled:
            return False
            
        try:
            # Prepare JSON payload
            payload = json.dumps(event).encode('utf-8')
            
            # Create request
            req = urllib.request.Request(
                self.apps_script_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            # Send request with timeout
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                if result.get('status') == 'success':
                    # Remove from queue on success
                    try:
                        self.event_queue.remove(event)
                        self._save_queue()
                    except ValueError:
                        pass  # Event already removed
                    
                    return True
                else:
                    logger.error(f"Telemetry: Apps Script error: {result.get('message')}")
                    return False
            
        except urllib.error.URLError as e:
            logger.debug(f"Telemetry: Network error (offline?): {e}")
            return False
        except Exception as e:
            logger.error(f"Telemetry: Failed to send event: {e}")
            return False
    
    def _flush_backlog(self, max_events: int = 50):
        """Send pending events in batches"""
        if not self.sheets_enabled or len(self.event_queue) == 0:
            return
            
        # Send up to max_events
        events_to_send = list(self.event_queue)[:max_events]
        
        try:
            # Prepare batch payload
            payload = json.dumps({
                'events': events_to_send
            }).encode('utf-8')
            
            # Create request
            req = urllib.request.Request(
                self.apps_script_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            # Send batch request
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                if result.get('status') == 'success':
                    # Remove sent events
                    for event in events_to_send:
                        try:
                            self.event_queue.remove(event)
                        except ValueError:
                            pass
                    
                    self._save_queue()
                    logger.info(f"Telemetry: Flushed {result.get('events_received', len(events_to_send))} events")
                else:
                    logger.error(f"Telemetry: Batch send error: {result.get('message')}")
            
        except urllib.error.URLError as e:
            logger.debug(f"Telemetry: Network error during batch send: {e}")
        except Exception as e:
            logger.error(f"Telemetry: Failed to flush backlog: {e}")
    
    def get_queue_size(self) -> int:
        """Get number of pending events"""
        return len(self.event_queue)
    
    def clear_queue(self):
        """Clear all pending events (use with caution)"""
        self.event_queue.clear()
        self._save_queue()
        logger.info("Telemetry: Cleared event queue")


# Global telemetry instance
_telemetry_instance: Optional[TelemetryService] = None


def init_telemetry(data_dir: Path) -> TelemetryService:
    """Initialize the global telemetry service"""
    global _telemetry_instance
    _telemetry_instance = TelemetryService(data_dir)
    return _telemetry_instance


def get_telemetry() -> Optional[TelemetryService]:
    """Get the global telemetry instance"""
    return _telemetry_instance


def track_event(event_type: str, user_id: Optional[str] = None, properties: Optional[Dict[str, Any]] = None):
    """Convenience function to track an event"""
    if _telemetry_instance:
        _telemetry_instance.track_event(event_type, user_id, properties)
