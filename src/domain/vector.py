from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.models import TokenUsage


class DistanceMetric(str, Enum):
    COSINE = "cosine"
    DOT_PRODUCT = "dot_product"
    EUCLIDEAN = "euclidean"


class FilterOperator(str, Enum):
    EQ = "$eq"
    NE = "$ne"
    GT = "$gt"
    GTE = "$gte"
    LT = "$lt"
    LTE = "$lte"
    IN = "$in"
    NIN = "$nin"
    CONTAINS = "$contains"


class MetadataFilter(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    operator: FilterOperator = FilterOperator.EQ
    value: Any


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_texts: list[str]
    model: str = "text-embedding-3-small"
    user: str | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)


class EmbeddingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    embeddings: list[list[float]]
    model: str
    token_usage: TokenUsage


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    doc_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    start_char: int = 0
    end_char: int = 0
    chunk_index: int = 0


class VectorRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    vector: list[float]
    payload: dict[str, Any] = Field(default_factory=dict)


class VectorSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    score: float
    payload: dict[str, Any] = Field(default_factory=dict)
    vector: list[float] | None = None
