from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    HEALED = "healed"


class HealingPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_attempts: int = Field(default=2, ge=1)
    fallback_node_id: str | None = None


class MeshNodeState(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    health: NodeHealth = NodeHealth.HEALTHY
    error_count: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
