import pytest
from pydantic import SecretStr

from src.adapters.mock_adapter import MockAdapter, rate_limit_failure
from src.config import ProviderCredentials
from src.domain.exceptions import RateLimitExceeded
from src.domain.models import CompletionRequest, Message, Role


def test_completion_request_is_frozen():
    req = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="gpt-4o")
    with pytest.raises(Exception):
        req.model = "other-model"  # type: ignore[misc]


def test_credentials_never_expose_raw_key_in_repr():
    creds = ProviderCredentials(api_key=SecretStr("sk-super-secret-value"))
    assert "sk-super-secret-value" not in repr(creds)
    assert "sk-super-secret-value" not in str(creds)
    assert creds.reveal() == "sk-super-secret-value"


@pytest.mark.asyncio
async def test_mock_adapter_deterministic_success():
    adapter = MockAdapter(response_content="hello world")
    req = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")
    resp = await adapter.complete(req)
    assert resp.content == "hello world"
    assert resp.provider == "mock"
    assert resp.token_usage.total_tokens == 15


@pytest.mark.asyncio
async def test_mock_adapter_scripted_failure_then_success():
    adapter = MockAdapter(failure_script=[rate_limit_failure(), None])
    req = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")

    with pytest.raises(RateLimitExceeded):
        await adapter.complete(req)

    resp = await adapter.complete(req)
    assert resp.content == "mock completion"
    assert adapter.call_count == 2


@pytest.mark.asyncio
async def test_mock_adapter_streaming_yields_final_chunk_with_usage():
    adapter = MockAdapter(response_content="a b c")
    req = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")
    chunks = [c async for c in adapter.stream(req)]
    assert len(chunks) == 3
    assert chunks[-1].is_final is True
    assert chunks[-1].token_usage is not None
