import pytest

from src.domain.federation import ConsensusRole, RegionNode
from src.federation.consensus import RaftConsensusEngine
from src.federation.node import MultiRegionNodeManager
from src.security.vault import ZeroTrustKeyVault


@pytest.mark.asyncio
async def test_phase10_federation_and_vault_pipeline():
    # 1. Multi-Region Active-Active Routing
    node_mgr = MultiRegionNodeManager()
    node_mgr.register_node(RegionNode(region_id="us-east", endpoint="https://us.hop.ai", latency_ms=12.0))
    node_mgr.register_node(RegionNode(region_id="eu-central", endpoint="https://eu.hop.ai", latency_ms=5.0))

    optimal = node_mgr.get_optimal_node()
    assert optimal.region_id == "eu-central"

    # 2. Raft Consensus Election
    consensus = RaftConsensusEngine(local_node_id="eu-central", cluster_nodes=["us-east", "eu-central"])
    state = consensus.trigger_election()
    assert state.role == ConsensusRole.LEADER
    assert state.leader_id == "eu-central"

    # 3. Zero-Trust Key Vault Encryption
    vault = ZeroTrustKeyVault()
    key = vault.generate_key("node_eu_key")
    encrypted_secret = vault.encrypt_string("node_eu_key", "sk-proj-super-secret-key-12345")
    decrypted_secret = vault.decrypt_string("node_eu_key", encrypted_secret)

    assert decrypted_secret == "sk-proj-super-secret-key-12345"
