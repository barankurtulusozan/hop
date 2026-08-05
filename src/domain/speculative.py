from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpeculativeDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_id: str
    prompt: str
    draft_tokens: list[str] = Field(default_factory=list)
    accepted_tokens: list[str] = Field(default_factory=list)
    acceptance_rate: float = 1.0
    latency_savings_pct: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
