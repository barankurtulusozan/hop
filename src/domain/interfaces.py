"""
Core port definition. This is the ONLY contract the orchestrator and business
code are allowed to depend on. No vendor SDK imports permitted here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterable

from src.domain.models import CompletionRequest, CompletionResponse, StreamChunk


class LLMProvider(ABC):
    """Hexagonal port: every vendor adapter (OpenAI, Anthropic, Mock, ...) implements this."""

    #: Short, stable identifier used in telemetry and routing config, e.g. "openai", "anthropic".
    name: str

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a single, non-streaming completion.

        Implementations MUST raise only subclasses of
        `src.domain.exceptions.LLMException` -- vendor exceptions must be
        caught and translated before crossing this boundary.
        """
        raise NotImplementedError

    @abstractmethod
    def stream(self, request: CompletionRequest) -> AsyncIterable[StreamChunk]:
        """Execute a streaming completion, yielding chunks as they arrive.

        Same exception-translation contract as `complete`.
        """
        raise NotImplementedError
