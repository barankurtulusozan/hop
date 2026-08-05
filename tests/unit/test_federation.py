import pytest

from src.domain.exceptions import FederationException
from src.domain.federation import ConsensusRole, NodeStatus, RegionNode
from src.federation.consensus import RaftConsensusEngine
from src.federation.node import MultiRegionNodeManager


def test_multi_region_node_manager():
    mgr = MultiRegionNodeManager()

    n1 = RegionNode(region_id="us-east-1", endpoint="https://us.hop.ai", latency_ms=25.0)
    n2 = RegionNode(region_id="eu-west-1", endpoint="https://eu.hop.ai", latency_ms=10.0)

    mgr.register_node(n1)
    mgr.register_node(n2)

    assert mgr.get_node("us-east-1").endpoint == "https://us.hop.ai"

    # Optimal node selected by lowest latency (eu-west-1 = 10ms)
    optimal = mgr.get_optimal_node()
    assert optimal.region_id == "eu-west-1"


def test_raft_consensus_engine():
    cluster = ["node-1", "node-2", "node-3"]
    engine = RaftConsensusEngine(local_node_id="node-1", cluster_nodes=cluster)

    assert engine.role == ConsensusRole.FOLLOWER

    state = engine.trigger_election()
    assert state.role == ConsensusRole.LEADER
    assert state.leader_id == "node-1"
    assert state.term == 2
