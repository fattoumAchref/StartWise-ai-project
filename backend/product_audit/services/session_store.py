from threading import Lock

from .schemas import AuditSessionState


class ProductAuditSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, AuditSessionState] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> AuditSessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, state: AuditSessionState) -> AuditSessionState:
        with self._lock:
            state.touch()
            self._sessions[state.session_id] = state
            return state

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None


product_audit_session_store = ProductAuditSessionStore()
