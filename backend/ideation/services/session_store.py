import json
from pathlib import Path
from threading import Lock

from .schemas import ImageAssetState, QuestionState, SessionState, SourceLink

_PERSIST_FILE = Path(__file__).parent.parent.parent / "ideation_sessions.json"


def _state_from_dict(d: dict) -> SessionState:
    questions = [
        QuestionState(
            question=q["question"],
            response=q.get("response"),
            keywords=q.get("keywords"),
            sources=[SourceLink(**s) for s in q["sources"]] if q.get("sources") else None,
            is_satisfactory=q.get("is_satisfactory", False),
            satisfaction_reason=q.get("satisfaction_reason"),
        )
        for q in d.get("questions", [])
    ]
    return SessionState(
        session_id=d["session_id"],
        description=d["description"],
        questions=questions,
        summary=d.get("summary"),
        background_image=ImageAssetState.from_dict(d.get("background_image")),
    )


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = Lock()
        self._load()

    def _load(self) -> None:
        if _PERSIST_FILE.exists():
            try:
                data = json.loads(_PERSIST_FILE.read_text(encoding="utf-8"))
                for d in data.values():
                    state = _state_from_dict(d)
                    self._sessions[state.session_id] = state
            except Exception:
                pass  # corrupt file — start fresh

    def _flush(self) -> None:
        try:
            _PERSIST_FILE.write_text(
                json.dumps(
                    {sid: s.to_dict() for sid, s in self._sessions.items()},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def create(self, session_id: str, description: str) -> SessionState:
        with self._lock:
            state = SessionState(session_id=session_id, description=description)
            self._sessions[session_id] = state
            self._flush()
            return state

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, state: SessionState) -> SessionState:
        with self._lock:
            self._sessions[state.session_id] = state
            self._flush()
            return state

    def delete(self, session_id: str) -> bool:
        with self._lock:
            removed = self._sessions.pop(session_id, None) is not None
            if removed:
                self._flush()
            return removed


session_store = SessionStore()
