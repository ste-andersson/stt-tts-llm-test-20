from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Dict, Deque, List, Any

class SessionBuffers:
    def __init__(self, max_items: int = 500):
        self.started_at = time.time()
        self.frontend_chunks: Deque[int] = deque(maxlen=max_items)   # store byte lengths
        self.openai_chunks: Deque[int] = deque(maxlen=max_items)     # store byte lengths (after b64 append)
        self.openai_text: Deque[str] = deque(maxlen=max_items)
        self.frontend_text: Deque[str] = deque(maxlen=max_items)
        self.rt_events: Deque[str] = deque(maxlen=max_items)

class DebugStore:
    def __init__(self):
        self._sessions: Dict[str, SessionBuffers] = {}

    def get_or_create(self, session_id: str) -> SessionBuffers:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionBuffers()
        return self._sessions[session_id]

    def new_session(self) -> str:
        sid = str(uuid.uuid4())
        self._sessions[sid] = SessionBuffers()
        return sid

    def list_sessions(self) -> List[str]:
        return list(self._sessions.keys())

    def reset(self, session_id: str | None = None) -> None:
        if session_id:
            self._sessions[session_id] = SessionBuffers()
        else:
            self._sessions.clear()

store = DebugStore()
