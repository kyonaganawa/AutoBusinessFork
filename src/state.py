import os
import json
from typing import Dict, Optional
from datetime import datetime
from uuid import uuid4

from config import ROOT_DIR, get_verbose
from status import info, error, warning

# Define the state file path
STATE_DIR = os.path.join(ROOT_DIR, ".state")
VIDEO_STATE_FILE = os.path.join(STATE_DIR, "video_state.json")

class VideoState:
    """Manages the state of video generation process for persistence."""
    
    def __init__(self):
        """Initialize the state management system."""
        # Create state directory if it doesn't exist
        if not os.path.exists(STATE_DIR):
            os.makedirs(STATE_DIR)
        
        # Create or load state file
        if not os.path.exists(VIDEO_STATE_FILE):
            self._state = {}
            self._save_state()
        else:
            self._load_state()
            self._migrate_sessions()
    
    def _migrate_sessions(self):
        """Migrate old session format to new format.
        
        This ensures all sessions have required fields and updates
        any old sessions to the new format.
        """
        modified = False
        for session_id, session in self._state.items():
            # Add ID field if missing
            if 'id' not in session:
                session['id'] = session_id
                modified = True
                if get_verbose():
                    info(f"Migrated session {session_id}: Added ID field")
            
            # Add last_updated if missing
            if 'last_updated' not in session and session.get('status') != 'completed':
                session['last_updated'] = session.get('created_at')
                modified = True
                if get_verbose():
                    info(f"Migrated session {session_id}: Added last_updated field")
            
            # Ensure all required fields exist
            required_fields = {
                'created_at': datetime.now().isoformat(),
                'status': 'initialized',
                'steps_completed': [],
                'data': {}
            }
            
            for field, default_value in required_fields.items():
                if field not in session:
                    session[field] = default_value
                    modified = True
                    if get_verbose():
                        info(f"Migrated session {session_id}: Added missing field {field}")
        
        if modified:
            if get_verbose():
                info("Saving migrated sessions...")
            self._save_state()
    
    def _load_state(self):
        """Load the state from the JSON file."""
        try:
            with open(VIDEO_STATE_FILE, 'r') as f:
                self._state = json.load(f)
        except Exception as e:
            if get_verbose():
                error(f"Failed to load state: {str(e)}")
            self._state = {}
    
    def _save_state(self):
        """Save the current state to the JSON file."""
        try:
            with open(VIDEO_STATE_FILE, 'w') as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            if get_verbose():
                error(f"Failed to save state: {str(e)}")
    
    def create_video_session(self, niche: str, language: str) -> str:
        """Create a new video generation session.
        
        Args:
            niche: The content niche
            language: The content language
            
        Returns:
            session_id: Unique identifier for this video generation session
        """
        session_id = str(uuid4())
        self._state[session_id] = {
            "id": session_id,  # Add ID to the session data itself
            "created_at": datetime.now().isoformat(),
            "niche": niche,
            "language": language,
            "status": "initialized",
            "steps_completed": [],
            "data": {}
        }
        self._save_state()
        return session_id
    
    def save_step_result(self, session_id: str, step: str, data: dict) -> None:
        """Save the result of a generation step.
        
        Args:
            session_id: The video session identifier
            step: The step name (e.g., 'topic', 'script', 'metadata', etc.)
            data: The data to save for this step
        """
        if session_id not in self._state:
            if get_verbose():
                error(f"Session {session_id} not found")
            return
        
        self._state[session_id]["steps_completed"].append(step)
        self._state[session_id]["data"][step] = data
        self._state[session_id]["status"] = "in_progress"
        self._state[session_id]["last_updated"] = datetime.now().isoformat()
        self._save_state()
    
    def mark_completed(self, session_id: str, video_path: str) -> None:
        """Mark a video session as completed.
        
        Args:
            session_id: The video session identifier
            video_path: Path to the generated video
        """
        if session_id not in self._state:
            if get_verbose():
                error(f"Session {session_id} not found")
            return
        
        self._state[session_id]["status"] = "completed"
        self._state[session_id]["video_path"] = video_path
        self._state[session_id]["completed_at"] = datetime.now().isoformat()
        self._save_state()
    
    def mark_failed(self, session_id: str, error_message: str) -> None:
        """Mark a video session as failed.
        
        Args:
            session_id: The video session identifier
            error_message: The error message describing the failure
        """
        if session_id not in self._state:
            if get_verbose():
                error(f"Session {session_id} not found")
            return
        
        self._state[session_id]["status"] = "failed"
        self._state[session_id]["error"] = error_message
        self._state[session_id]["failed_at"] = datetime.now().isoformat()
        self._save_state()
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get the state of a video session.
        
        Args:
            session_id: The video session identifier
            
        Returns:
            The session state or None if not found
        """
        return self._state.get(session_id)
    
    def get_incomplete_sessions(self) -> Dict[str, Dict]:
        """Get all sessions that haven't completed successfully.
        
        Returns:
            Dict of session_id to session state for all incomplete sessions
        """
        return {
            session_id: state 
            for session_id, state in self._state.items() 
            if state["status"] in ["initialized", "in_progress", "failed"]
        }
    
    def cleanup_completed_sessions(self, days_old: int = 7) -> None:
        """Remove completed sessions older than specified days.
        
        Args:
            days_old: Number of days after which to remove completed sessions
        """
        now = datetime.now()
        to_remove = []
        
        for session_id, state in self._state.items():
            if state["status"] != "completed":
                continue
            
            completed_at = datetime.fromisoformat(state["completed_at"])
            if (now - completed_at).days > days_old:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self._state[session_id]
        
        if to_remove:
            self._save_state()
            
    def cleanup_incomplete_sessions(self) -> None:
        """Remove all incomplete sessions.
        
        This will remove any session that is not marked as completed,
        including initialized, in_progress, and failed sessions.
        """
        to_remove = []
        
        for session_id, state in self._state.items():
            if state["status"] != "completed":
                to_remove.append(session_id)
        
        if to_remove:
            for session_id in to_remove:
                if get_verbose():
                    info(f"Removing incomplete session: {session_id} (Status: {self._state[session_id]['status']})")
                del self._state[session_id]
            self._save_state() 