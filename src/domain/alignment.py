from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlignmentStatus(str, Enum):
    ALIGNED = "aligned"
    VIOLATION_BLOCKED = "violation_blocked"
    SANITIZED = "sanitized"


class AlignmentPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str
    forbidden_terms: list[str] = Field(default_factory=list)
    toxicity_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class AlignmentVerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: AlignmentStatus
    is_aligned: bool
    violations: list[str] = Field(default_factory=list)
    sanitized_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
