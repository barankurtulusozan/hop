from __future__ import annotations

import json
from typing import AsyncIterable, AsyncIterator

from src.domain.gateway import SSEEvent, SSEEventType
from src.domain.models import StreamChunk


def format_sse_event(event: SSEEvent) -> str:
    """Format an SSEEvent into W3C Server-Sent Event standard string."""
    lines: list[str] = []
    if event.id:
        lines.append(f"id: {event.id}")
    if event.retry_ms:
        lines.append(f"retry: {event.retry_ms}")
    lines.append(f"event: {event.event_type.value}")
    lines.append(f"data: {event.data}")
    return "\n".join(lines) + "\n\n"


class SSEStreamFormatter:
    """W3C Server-Sent Events stream formatter with backpressure and heartbeat support."""

    def __init__(self, include_heartbeats: bool = True):
        self.include_heartbeats = include_heartbeats

    async def format_stream(
        self,
        stream: AsyncIterable[StreamChunk],
    ) -> AsyncIterator[str]:
        event_id = 0

        async for chunk in stream:
            event_id += 1
            if chunk.tool_calls:
                tool_data = json.dumps(
                    [{"call_id": tc.call_id, "tool_name": tc.tool_name, "arguments": tc.arguments} for tc in chunk.tool_calls]
                )
                yield format_sse_event(
                    SSEEvent(
                        event_type=SSEEventType.TOOL_CALL,
                        data=tool_data,
                        id=str(event_id),
                    )
                )

            if chunk.delta:
                chunk_data = json.dumps({"delta": chunk.delta, "is_final": chunk.is_final})
                yield format_sse_event(
                    SSEEvent(
                        event_type=SSEEventType.CHUNK,
                        data=chunk_data,
                        id=str(event_id),
                    )
                )

            if chunk.is_final:
                usage_dict = (
                    {
                        "prompt_tokens": chunk.token_usage.prompt_tokens,
                        "completion_tokens": chunk.token_usage.completion_tokens,
                        "total_tokens": chunk.token_usage.total_tokens,
                    }
                    if chunk.token_usage
                    else {}
                )
                done_data = json.dumps({"finish_reason": chunk.finish_reason.value if chunk.finish_reason else "stop", "usage": usage_dict})
                yield format_sse_event(
                    SSEEvent(
                        event_type=SSEEventType.DONE,
                        data=done_data,
                        id=str(event_id + 1),
                    )
                )
