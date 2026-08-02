"""
Immutable configuration for the orchestrator. Values are read once at process
start from environment variables and frozen -- nothing downstream can mutate
config at runtime, which rules out an entire class of "who changed the retry
count mid-request" bugs.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, SecretStr


class ProviderCredentials(BaseModel):
    """
    Immutable secret container. `api_key` is a SecretStr specifically so that
    accidental logging (e.g. `logger.info(f"config={config}")`) or
    repr()/str() in a stack trace prints '**********' instead of the raw key.
    """

    model_config = ConfigDict(frozen=True)

    api_key: SecretStr
    organization_id: str | None = None
    base_url: str | None = None

    def reveal(self) -> str:
        """Explicit, deliberate access to the raw secret. Only adapters call this,
        and only at the point of constructing the vendor SDK client."""
        return self.api_key.get_secret_value()


class RetryConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_retries: int = 3
    initial_delay_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 30.0
    # Full jitter (AWS architecture blog algorithm): actual delay is
    # uniform(0, computed_delay), not just +/- noise on top of it.
    jitter: bool = True
    # Request timeout safety threshold (B-4)
    request_timeout_seconds: float = 30.0
    # Circuit breaker thresholds (B-3)
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_time_seconds: float = 30.0


class ProviderSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    default_provider: str = "openai"
    openai: ProviderCredentials | None = None
    anthropic: ProviderCredentials | None = None


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    providers: ProviderSettings
    retry: RetryConfig = RetryConfig()
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        """
        Build settings from environment variables. Never accepts secrets as
        plain constructor args in application code -- this is the one
        sanctioned entry point that reads raw key material, and it wraps it
        in SecretStr immediately.
        """
        openai_key = os.environ.get("OPENAI_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        return cls(
            providers=ProviderSettings(
                default_provider=os.environ.get("LLM_DEFAULT_PROVIDER", "openai"),
                openai=ProviderCredentials(api_key=SecretStr(openai_key)) if openai_key else None,
                anthropic=ProviderCredentials(api_key=SecretStr(anthropic_key)) if anthropic_key else None,
            ),
            retry=RetryConfig(
                max_retries=int(os.environ.get("LLM_MAX_RETRIES", "3")),
                initial_delay_seconds=float(os.environ.get("LLM_INITIAL_DELAY_SECONDS", "0.5")),
                backoff_multiplier=float(os.environ.get("LLM_BACKOFF_MULTIPLIER", "2.0")),
                max_delay_seconds=float(os.environ.get("LLM_MAX_DELAY_SECONDS", "30.0")),
                request_timeout_seconds=float(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "30.0")),
                circuit_breaker_failure_threshold=int(os.environ.get("LLM_CB_FAILURE_THRESHOLD", "5")),
                circuit_breaker_recovery_time_seconds=float(os.environ.get("LLM_CB_RECOVERY_SECONDS", "30.0")),
            ),
            log_level=os.environ.get("LLM_LOG_LEVEL", "INFO"),
        )

    def __repr__(self) -> str:  # pragma: no cover
        # Explicit safe repr: pydantic's default repr would already mask
        # SecretStr fields, but we spell it out so nobody "fixes" this later
        # by unwrapping .get_secret_value() in a debug log line.
        return (
            f"Settings(default_provider={self.providers.default_provider!r}, "
            f"retry={self.retry!r}, log_level={self.log_level!r})"
        )
