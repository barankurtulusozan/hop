from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SSEEventType(str, Enum):
    CHUNK = "chunk"
    TOOL_CALL = "tool_call"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    DONE = "done"


class SSEEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: SSEEventType
    data: str
    id: str | None = None
    retry_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
