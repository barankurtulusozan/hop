from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator

from src.domain.observability import Span, SpanKind


class Tracer:
    """Thread-safe, task-aware OpenTelemetry-compatible distributed tracing collector."""

    def __init__(self):
        self._spans: dict[str, Span] = {}
        self._lock = asyncio.Lock()

    async def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.LLM_CALL,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        t_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        s_id = f"span_{uuid.uuid4().hex[:8]}"
        span = Span(
            span_id=s_id,
            trace_id=t_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_time=time.time(),
            attributes=attributes or {},
        )
        async with self._lock:
            self._spans[s_id] = span
        return span

    async def end_span(
        self,
        span_id: str,
        status: str = "OK",
        error: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        async with self._lock:
            if span_id not in self._spans:
                raise ValueError(f"Span ID '{span_id}' not found in active tracer")

            existing = self._spans[span_id]
            end_time = time.time()
            duration_ms = round((end_time - existing.start_time) * 1000, 3)

            merged_attrs = dict(existing.attributes)
            if attributes:
                merged_attrs.update(attributes)

            updated = Span(
                span_id=existing.span_id,
                trace_id=existing.trace_id,
                parent_span_id=existing.parent_span_id,
                name=existing.name,
                kind=existing.kind,
                start_time=existing.start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                attributes=merged_attrs,
                status=status,
                error=error,
            )
            self._spans[span_id] = updated
            return updated

    async def export_spans(self, trace_id: str | None = None) -> list[Span]:
        async with self._lock:
            if trace_id:
                return [s for s in self._spans.values() if s.trace_id == trace_id]
            return list(self._spans.values())

    @asynccontextmanager
    async def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.LLM_CALL,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> AsyncIterator[Span]:
        span_obj = await self.start_span(
            name=name,
            kind=kind,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            attributes=attributes,
        )
        try:
            yield span_obj
            await self.end_span(span_id=span_obj.span_id, status="OK")
        except Exception as exc:
            await self.end_span(span_id=span_obj.span_id, status="ERROR", error=str(exc))
            raise
