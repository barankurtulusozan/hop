import pytest

from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.domain.evals import TestCase
from src.evals.evaluator import ShadowEvaluator


@pytest.mark.asyncio
async def test_shadow_evaluator_metrics():
    evaluator = ShadowEvaluator(embedding_provider=MockEmbeddingAdapter(dimension=32))

    tc = TestCase(
        test_case_id="tc_001",
        input="What is hexagonal architecture?",
        expected_output="Hexagonal architecture decouples domain logic via ports and adapters.",
        expected_tools=["search_knowledge_base"],
        metadata={"max_latency_ms": 2000.0, "min_pass_score": 0.6},
    )

    res = await evaluator.evaluate_test_case(
        test_case=tc,
        actual_output="Hexagonal architecture decouples domain logic via ports and adapters.",
        actual_tools=["search_knowledge_base"],
        latency_ms=150.0,
    )

    assert res.test_case_id == "tc_001"
    assert res.passed is True
    assert res.metric_scores["exact_match"] == 1.0
    assert res.metric_scores["tool_accuracy"] == 1.0
    assert res.metric_scores["latency_score"] == 1.0


@pytest.mark.asyncio
async def test_shadow_evaluator_suite_runner():
    evaluator = ShadowEvaluator()
    tc1 = TestCase(test_case_id="tc_1", input="Query 1", expected_output="Ans 1")
    tc2 = TestCase(test_case_id="tc_2", input="Query 2", expected_output="Ans 2")

    async def mock_runner(tc: TestCase):
        return (tc.expected_output or "", [], 50.0)

    results = await evaluator.evaluate_suite([tc1, tc2], mock_runner)
    assert len(results) == 2
    assert all(r.passed for r in results)
