from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CommandResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    command: str
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    exit_code: int = 0
