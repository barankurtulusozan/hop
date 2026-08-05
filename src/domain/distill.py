from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrajectoryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    trajectory_id: str
    input_prompt: str
    system_prompt: str = ""
    completion_output: str
    eval_score: float = 1.0
    created_at: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class DistillationDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: list[TrajectoryRecord] = Field(default_factory=list)
    min_score_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
