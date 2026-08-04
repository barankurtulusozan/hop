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


