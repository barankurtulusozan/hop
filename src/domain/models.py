"""
Vendor-agnostic domain models for the LLM Orchestrator.

Nothing in this file may import an SDK (openai, anthropic, httpx, etc).
Adapters are responsible for translating these into/from vendor payloads.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Role
    content: str


class CompletionRequest(BaseModel):
    """Provider-agnostic completion request. Adapters map this to vendor payloads."""

    model_config = ConfigDict(frozen=True)

    messages: list[Message]
    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0)
    stop_sequences: list[str] = Field(default_factory=list)
    stream: bool = False
    # Free-form provider-specific overrides. Adapters may read this, but
    # orchestrator/domain code must never depend on its contents.
    provider_options: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class FinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class CompletionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str
    token_usage: TokenUsage
    latency_ms: float
    finish_reason: FinishReason
    provider: str
    model: str
    request_id: str


class StreamChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    delta: str
    is_final: bool = False
    finish_reason: FinishReason | None = None
    # Populated only on the final chunk, once usage is known.
    token_usage: TokenUsage | None = None

