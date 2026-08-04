from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RoutingStrategy(str, Enum):
    PRIORITY_FALLBACK = "priority_fallback"
    LOWEST_LATENCY = "lowest_latency"
    LOWEST_COST = "lowest_cost"
    ROUND_ROBIN = "round_robin"


class ProviderHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    is_circuit_open: bool = False
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
