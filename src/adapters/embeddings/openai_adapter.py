from __future__ import annotations

from typing import Any

from src.domain.exceptions import (
    EmbeddingException,
    InvalidRequestError,
    ProviderUnavailable,
    RateLimitExceeded,
)
from src.domain.interfaces import EmbeddingProvider
from src.domain.models import TokenUsage
from src.domain.vector import EmbeddingRequest, EmbeddingResponse

try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENAI_AVAILABLE = False
    AsyncOpenAI = Any  # type: ignore


class OpenAIEmbeddingAdapter(EmbeddingProvider):
    """OpenAI API implementation of the EmbeddingProvider hexagonal port."""

    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "text-embedding-3-small",
        dimension: int = 1536,
        client: AsyncOpenAI | None = None,
    ):
        if not OPENAI_AVAILABLE and client is None:
            raise ImportError(
                "The 'openai' package is required to use OpenAIEmbeddingAdapter. "
                "Install it with `pip install openai` or `pip install .[openai]`."
            )
        self.default_model = default_model
        self._dimension = dimension
        self._client = client or AsyncOpenAI(api_key=api_key)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        model = request.model or self.default_model
        try:
            kwargs: dict[str, Any] = {
                "input": request.input_texts,
                "model": model,
            }
            if request.user:
                kwargs["user"] = request.user
            kwargs.update(request.provider_options)

            res = await self._client.embeddings.create(**kwargs)

            embeddings = [data.embedding for data in res.data]
            prompt_tokens = res.usage.prompt_tokens if res.usage else 0

            return EmbeddingResponse(
                embeddings=embeddings,
                model=model,
                token_usage=TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=0),
            )
        except Exception as e:
            if not OPENAI_AVAILABLE:
                raise EmbeddingException(f"OpenAI SDK unavailable: {e}", provider=self.name) from e
            if isinstance(e, openai.RateLimitError):
                raise RateLimitExceeded(
                    message=str(e),
                    provider=self.name,
                ) from e
            if isinstance(e, (openai.AuthenticationError, openai.BadRequestError)):
                raise InvalidRequestError(
                    message=str(e),
                    provider=self.name,
                ) from e
            if isinstance(e, (openai.APIConnectionError, openai.InternalServerError)):
                raise ProviderUnavailable(
                    message=str(e),
                    provider=self.name,
                ) from e
            raise EmbeddingException(
                message=f"OpenAI embedding generation failed: {e}",
                provider=self.name,
            ) from e
