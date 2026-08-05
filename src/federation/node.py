from __future__ import annotations

import logging

from src.domain.exceptions import FederationException
from src.domain.federation import NodeStatus, RegionNode

logger = logging.getLogger("llm_orchestrator.federation.node")


class MultiRegionNodeManager:
    """Multi-region active-active cluster node manager for cross-region routing and failover."""

    def __init__(self):
        self._nodes: dict[str, RegionNode] = {}

    def register_node(self, node: RegionNode) -> None:
        self._nodes[node.region_id] = node
        logger.info(f"Registered multi-region node '{node.region_id}' at '{node.endpoint}'")

    def get_node(self, region_id: str) -> RegionNode:
        if region_id not in self._nodes:
            raise FederationException(f"Unknown region node '{region_id}'")
        return self._nodes[region_id]

    def get_optimal_node(self) -> RegionNode:
        active_nodes = [n for n in self._nodes.values() if n.status == NodeStatus.ACTIVE]
        if not active_nodes:
            raise FederationException("No active region nodes available in federation cluster")

        # Select node with lowest latency
        sorted_nodes = sorted(active_nodes, key=lambda x: x.latency_ms)
        return sorted_nodes[0]
