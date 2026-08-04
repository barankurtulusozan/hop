from __future__ import annotations

import uuid
from typing import Any

from src.domain.agent import AgentConfig, AgentResponse
from src.domain.models import CompletionRequest, Message, Role, TokenUsage
from src.memory.manager import MemoryManager
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.tool_runner import ToolOrchestrator
from src.tools.executor import ToolExecutor


class Agent:
    """Stateful agent encapsulating an AgentConfig, LLMOrchestrator, optional ToolExecutor, and MemoryManager."""

    def __init__(
        self,
        config: AgentConfig,
        orchestrator: LLMOrchestrator,
        tool_executor: ToolExecutor | None = None,
        memory_manager: MemoryManager | None = None,
    ):
        self.config = config
        self.orchestrator = orchestrator
        self.tool_executor = tool_executor
        self.memory_manager = memory_manager
        self._tool_runner = (
            ToolOrchestrator(llm_orchestrator=orchestrator, tool_executor=tool_executor)
            if tool_executor
            else None
        )

    async def run(
        self,
        user_input: str,
        session_id: str | None = None,
        system_override: str | None = None,
    ) -> AgentResponse:
        active_session_id = session_id or f"session_{self.config.name}_{uuid.uuid4().hex[:8]}"
        system_prompt = system_override or self.config.system_prompt

        # Manage conversation memory
        if self.memory_manager:
            user_msg = Message(role=Role.USER, content=user_input)
            await self.memory_manager.add_turn(
                session_id=active_session_id,
                message=user_msg,
                system_prompt=system_prompt,
            )
            history_messages = await self.memory_manager.get_messages(
                session_id=active_session_id, query=user_input
            )
        else:
            history_messages = []
            if system_prompt:
                history_messages.append(Message(role=Role.SYSTEM, content=system_prompt))
            history_messages.append(Message(role=Role.USER, content=user_input))

        tools = (
            self.tool_executor.registry.list_tools()
            if self.tool_executor
            else []
        )

        request = CompletionRequest(
            messages=history_messages,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            tools=tools,
        )

        if self._tool_runner and tools:
            response, tool_results = await self._tool_runner.run_with_tools(request)
        else:
            response = await self.orchestrator.complete(request)
            tool_results = []

        assistant_msg = Message(
            role=Role.ASSISTANT,
            content=response.content,
            tool_calls=response.tool_calls,
        )

        if self.memory_manager:
            await self.memory_manager.add_turn(
                session_id=active_session_id,
                message=assistant_msg,
                system_prompt=system_prompt,
            )

        return AgentResponse(
            agent_name=self.config.name,
            message=assistant_msg,
            tool_results=tool_results,
            token_usage=response.token_usage,
            metadata={"session_id": active_session_id, "provider": response.provider},
        )
