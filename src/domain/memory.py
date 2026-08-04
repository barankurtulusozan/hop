from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.models import Message


class MemoryStrategy(str, Enum):
    FULL_HISTORY = "full_history"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUDGET = "token_budget"
    SUMMARIZED = "summarized"
    HYBRID_VECTOR = "hybrid_vector"


class ConversationTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    turn_id: str
    message: Message
    timestamp: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    system_prompt: str = ""
    turns: list[ConversationTurn] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
