from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    ANONYMOUS = "anonymous"


class Permission(str, Enum):
    LLM_EXECUTE = "llm:execute"
    TOOL_INVOKE = "tool:invoke"
    VECTOR_WRITE = "vector:write"
    VECTOR_READ = "vector:read"
    AGENT_RUN = "agent:run"
    EVAL_RUN = "eval:run"
    CONFIG_MANAGE = "config:manage"


class RateLimitTier(str, Enum):
    FREE = "free"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"


class TenantContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    user_id: str
    roles: list[Role] = Field(default_factory=lambda: [Role.ANONYMOUS])
    permissions: list[Permission] = Field(default_factory=list)
    tier: RateLimitTier = RateLimitTier.STANDARD
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource: str
    required_permissions: list[Permission] = Field(default_factory=list)
