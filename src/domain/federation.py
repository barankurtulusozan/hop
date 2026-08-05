from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeStatus(str, Enum):
    ACTIVE = "active"
    STANDBY = "standby"
    UNREACHABLE = "unreachable"


class ConsensusRole(str, Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class RegionNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    region_id: str
    endpoint: str
    latency_ms: float = 0.0
    status: NodeStatus = NodeStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class FederatedConsensusState(BaseModel):
    model_config = ConfigDict(frozen=True)

    term: int = 1
    leader_id: str | None = None
    role: ConsensusRole = ConsensusRole.FOLLOWER
    nodes: list[str] = Field(default_factory=list)


class ZeroTrustKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    key_id: str
    algorithm: str = "AES-256-GCM"
    secret_bytes: bytes
    created_at: float = 0.0
