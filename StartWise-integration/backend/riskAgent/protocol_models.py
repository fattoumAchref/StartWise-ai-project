"""
agents/risk/protocol_models.py
================================
Google/IBM A2A Protocol data models for the Risk Agent.

Reference: https://google.github.io/A2A/specification

Covers:
  - Part types      : TextPart, DataPart, FilePart
  - Message         : role (user|agent) + parts
  - Artifact        : named task output with parts
  - TaskStatus      : state + timestamp + optional agent message
  - Task            : id + status + message history + artifacts + metadata
  - AgentCard       : agent identity, skills, capabilities
  - JSONRPCError    : standard + A2A-specific error codes
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union


# ── Parts ─────────────────────────────────────────────────────────────────────

@dataclass
class TextPart:
    text: str
    type: Literal["text"] = "text"

    def to_dict(self) -> Dict:
        return {"type": self.type, "text": self.text}


@dataclass
class DataPart:
    data: Dict[str, Any]
    mimeType: str = "application/json"
    type: Literal["data"] = "data"

    def to_dict(self) -> Dict:
        return {"type": self.type, "mimeType": self.mimeType, "data": self.data}


@dataclass
class FilePart:
    file: Dict[str, Any]  # {name, mimeType, bytes | uri}
    type: Literal["file"] = "file"

    def to_dict(self) -> Dict:
        return {"type": self.type, "file": self.file}


Part = Union[TextPart, DataPart, FilePart]


def part_from_dict(d: Dict) -> Part:
    t = d.get("type", "text")
    if t == "data":
        return DataPart(data=d.get("data", {}), mimeType=d.get("mimeType", "application/json"))
    if t == "file":
        return FilePart(file=d.get("file", {}))
    return TextPart(text=d.get("text", ""))


# ── Message ───────────────────────────────────────────────────────────────────

@dataclass
class Message:
    role: Literal["user", "agent"]
    parts: List[Part]

    def to_dict(self) -> Dict:
        return {"role": self.role, "parts": [p.to_dict() for p in self.parts]}

    @classmethod
    def from_dict(cls, d: Dict) -> "Message":
        return cls(
            role=d.get("role", "user"),
            parts=[part_from_dict(p) for p in d.get("parts", [])],
        )

    def get_text(self) -> str:
        """Concatenate all TextPart content."""
        return " ".join(p.text for p in self.parts if isinstance(p, TextPart))

    def get_data(self) -> Optional[Dict]:
        """Return the first DataPart payload, or None."""
        for p in self.parts:
            if isinstance(p, DataPart):
                return p.data
        return None


# ── Artifact ──────────────────────────────────────────────────────────────────

@dataclass
class Artifact:
    name: str
    parts: List[Part]
    description: str = ""
    index: int = 0
    append: bool = False
    lastChunk: bool = True

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parts": [p.to_dict() for p in self.parts],
            "index": self.index,
            "append": self.append,
            "lastChunk": self.lastChunk,
        }


# ── Task ──────────────────────────────────────────────────────────────────────

TaskState = Literal[
    "submitted",
    "working",
    "input-required",
    "completed",
    "failed",
    "canceled",
]


@dataclass
class TaskStatus:
    state: TaskState
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Populated when state == "input-required": agent message asking the caller
    message: Optional[Message] = None

    def to_dict(self) -> Dict:
        d: Dict = {"state": self.state, "timestamp": self.timestamp}
        if self.message:
            d["message"] = self.message.to_dict()
        return d


@dataclass
class Task:
    id: str
    status: TaskStatus
    messages: List[Message] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    sessionId: Optional[str] = None

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> Dict:
        safe_meta = {k: v for k, v in self.metadata.items() if not k.startswith("_")}
        return {
            "id": self.id,
            "sessionId": self.sessionId,
            "status": self.status.to_dict(),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "history": [m.to_dict() for m in self.messages],
            "metadata": safe_meta,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_user_text(self) -> str:
        """Text of the most recent user message."""
        for m in reversed(self.messages):
            if m.role == "user":
                return m.get_text()
        return ""

    def all_user_text(self) -> str:
        """All user messages joined — used to re-parse after clarification rounds."""
        return " | ".join(m.get_text() for m in self.messages if m.role == "user")

    def add_message(self, msg: Message) -> None:
        self.messages.append(msg)


# ── Agent Card ────────────────────────────────────────────────────────────────

@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    inputModes: List[str] = field(default_factory=lambda: ["text/plain"])
    outputModes: List[str] = field(default_factory=lambda: ["application/json"])

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "examples": self.examples,
            "inputModes": self.inputModes,
            "outputModes": self.outputModes,
        }


@dataclass
class AgentCapabilities:
    streaming: bool = True
    pushNotifications: bool = False
    stateTransitionHistory: bool = True

    def to_dict(self) -> Dict:
        return {
            "streaming": self.streaming,
            "pushNotifications": self.pushNotifications,
            "stateTransitionHistory": self.stateTransitionHistory,
        }


@dataclass
class AgentCard:
    name: str
    description: str
    url: str
    version: str
    capabilities: AgentCapabilities
    skills: List[AgentSkill]
    defaultInputModes: List[str] = field(default_factory=lambda: ["text/plain"])
    defaultOutputModes: List[str] = field(default_factory=lambda: ["application/json"])
    authentication: Dict[str, Any] = field(
        default_factory=lambda: {"schemes": [{"type": "none"}]}
    )

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities.to_dict(),
            "skills": [s.to_dict() for s in self.skills],
            "defaultInputModes": self.defaultInputModes,
            "defaultOutputModes": self.defaultOutputModes,
            "authentication": self.authentication,
        }


# ── JSON-RPC 2.0 Errors ───────────────────────────────────────────────────────

@dataclass
class JSONRPCError:
    code: int
    message: str
    data: Any = None

    def to_dict(self) -> Dict:
        d: Dict = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


# Standard JSON-RPC 2.0 errors
JSONRPC_PARSE_ERROR      = JSONRPCError(-32700, "Parse error")
JSONRPC_INVALID_REQUEST  = JSONRPCError(-32600, "Invalid Request")
JSONRPC_METHOD_NOT_FOUND = JSONRPCError(-32601, "Method not found")
JSONRPC_INVALID_PARAMS   = JSONRPCError(-32602, "Invalid params")
JSONRPC_INTERNAL_ERROR   = JSONRPCError(-32603, "Internal error")

# A2A-specific errors (per spec)
A2A_TASK_NOT_FOUND        = JSONRPCError(-32001, "Task not found")
A2A_TASK_NOT_CANCELABLE   = JSONRPCError(-32002, "Task not cancelable")
A2A_PUSH_NOT_SUPPORTED    = JSONRPCError(-32003, "Push notifications not supported")
A2A_UNSUPPORTED_OPERATION = JSONRPCError(-32004, "Unsupported operation")