from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpanKind(str, Enum):
    LLM_CALL = "llm_call"
    TOOL_EXECUTION = "tool_execution"
    VECTOR_SEARCH = "vector_search"
    AGENT_TURN = "agent_turn"
    WORKFLOW_NODE = "workflow_node"


class Span(BaseModel):
    model_config = ConfigDict(frozen=True)

    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    name: str
    kind: SpanKind
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: str = "OK"
    error: str | None = None


class CostLimit(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    max_daily_budget_usd: float = 100.0
    max_tokens_per_minute: int = 100000
    current_daily_spend_usd: float = 0.0


class SafetyViolationType(str, Enum):
    PII_LEAK = "pii_leak"
    PROMPT_INJECTION = "prompt_injection"
    COST_EXCEEDED = "cost_exceeded"
    LENGTH_EXCEEDED = "length_exceeded"


class SafetyCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_safe: bool
    violations: list[SafetyViolationType] = Field(default_factory=list)
    sanitized_text: str
    redacted_items_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
