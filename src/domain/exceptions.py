"""
Domain exception hierarchy for the LLM Orchestrator.

These exceptions are the ONLY error contract that adapters are allowed to
raise across the port boundary. Vendor-specific exceptions (openai.APIError,
anthropic.APIStatusError, etc.) must be caught and translated inside the
adapter layer -- they must never leak into orchestrator or business code.
"""

from __future__ import annotations


class LLMException(Exception):
    """Base class for all domain-level LLM errors."""

    def __init__(self, message: str, *, provider: str | None = None, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.__class__.__name__}(provider={self.provider!r}, retryable={self.retryable}, message={self.message!r})"


class RateLimitExceeded(LLMException):
    """Raised on HTTP 429 / provider-reported rate limiting. Always retryable."""

    def __init__(self, message: str = "Rate limit exceeded", *, provider: str | None = None,
                 retry_after_seconds: float | None = None):
        super().__init__(message, provider=provider, retryable=True)
        self.retry_after_seconds = retry_after_seconds


class ProviderUnavailable(LLMException):
    """Raised on 5xx / connection-level failures. Retryable."""

    def __init__(self, message: str = "Provider unavailable", *, provider: str | None = None,
                 status_code: int | None = None):
        super().__init__(message, provider=provider, retryable=True)
        self.status_code = status_code


class InvalidRequestError(LLMException):
    """Raised on 4xx (excluding 429) -- malformed request, bad model name, etc.

    Never retryable: retrying an invalid request produces the same failure.
    """

    def __init__(self, message: str = "Invalid request", *, provider: str | None = None,
                 status_code: int | None = None):
        super().__init__(message, provider=provider, retryable=False)
        self.status_code = status_code


class RetryBudgetExhausted(LLMException):
    """Raised by the orchestrator when all configured retry attempts are used up."""

    def __init__(self, message: str = "Retry budget exhausted", *, provider: str | None = None,
                 attempts: int = 0, last_error: Exception | None = None):
        super().__init__(message, provider=provider, retryable=False)
        self.attempts = attempts
        self.last_error = last_error


class VectorException(LLMException):
    """Base exception for all vector operations and RAG errors."""

    def __init__(self, message: str = "Vector error", *, provider: str | None = None, retryable: bool = False):
        super().__init__(message, provider=provider, retryable=retryable)


class EmbeddingException(VectorException):
    """Raised when an embedding provider fails to generate vector embeddings."""

    def __init__(self, message: str = "Embedding generation failed", *, provider: str | None = None, retryable: bool = True):
        super().__init__(message, provider=provider, retryable=retryable)


class VectorStoreException(VectorException):
    """Raised on vector store operations (indexing, search, query, invalid vectors)."""

    def __init__(self, message: str = "Vector store error", *, provider: str | None = None, retryable: bool = False):
        super().__init__(message, provider=provider, retryable=retryable)


class ChunkingException(VectorException):
    """Raised when document splitting or chunking fails."""

    def __init__(self, message: str = "Document chunking failed"):
        super().__init__(message, retryable=False)


class AgentException(LLMException):
    """Base exception for agent and workflow execution errors."""

    def __init__(self, message: str = "Agent error", *, provider: str | None = None, retryable: bool = False):
        super().__init__(message, provider=provider, retryable=retryable)


class MemoryException(AgentException):
    """Raised when memory management or turn compaction fails."""

    def __init__(self, message: str = "Memory error"):
        super().__init__(message, retryable=False)


class WorkflowException(AgentException):
    """Raised on workflow graph execution, cycle limits, or routing failures."""

    def __init__(self, message: str = "Workflow execution error"):
        super().__init__(message, retryable=False)


class ObservabilityException(LLMException):
    """Base exception for tracing, cost guardrails, and telemetry errors."""

    def __init__(self, message: str = "Observability error", *, provider: str | None = None, retryable: bool = False):
        super().__init__(message, provider=provider, retryable=retryable)


class CostBudgetExceeded(ObservabilityException):
    """Raised when tenant/user daily dollar budget or per-minute token rate limit is breached."""

    def __init__(self, message: str = "Cost budget exceeded", *, tenant_id: str | None = None):
        super().__init__(message, retryable=False)
        self.tenant_id = tenant_id


class SafetyViolationError(ObservabilityException):
    """Raised when prompt injection or toxic content violates safety guardrails."""

    def __init__(self, message: str = "Safety policy violation"):
        super().__init__(message, retryable=False)


class GatewayException(LLMException):
    """Raised on streaming SSE gateway, backpressure, or connection errors."""

    def __init__(self, message: str = "Streaming gateway error"):
        super().__init__(message, retryable=False)


class RouterException(LLMException):
    """Raised on dynamic provider fallback routing failures or when all providers are unavailable."""

    def __init__(self, message: str = "Dynamic routing failed"):
        super().__init__(message, retryable=True)


class QueueException(LLMException):
    """Raised on async queue worker failures or task dead-lettering."""

    def __init__(self, message: str = "Async queue task error"):
        super().__init__(message, retryable=False)


class SecurityException(LLMException):
    """Base exception for authentication, authorization, and tenant security policy violations."""

    def __init__(self, message: str = "Security exception", *, provider: str | None = None, retryable: bool = False):
        super().__init__(message, provider=provider, retryable=retryable)


class AuthenticationError(SecurityException):
    """Raised when an API Bearer token or credentials are missing or invalid."""

    def __init__(self, message: str = "Authentication failed: invalid token"):
        super().__init__(message, retryable=False)


class AuthorizationError(SecurityException):
    """Raised when an authenticated tenant/user lacks required PBAC permissions."""

    def __init__(self, message: str = "Authorization failed: permission denied"):
        super().__init__(message, retryable=False)


class RateLimitViolationError(SecurityException):
    """Raised when a tenant breaches requests-per-minute (RPM) rate limits."""

    def __init__(self, message: str = "Rate limit breached"):
        super().__init__(message, retryable=True)


class CacheException(LLMException):
    """Raised on semantic vector cache operation failures."""

    def __init__(self, message: str = "Semantic cache error"):
        super().__init__(message, retryable=False)


class MeshException(LLMException):
    """Raised when self-healing agent mesh fails auto-remediation."""

    def __init__(self, message: str = "Self-healing mesh error"):
        super().__init__(message, retryable=False)


class DistillationException(LLMException):
    """Raised on model distillation trajectory dataset harvesting errors."""

    def __init__(self, message: str = "Trajectory distillation error"):
        super().__init__(message, retryable=False)


class FederationException(LLMException):
    """Raised on multi-region active-active federation or Raft consensus failures."""

    def __init__(self, message: str = "Federation error"):
        super().__init__(message, retryable=True)


class VaultException(LLMException):
    """Raised on zero-trust key vault encryption/decryption or key isolation failures."""

    def __init__(self, message: str = "Key vault error"):
        super().__init__(message, retryable=False)


class SpeculativeException(LLMException):
    """Raised on speculative draft verification or token acceptance failures."""

    def __init__(self, message: str = "Speculative execution error"):
        super().__init__(message, retryable=False)


class AlignmentViolationError(LLMException):
    """Raised when completion text violates RLHF/DPO model alignment policies."""

    def __init__(self, message: str = "Model alignment policy breach"):
        super().__init__(message, retryable=False)








