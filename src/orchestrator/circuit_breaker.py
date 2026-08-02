"""
Circuit Breaker implementation to prevent cascading failure amplification.
"""

from __future__ import annotations

from enum import Enum
import time
from typing import Callable

from src.domain.exceptions import LLMException


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(LLMException):
    """Raised when request is rejected immediately because circuit breaker is OPEN."""

    def __init__(self, provider: str, message: str = "Circuit breaker is OPEN"):
        super().__init__(message, provider=provider, retryable=False)


class CircuitBreaker:
    """
    Per-provider circuit breaker state machine.

    CLOSED -> (consecutive failures >= threshold) -> OPEN
    OPEN -> (recovery_time_seconds elapsed) -> HALF_OPEN
    HALF_OPEN -> (success) -> CLOSED
    HALF_OPEN -> (failure) -> OPEN
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 5,
        recovery_time_seconds: float = 30.0,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds
        self._time_fn = time_fn

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            now = self._time_fn()
            if now - self.last_failure_time >= self.recovery_time_seconds:
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN allows a single probe attempt
        return True

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = self._time_fn()
        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
