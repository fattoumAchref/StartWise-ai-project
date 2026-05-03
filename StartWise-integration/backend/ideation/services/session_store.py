from threading import Lock

from .schemas import SessionState


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = Lock()

    def create(self, session_id: str, description: str) -> SessionState:
        with self._lock:
            state = SessionState(session_id=session_id, description=description)
            self._sessions[session_id] = state
            return state

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, state: SessionState) -> SessionState:
        with self._lock:
            self._sessions[state.session_id] = state
            return state

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None


session_store = SessionStore()
