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
