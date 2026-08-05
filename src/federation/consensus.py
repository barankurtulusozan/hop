from __future__ import annotations

import logging

from src.domain.federation import ConsensusRole, FederatedConsensusState

logger = logging.getLogger("llm_orchestrator.federation.consensus")


class RaftConsensusEngine:
    """Raft-inspired federated consensus engine for multi-node agent state synchronization."""

    def __init__(self, local_node_id: str, cluster_nodes: list[str]):
        self.local_node_id = local_node_id
        self.cluster_nodes = cluster_nodes
        self.current_term = 1
        self.role = ConsensusRole.FOLLOWER
        self.leader_id: str | None = None

    def trigger_election(self) -> FederatedConsensusState:
        self.current_term += 1
        self.role = ConsensusRole.CANDIDATE
        logger.info(f"Node '{self.local_node_id}' starting election for term {self.current_term}")

        # In local consensus mock, self acquires majority vote and becomes leader
        self.role = ConsensusRole.LEADER
        self.leader_id = self.local_node_id
        logger.info(f"Node '{self.local_node_id}' elected LEADER for term {self.current_term}")

        return self.get_state()

    def get_state(self) -> FederatedConsensusState:
        return FederatedConsensusState(
            term=self.current_term,
            leader_id=self.leader_id,
            role=self.role,
            nodes=list(self.cluster_nodes),
        )
