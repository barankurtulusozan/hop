from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from typing import Any, Awaitable, Callable

from src.agent.agent import Agent
from src.domain.agent import AgentResponse, WorkflowResult, WorkflowStatus
from src.domain.exceptions import WorkflowException

logger = logging.getLogger("llm_orchestrator.workflow")


class WorkflowNode:
    """Represents a discrete step in a workflow execution graph."""

    def __init__(self, name: str, action: Agent | Callable[..., Any]):
        self.name = name
        self.action = action

    async def execute(self, state: dict[str, Any]) -> tuple[dict[str, Any], AgentResponse | None]:
        if isinstance(self.action, Agent):
            # Format user prompt from input state
            user_input = state.get("input", state.get("query", str(state)))
            session_id = state.get("session_id")
            agent_resp = await self.action.run(user_input=user_input, session_id=session_id)

            new_state = dict(state)
            new_state[f"{self.name}_output"] = agent_resp.message.content
            new_state["last_output"] = agent_resp.message.content
            return new_state, agent_resp

        if callable(self.action):
            res = self.action(state)
            if inspect.isawaitable(res):
                res = await res
            new_state = dict(state)
            if isinstance(res, dict):
                new_state.update(res)
            else:
                new_state[f"{self.name}_output"] = res
                new_state["last_output"] = res
            return new_state, None

        raise WorkflowException(f"Unsupported action type in node '{self.name}': {type(self.action)}")


class WorkflowEdge:
    """Defines a directed transition between workflow nodes with an optional condition predicate."""

    def __init__(
        self,
        source: str,
        target: str,
        condition: Callable[[dict[str, Any]], bool] | None = None,
    ):
        self.source = source
        self.target = target
        self.condition = condition

    def evaluate(self, state: dict[str, Any]) -> bool:
        if self.condition is None:
            return True
        try:
            return bool(self.condition(state))
        except Exception as e:
            logger.warning(f"Error evaluating workflow edge condition ({self.source} -> {self.target}): {e}")
            return False


class WorkflowGraph:
    """Directed workflow graph orchestrating multi-agent, sequential, parallel, and conditional execution paths."""

    def __init__(self, max_steps: int = 50):
        self.max_steps = max_steps
        self.nodes: dict[str, WorkflowNode] = {}
        self.edges: list[WorkflowEdge] = []
        self.entry_point: str | None = None

    def add_node(self, name: str, action: Agent | Callable[..., Any]) -> WorkflowGraph:
        if name in self.nodes:
            raise WorkflowException(f"Node '{name}' already registered in workflow graph")
        self.nodes[name] = WorkflowNode(name=name, action=action)
        if self.entry_point is None:
            self.entry_point = name
        return self

    def add_edge(
        self,
        source: str,
        target: str,
        condition: Callable[[dict[str, Any]], bool] | None = None,
    ) -> WorkflowGraph:
        if source not in self.nodes:
            raise WorkflowException(f"Source node '{source}' not found in graph")
        if target not in self.nodes:
            raise WorkflowException(f"Target node '{target}' not found in graph")
        self.edges.append(WorkflowEdge(source=source, target=target, condition=condition))
        return self

    def set_entry_point(self, name: str) -> WorkflowGraph:
        if name not in self.nodes:
            raise WorkflowException(f"Entry point node '{name}' not found in graph")
        self.entry_point = name
        return self

    async def run(self, initial_inputs: dict[str, Any]) -> WorkflowResult:
        if not self.entry_point:
            raise WorkflowException("No entry point configured for workflow graph")

        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        state = dict(initial_inputs)
        history: list[AgentResponse] = []
        current_nodes = [self.entry_point]
        steps = 0

        try:
            while current_nodes and steps < self.max_steps:
                steps += 1

                if len(current_nodes) == 1:
                    node_name = current_nodes[0]
                    node = self.nodes[node_name]
                    state, agent_resp = await node.execute(state)
                    if agent_resp:
                        history.append(agent_resp)
                else:
                    # Parallel execution of multiple active target nodes
                    tasks = [self.nodes[name].execute(state) for name in current_nodes]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    next_combined_state = dict(state)
                    for res in results:
                        if isinstance(res, Exception):
                            raise res
                        sub_state, agent_resp = res
                        next_combined_state.update(sub_state)
                        if agent_resp:
                            history.append(agent_resp)
                    state = next_combined_state

                # Find valid outbound edges from executed nodes
                next_nodes: list[str] = []
                for current in current_nodes:
                    outbound_edges = [e for e in self.edges if e.source == current]
                    for edge in outbound_edges:
                        if edge.evaluate(state) and edge.target not in next_nodes:
                            next_nodes.append(edge.target)

                current_nodes = next_nodes

            if steps >= self.max_steps:
                raise WorkflowException(f"Workflow execution exceeded maximum safety steps limit ({self.max_steps})")

            return WorkflowResult(
                workflow_id=workflow_id,
                status=WorkflowStatus.COMPLETED,
                outputs=state,
                history=history,
            )
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return WorkflowResult(
                workflow_id=workflow_id,
                status=WorkflowStatus.FAILED,
                outputs=state,
                history=history,
                error=str(e),
            )
