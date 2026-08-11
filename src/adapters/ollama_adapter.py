from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import AsyncIterable, Any

from src.domain.exceptions import (
    InvalidRequestError,
    ProviderUnavailable,
    RateLimitExceeded,
)
from src.domain.interfaces import LLMProvider
from src.domain.models import (
    CompletionRequest,
    CompletionResponse,
    FinishReason,
    Message,
    StreamChunk,
    TokenUsage,
)


class OllamaAdapter(LLMProvider):
    """Adapter for running open-weights local LLM inference via Ollama service."""

    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.2:1b",
        timeout_seconds: float = 30.0,
        http_client: Any = None,  # Custom mock/http injector for testing
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    def _format_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        formatted = []
        for msg in messages:
            formatted.append({
                "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                "content": msg.content or "",
            })
        return formatted

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute non-streaming completion against Ollama /api/chat endpoint."""
        start_time = time.perf_counter()
        model = request.model or self.default_model

        payload = {
            "model": model,
            "messages": self._format_messages(request.messages),
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens or 2048,
            },
        }

        # Handle custom HTTP client for testing or execute urllib request
        try:
            if self.http_client:
                res_data = await self.http_client.post(f"{self.base_url}/api/chat", json=payload)
            else:
                req = urllib.request.Request(
                    url=f"{self.base_url}/api/chat",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    res_data = json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitExceeded(provider=self.name) from e
            elif e.code >= 500:
                raise ProviderUnavailable(provider=self.name, status_code=e.code) from e
            else:
                raise InvalidRequestError(provider=self.name, status_code=e.code) from e
        except Exception as e:
            raise ProviderUnavailable(f"Ollama connection error: {e}", provider=self.name) from e

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        message_obj = res_data.get("message", {})
        content = message_obj.get("content", "")

        prompt_tokens = res_data.get("prompt_eval_count", 0)
        completion_tokens = res_data.get("eval_count", 0)

        import uuid

        return CompletionResponse(
            content=content,
            token_usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
            latency_ms=elapsed_ms,
            finish_reason=FinishReason.STOP,
            provider=self.name,
            model=model,
            request_id=f"ollama_{uuid.uuid4().hex[:12]}",
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterable[StreamChunk]:
        """Stream chunks from Ollama endpoint."""
        # For stream compatibility in unit/integration environments without active local daemon,
        # fallback to single chunk if complete succeeds
        resp = await self.complete(request)
        yield StreamChunk(
            delta=resp.content,
            is_final=True,
            finish_reason=FinishReason.STOP,
            token_usage=resp.token_usage,
        )
