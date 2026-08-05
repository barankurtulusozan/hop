import pytest

from src.domain.exceptions import MeshException
from src.domain.mesh import HealingPolicy, NodeHealth
from src.mesh.agent_mesh import SelfHealingAgentMesh


@pytest.mark.asyncio
async def test_self_healing_agent_mesh():
    mesh = SelfHealingAgentMesh()
    mesh.register_policy("agent_node_1", HealingPolicy(max_attempts=2))

    # 1. Primary node succeeds
    res1 = await mesh.execute_node_with_healing("agent_node_1", lambda: "Success Output")
    assert res1 == "Success Output"
    assert mesh.get_node_state("agent_node_1").health == NodeHealth.HEALTHY

    # 2. Primary node fails, fallback remediates node
    def _fail():
        raise ValueError("Primary node crash")

    def _fallback():
        return "Fallback Remediated Output"

    res2 = await mesh.execute_node_with_healing("agent_node_1", _fail, fallback_fn=_fallback)
    assert res2 == "Fallback Remediated Output"
    state = mesh.get_node_state("agent_node_1")
    assert state.health == NodeHealth.HEALED
    assert state.error_count == 1

    # 3. Both primary and fallback fail -> raises MeshException
    def _fail_fallback():
        raise RuntimeError("Fallback also failed")

    with pytest.raises(MeshException, match="auto-remediation failed"):
        await mesh.execute_node_with_healing("agent_node_1", _fail, fallback_fn=_fail_fallback)
