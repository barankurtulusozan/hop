from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from src.domain.exceptions import MemoryException
from src.domain.memory import ConversationTurn, MemoryStrategy, SessionState
from src.domain.models import CompletionRequest, Message, Role
from src.orchestrator.pipeline import LLMOrchestrator
from src.vector.pipeline import DenseRetriever


def _estimate_message_tokens(msg: Message) -> int:
    # Rule of thumb token estimation: ~4 chars per token + tool call payload overhead
    chars = len(msg.content)
    if msg.tool_calls:
        for tc in msg.tool_calls:
            chars += len(tc.tool_name) + len(str(tc.arguments))
    return max(1, chars // 4)


class MemoryManager:
    """Stateful conversation memory manager supporting sliding window, token budgeting, rolling summarization, and hybrid RAG memory."""

    def __init__(
        self,
        strategy: MemoryStrategy = MemoryStrategy.SLIDING_WINDOW,
        max_window_size: int = 10,
        max_token_budget: int = 2000,
        orchestrator: LLMOrchestrator | None = None,
        retriever: DenseRetriever | None = None,
    ):
        self.strategy = strategy
        self.max_window_size = max_window_size
        self.max_token_budget = max_token_budget
        self.orchestrator = orchestrator
        self.retriever = retriever

        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_session(self, session_id: str, system_prompt: str = "") -> SessionState:
        async with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(
                    session_id=session_id,
                    system_prompt=system_prompt,
                )
            return self._sessions[session_id]

    async def add_turn(
        self,
        session_id: str,
        message: Message,
        metadata: dict[str, Any] | None = None,
        system_prompt: str = "",
    ) -> ConversationTurn:
        turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            message=message,
            timestamp=time.time(),
            metadata=metadata or {},
        )
        async with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(
                    session_id=session_id,
                    system_prompt=system_prompt,
                )
            state = self._sessions[session_id]
            updated_turns = list(state.turns) + [turn]
            self._sessions[session_id] = SessionState(
                session_id=state.session_id,
                system_prompt=system_prompt or state.system_prompt,
                turns=updated_turns,
                summary=state.summary,
                metadata=state.metadata,
            )

        # Trigger auto-summarize if SUMMARIZED strategy and window threshold exceeded
        if self.strategy == MemoryStrategy.SUMMARIZED and len(updated_turns) > self.max_window_size:
            await self.summarize(session_id)

        return turn

    async def summarize(self, session_id: str) -> str:
        if not self.orchestrator:
            raise MemoryException("LLMOrchestrator required for SUMMARIZED memory strategy")

        async with self._lock:
            state = self._sessions.get(session_id)
            if not state or not state.turns:
                return ""

            # Keep the most recent 2 turns, summarize the older turns
            turns_to_summarize = state.turns[:-2]
            turns_to_keep = state.turns[-2:]

            if not turns_to_summarize:
                return state.summary or ""

            formatted_history = "\n".join(
                f"{t.message.role.value}: {t.message.content}" for t in turns_to_summarize
            )
            existing_summary = f"Existing Summary: {state.summary}\n" if state.summary else ""
            prompt = (
                f"{existing_summary}Summarize the following conversation history concisely:\n"
                f"{formatted_history}"
            )

            req = CompletionRequest(
                messages=[Message(role=Role.USER, content=prompt)],
                model="gpt-4o",
                temperature=0.3,
            )

        # Call orchestrator outside lock
        res = await self.orchestrator.complete(req)
        new_summary = res.content.strip()

        async with self._lock:
            state = self._sessions[session_id]
            self._sessions[session_id] = SessionState(
                session_id=state.session_id,
                system_prompt=state.system_prompt,
                turns=turns_to_keep,
                summary=new_summary,
                metadata=state.metadata,
            )

        return new_summary

    async def get_messages(self, session_id: str, query: str | None = None) -> list[Message]:
        async with self._lock:
            state = self._sessions.get(session_id)
            if not state:
                return []

            system_prompt = state.system_prompt
            summary = state.summary
            turns = list(state.turns)

        messages: list[Message] = []
        if system_prompt:
            messages.append(Message(role=Role.SYSTEM, content=system_prompt))

        if self.strategy == MemoryStrategy.FULL_HISTORY:
            messages.extend([t.message for t in turns])
            return messages

        if self.strategy == MemoryStrategy.SLIDING_WINDOW:
            recent_turns = turns[-self.max_window_size :] if len(turns) > self.max_window_size else turns
            messages.extend([t.message for t in recent_turns])
            return messages

        if self.strategy == MemoryStrategy.TOKEN_BUDGET:
            budget = self.max_token_budget - (len(system_prompt) // 4 if system_prompt else 0)
            selected_turns: list[ConversationTurn] = []
            current_tokens = 0
            for t in reversed(turns):
                t_tokens = _estimate_message_tokens(t.message)
                if current_tokens + t_tokens <= budget:
                    selected_turns.insert(0, t)
                    current_tokens += t_tokens
                else:
                    break
            messages.extend([t.message for t in selected_turns])
            return messages

        if self.strategy == MemoryStrategy.SUMMARIZED:
            if summary:
                messages.append(
                    Message(role=Role.SYSTEM, content=f"Prior Conversation Summary: {summary}")
                )
            messages.extend([t.message for t in turns])
            return messages

        if self.strategy == MemoryStrategy.HYBRID_VECTOR:
            # Token budgeted recent turns + retrieved vector memories
            budget = self.max_token_budget // 2
            selected_turns = []
            current_tokens = 0
            for t in reversed(turns):
                t_tokens = _estimate_message_tokens(t.message)
                if current_tokens + t_tokens <= budget:
                    selected_turns.insert(0, t)
                    current_tokens += t_tokens
                else:
                    break

            if query and self.retriever:
                vector_results = await self.retriever.retrieve(query=query, top_k=2)
                if vector_results:
                    context_snippets = "\n".join(
                        res.payload.get("text", "") for res in vector_results
                    )
                    messages.append(
                        Message(
                            role=Role.SYSTEM,
                            content=f"Relevant Memory Context:\n{context_snippets}",
                        )
                    )

            messages.extend([t.message for t in selected_turns])
            return messages

        messages.extend([t.message for t in turns])
        return messages

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
