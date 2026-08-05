from __future__ import annotations

import inspect
import logging
from typing import Any, Awaitable, Callable

from src.domain.exceptions import MeshException
from src.domain.mesh import HealingPolicy, MeshNodeState, NodeHealth

logger = logging.getLogger("llm_orchestrator.mesh")


class SelfHealingAgentMesh:
    """Self-healing agent node mesh providing trajectory monitoring and automatic fallback remediation."""

    def __init__(self):
        self._policies: dict[str, HealingPolicy] = {}
        self._node_states: dict[str, MeshNodeState] = {}

    def register_policy(self, node_id: str, policy: HealingPolicy) -> None:
        self._policies[node_id] = policy

    def get_node_state(self, node_id: str) -> MeshNodeState:
        return self._node_states.get(node_id, MeshNodeState(node_id=node_id, health=NodeHealth.HEALTHY))

    async def execute_node_with_healing(
        self,
        node_id: str,
        primary_fn: Callable[..., Any],
        fallback_fn: Callable[..., Any] | None = None,
    ) -> Any:
        policy = self._policies.get(node_id, HealingPolicy())
        state = self.get_node_state(node_id)

        try:
            res = primary_fn()
            if inspect.isawaitable(res):
                res = await res

            # Successful run resets node state to HEALTHY
            self._node_states[node_id] = MeshNodeState(
                node_id=node_id,
                health=NodeHealth.HEALTHY,
                error_count=0,
            )
            return res

        except Exception as primary_exc:
            error_count = state.error_count + 1
            logger.warning(f"Mesh node '{node_id}' failed attempt {error_count}/{policy.max_attempts}: {primary_exc}")

            if fallback_fn:
                logger.info(f"Triggering auto-remediation fallback for node '{node_id}'")
                try:
                    res_fallback = fallback_fn()
                    if inspect.isawaitable(res_fallback):
                        res_fallback = await res_fallback

                    self._node_states[node_id] = MeshNodeState(
                        node_id=node_id,
                        health=NodeHealth.HEALED,
                        error_count=error_count,
                        last_error=str(primary_exc),
                    )
                    logger.info(f"Mesh node '{node_id}' auto-remediated successfully via fallback")
                    return res_fallback

                except Exception as fallback_exc:
                    logger.error(f"Fallback remediation for node '{node_id}' also failed: {fallback_exc}")

            self._node_states[node_id] = MeshNodeState(
                node_id=node_id,
                health=NodeHealth.FAILED,
                error_count=error_count,
                last_error=str(primary_exc),
            )
            raise MeshException(f"Node '{node_id}' auto-remediation failed: {primary_exc}")
