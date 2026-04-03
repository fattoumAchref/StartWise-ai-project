from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceLink:
    title: str
    url: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
        }


@dataclass
class QuestionState:
    question: str
    response: Optional[str] = None
    keywords: Optional[list[str]] = None
    sources: Optional[list[SourceLink]] = None
    is_satisfactory: bool = False
    satisfaction_reason: Optional[str] = None


@dataclass
class ImageAssetState:
    image_url: Optional[str] = None
    business_idea: Optional[str] = None
    generated_at: Optional[str] = None
    status: Optional[str] = None
    prompt: Optional[str] = None
    filename: Optional[str] = None
    local_path: Optional[str] = None
    file_size: Optional[int] = None
    serve_url: Optional[str] = None
    content_type: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "image_url": self.image_url,
            "business_idea": self.business_idea,
            "generated_at": self.generated_at,
            "status": self.status,
            "prompt": self.prompt,
            "filename": self.filename,
            "local_path": self.local_path,
            "file_size": self.file_size,
            "serve_url": self.serve_url,
            "content_type": self.content_type,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: Optional[dict]) -> Optional["ImageAssetState"]:
        if not payload:
            return None
        return cls(
            image_url=payload.get("image_url"),
            business_idea=payload.get("business_idea"),
            generated_at=payload.get("generated_at"),
            status=payload.get("status"),
            prompt=payload.get("prompt"),
            filename=payload.get("filename"),
            local_path=payload.get("local_path"),
            file_size=payload.get("file_size"),
            serve_url=payload.get("serve_url"),
            content_type=payload.get("content_type"),
            error=payload.get("error"),
        )


@dataclass
class SessionState:
    session_id: str
    description: str
    questions: list[QuestionState] = field(default_factory=list)
    summary: Optional[str] = None
    background_image: Optional[ImageAssetState] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "description": self.description,
            "questions": [
                {
                    "question": q.question,
                    "response": q.response,
                    "keywords": q.keywords,
                    "sources": [item.to_dict() for item in q.sources] if q.sources else None,
                    "is_satisfactory": q.is_satisfactory,
                    "satisfaction_reason": q.satisfaction_reason,
                }
                for q in self.questions
            ],
            "summary": self.summary,
            "background_image": self.background_image.to_dict() if self.background_image else None,
        }
