import pytest
from unittest.mock import AsyncMock
from src.adapters.ollama_adapter import OllamaAdapter
from src.domain.exceptions import ProviderUnavailable
from src.domain.models import CompletionRequest, Message, Role


@pytest.mark.asyncio
async def test_ollama_adapter_complete_success():
    mock_client = AsyncMock()
    mock_client.post.return_value = {
        "model": "llama3.2:1b",
        "message": {"role": "assistant", "content": "Hello from local Ollama model!"},
        "prompt_eval_count": 12,
        "eval_count": 8,
        "done": True,
    }

    adapter = OllamaAdapter(http_client=mock_client)
    req = CompletionRequest(
        messages=[Message(role=Role.USER, content="Hello!")],
        model="llama3.2:1b",
    )

    response = await adapter.complete(req)
    assert response.content == "Hello from local Ollama model!"
    assert response.provider == "ollama"
    assert response.token_usage.prompt_tokens == 12
    assert response.token_usage.completion_tokens == 8


@pytest.mark.asyncio
async def test_ollama_adapter_stream():
    mock_client = AsyncMock()
    mock_client.post.return_value = {
        "model": "llama3.2:1b",
        "message": {"role": "assistant", "content": "Streaming token test"},
        "prompt_eval_count": 5,
        "eval_count": 3,
        "done": True,
    }

    adapter = OllamaAdapter(http_client=mock_client)
    req = CompletionRequest(
        messages=[Message(role=Role.USER, content="Test stream")],
        model="llama3.2:1b",
    )

    chunks = []
    async for chunk in adapter.stream(req):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].delta == "Streaming token test"
    assert chunks[0].is_final is True


@pytest.mark.asyncio
async def test_ollama_adapter_connection_failure():
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Connection refused on port 11434")

    adapter = OllamaAdapter(http_client=mock_client)
    req = CompletionRequest(
        messages=[Message(role=Role.USER, content="Test failure")],
        model="llama3.2:1b",
    )

    with pytest.raises(ProviderUnavailable):
        await adapter.complete(req)
