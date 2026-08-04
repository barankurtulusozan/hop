from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from src.domain.models import Message, TokenUsage
from src.domain.tools import ToolResult


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    system_prompt: str = ""
    model: str = "gpt-4o"
    provider: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0)


class AgentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_name: str
    message: Message
    tool_results: list[ToolResult] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    workflow_id: str
    status: WorkflowStatus
    outputs: dict[str, Any] = Field(default_factory=dict)
    history: list[AgentResponse] = Field(default_factory=list)
    error: str | None = None
