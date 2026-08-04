from __future__ import annotations

from enum import Enum, IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskPriority(IntEnum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class QueueTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED
    attempts: int = 0
    max_retries: int = 3
    result: Any = None
    error: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
