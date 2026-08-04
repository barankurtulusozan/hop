import pytest

from src.domain.gateway import SSEEvent, SSEEventType
from src.domain.models import FinishReason, StreamChunk, TokenUsage
from src.gateway.streaming import SSEStreamFormatter, format_sse_event


def test_format_sse_event():
    evt = SSEEvent(event_type=SSEEventType.CHUNK, data='{"delta":"hi"}', id="1", retry_ms=5000)
    formatted = format_sse_event(evt)

    assert "id: 1\n" in formatted
    assert "retry: 5000\n" in formatted
    assert "event: chunk\n" in formatted
    assert 'data: {"delta":"hi"}\n\n' in formatted


@pytest.mark.asyncio
async def test_sse_stream_formatter():
    formatter = SSEStreamFormatter()

    async def mock_chunk_generator():
        yield StreamChunk(delta="Hello ")
        yield StreamChunk(delta="world!")
        yield StreamChunk(
            delta="",
            is_final=True,
            finish_reason=FinishReason.STOP,
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=2),
        )

    output_lines: list[str] = []
    async for sse_str in formatter.format_stream(mock_chunk_generator()):
        output_lines.append(sse_str)

    assert len(output_lines) == 3
    assert "event: chunk\n" in output_lines[0]
    assert "Hello " in output_lines[0]
    assert "event: done\n" in output_lines[2]
    assert "prompt_tokens" in output_lines[2]
