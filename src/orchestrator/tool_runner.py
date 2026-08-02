"""
Agentic Tool Execution Orchestrator & Auto-Correction Re-prompt Loop.
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.models import (
    CompletionRequest,
    CompletionResponse,
    FinishReason,
    Message,
    Role,
)
from src.domain.tools import ToolCall, ToolResult
from src.orchestrator.pipeline import LLMOrchestrator
from src.tools.executor import ToolExecutor

logger = logging.getLogger("llm_orchestrator.tools")


class ToolOrchestrator:
    """
    Orchestrates LLM completion requests requiring tool execution and auto-correction.

    Features:
    - Runs LLM completion with registered tools.
    - Intercepts tool calls and executes them via `ToolExecutor`.
    - Automatically feeds execution results back to the LLM as `Role.TOOL` messages.
    - If a tool argument fails Pydantic validation or crashes during execution,
      it constructs an explicit error turn and re-prompts the LLM to self-correct (up to `max_tool_retries`).
    """

    def __init__(
        self,
        llm_orchestrator: LLMOrchestrator,
        tool_executor: ToolExecutor,
        max_tool_retries: int = 3,
    ):
        self._llm = llm_orchestrator
        self._executor = tool_executor
        self._max_tool_retries = max_tool_retries

    async def run_with_tools(
        self,
        request: CompletionRequest,
        provider_name: str | None = None,
    ) -> tuple[CompletionResponse, list[ToolResult]]:
        """
        Execute completion with tool support, running tool calls and auto-correction loops.

        Returns (final_completion_response, list_of_executed_tool_results).
        """
        current_messages = list(request.messages)
        executed_results: list[ToolResult] = []
        retries = 0

        while retries <= self._max_tool_retries:
            current_request = request.model_copy(update={"messages": current_messages})
            response = await self._llm.complete(current_request, provider_name=provider_name)

            if not response.tool_calls:
                # No tools requested -- conversation turn complete
                return response, executed_results

            logger.info(
                "tool_calls_requested",
                extra={
                    "tool_calls_count": len(response.tool_calls),
                    "tools": [tc.tool_name for tc in response.tool_calls],
                    "retry_turn": retries,
                },
            )

            # Record assistant turn with tool calls
            current_messages.append(
                Message(
                    role=Role.ASSISTANT,
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            has_error = False
            for tool_call in response.tool_calls:
                result = await self._executor.execute(tool_call)
                executed_results.append(result)

                if result.is_error:
                    has_error = True
                    error_msg = f"Tool '{tool_call.tool_name}' execution failed: {result.error}"
                    current_messages.append(
                        Message(
                            role=Role.TOOL,
                            tool_call_id=tool_call.call_id,
                            name=tool_call.tool_name,
                            content=error_msg,
                        )
                    )
                else:
                    result_content = str(result.result) if result.result is not None else "Success"
                    current_messages.append(
                        Message(
                            role=Role.TOOL,
                            tool_call_id=tool_call.call_id,
                            name=tool_call.tool_name,
                            content=result_content,
                        )
                    )

            if not has_error:
                # All tool calls in this turn succeeded. Send results back for final LLM response
                final_request = request.model_copy(update={"messages": current_messages})
                final_response = await self._llm.complete(final_request, provider_name=provider_name)
                return final_response, executed_results

            # Validation or execution error occurred: trigger self-correction re-prompt attempt
            retries += 1
            logger.warning(
                "tool_call_error_triggering_reprompt",
                extra={"retry_turn": retries, "max_retries": self._max_tool_retries},
            )

        # Retries exhausted -- return last response with error results
        return response, executed_results
