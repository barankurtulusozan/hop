from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CacheStatus(str, Enum):
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"


class SemanticCacheConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    similarity_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    ttl_seconds: int = Field(default=86400, ge=0)


class CacheEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    prompt: str
    embedding: list[float]
    response: Any
    created_at: float


class CacheResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CacheStatus
    entry: CacheEntry | None = None
    similarity_score: float = 0.0
