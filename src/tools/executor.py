"""
Safe Tool Execution Sandbox with timeout protection, exception isolation, and latency timing.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any

from src.domain.tools import ToolCall, ToolResult, ToolValidationError
from src.tools.registry import ToolRegistry


class ToolExecutor:
    """
    Sandboxed execution engine.

    Guarantees:
    - Zero unhandled exceptions leak outside `execute()` (all failures become ToolResult with is_error=True).
    - Per-tool timeout protection (`timeout_seconds`).
    - Sync and Async handler execution support.
    - Argument validation before invocation.
    - Latency measurement (`duration_ms`).
    """

    def __init__(self, registry: ToolRegistry, default_timeout_seconds: float = 10.0):
        self._registry = registry
        self._default_timeout_seconds = default_timeout_seconds

    @property
    def registry(self) -> ToolRegistry:
        """Return the underlying ToolRegistry instance."""
        return self._registry

    async def execute(self, tool_call: ToolCall, timeout_seconds: float | None = None) -> ToolResult:
        start_time = time.perf_counter()
        timeout = timeout_seconds or self._default_timeout_seconds

        # 1. Lookup & Argument Validation
        try:
            tool_def = self._registry.get_tool(tool_call.tool_name)
            validated_args = self._registry.validate_arguments(tool_call.tool_name, tool_call.arguments)
        except ToolValidationError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                result=None,
                error=exc.message,
                is_error=True,
                duration_ms=round(duration_ms, 2),
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                result=None,
                error=str(exc),
                is_error=True,
                duration_ms=round(duration_ms, 2),
            )

        if tool_def.handler is None:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                result=None,
                error=f"No executable handler registered for tool '{tool_call.tool_name}'.",
                is_error=True,
                duration_ms=round(duration_ms, 2),
            )

        # 2. Sandboxed Execution
        try:
            async with asyncio.timeout(timeout):
                if inspect.iscoroutinefunction(tool_def.handler):
                    raw_result = await tool_def.handler(**validated_args)
                else:
                    raw_result = await asyncio.to_thread(tool_def.handler, **validated_args)
        except TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                result=None,
                error=f"Tool execution timed out after {timeout}s.",
                is_error=True,
                duration_ms=round(duration_ms, 2),
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                result=None,
                error=f"Tool runtime exception: {exc}",
                is_error=True,
                duration_ms=round(duration_ms, 2),
            )

        duration_ms = (time.perf_counter() - start_time) * 1000
        return ToolResult(
            call_id=tool_call.call_id,
            tool_name=tool_call.tool_name,
            result=raw_result,
            error=None,
            is_error=False,
            duration_ms=round(duration_ms, 2),
        )
