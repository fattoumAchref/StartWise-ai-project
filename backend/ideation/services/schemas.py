from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuestionState:
    question: str
    response: Optional[str] = None
    keywords: Optional[list[str]] = None
    is_satisfactory: bool = False
    satisfaction_reason: Optional[str] = None


@dataclass
class SessionState:
    session_id: str
    description: str
    questions: list[QuestionState] = field(default_factory=list)
    summary: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "description": self.description,
            "questions": [
                {
                    "question": q.question,
                    "response": q.response,
                    "keywords": q.keywords,
                    "is_satisfactory": q.is_satisfactory,
                    "satisfaction_reason": q.satisfaction_reason,
                }
                for q in self.questions
            ],
            "summary": self.summary,
        }
