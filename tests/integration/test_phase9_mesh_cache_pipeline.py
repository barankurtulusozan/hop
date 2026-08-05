import pytest

from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.cache.semantic_cache import SemanticCache
from src.distill.harvester import TrajectoryHarvester
from src.domain.cache import CacheStatus
from src.domain.mesh import NodeHealth
from src.mesh.agent_mesh import SelfHealingAgentMesh


@pytest.mark.asyncio
async def test_phase9_mesh_cache_and_distillation_pipeline():
    # 1. Setup Phase 9 components
    cache = SemanticCache(embedding_provider=MockEmbeddingAdapter(dimension=16))
    mesh = SelfHealingAgentMesh()
    harvester = TrajectoryHarvester(min_score_threshold=0.85)

    prompt = "Synthesize platform architecture metrics."

    # 2. Check Cache -> Miss initially
    cache_res = await cache.get(prompt)
    assert cache_res.status == CacheStatus.MISS

    # 3. Execute agent node with self-healing mesh
    def _primary_failed_node():
        raise ValueError("Primary node network timeout")

    def _remediated_fallback_node():
        return "Remediated platform trajectory response."

    output = await mesh.execute_node_with_healing(
        node_id="agent_summary_node",
        primary_fn=_primary_failed_node,
        fallback_fn=_remediated_fallback_node,
    )

    assert output == "Remediated platform trajectory response."
    state = mesh.get_node_state("agent_summary_node")
    assert state.health == NodeHealth.HEALED

    # 4. Store in Cache for future sub-ms bypass
    await cache.set(prompt, output)

    # 5. Harvest Trajectory for fine-tuning distillation
    rec = harvester.record_trajectory(
        input_prompt=prompt,
        completion_output=output,
        eval_score=0.96,
    )
    assert rec is not None

    # 6. Verify subsequent query hits cache instantly
    cache_hit = await cache.get(prompt)
    assert cache_hit.status == CacheStatus.HIT
    assert cache_hit.entry.response == output
