"""
agents/finance
==============
Finance agent package — exposes the A2A-compliant agent and server.

Quick start (standalone A2A server):
    uvicorn agents.finance.a2a_server:app --port 8001

Programmatic use:
    from finagents.finance import FinanceAgent
    from finagents.finance.protocol_models import Task, TaskStatus, Message, TextPart

    agent = FinanceAgent()
    task  = Task(id="t1", status=TaskStatus(state="submitted"),
                 messages=[Message(role="user", parts=[TextPart(text="Mon burn rate...")])])
    result = agent.process_task(task)
"""

from finagents.finance.agent import FinanceAgent
from finagents.finance.protocol_models import (
    Task,
    TaskStatus,
    Message,
    TextPart,
    DataPart,
    Artifact,
    AgentCard,
)

__all__ = [
    "FinanceAgent",
    "Task",
    "TaskStatus",
    "Message",
    "TextPart",
    "DataPart",
    "Artifact",
    "AgentCard",
]
