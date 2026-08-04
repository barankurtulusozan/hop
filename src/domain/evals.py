from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvalMetricKind(str, Enum):
    EXACT_MATCH = "exact_match"
    COSINE_RELEVANCE = "cosine_relevance"
    LATENCY_P95 = "latency_p95"
    COST_SCORE = "cost_score"
    TOOL_ACCURACY = "tool_accuracy"


class TestCase(BaseModel):
    __test__ = False
    model_config = ConfigDict(frozen=True)

    test_case_id: str
    input: str
    expected_output: str | None = None
    expected_tools: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    test_case_id: str
    score: float
    passed: bool
    metric_scores: dict[str, float] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)
