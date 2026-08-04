from __future__ import annotations

import math
from typing import Any, Awaitable, Callable

from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.domain.evals import EvalResult, TestCase
from src.domain.interfaces import EmbeddingProvider
from src.domain.vector import EmbeddingRequest


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    mag_a = math.sqrt(sum(x * x for x in vec_a))
    mag_b = math.sqrt(sum(x * x for x in vec_b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(vec_a, vec_b)) / (mag_a * mag_b)


class ShadowEvaluator:
    """Automated shadow evaluation engine scoring accuracy, semantic relevance, tool call precision, and latency."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None):
        self.embedding_provider = embedding_provider or MockEmbeddingAdapter(dimension=64)

    async def evaluate_test_case(
        self,
        test_case: TestCase,
        actual_output: str,
        actual_tools: list[str] | None = None,
        latency_ms: float = 0.0,
    ) -> EvalResult:
        metric_scores: dict[str, float] = {}

        # 1. Exact Match Score
        if test_case.expected_output:
            exact_match = 1.0 if actual_output.strip() == test_case.expected_output.strip() else 0.0
            metric_scores["exact_match"] = exact_match

            # 2. Cosine Semantic Relevance Score
            emb_req = EmbeddingRequest(input_texts=[actual_output, test_case.expected_output])
            emb_res = await self.embedding_provider.embed(emb_req)
            sim = _cosine_similarity(emb_res.embeddings[0], emb_res.embeddings[1])
            metric_scores["cosine_relevance"] = max(0.0, min(1.0, round(sim, 4)))

        # 3. Tool Accuracy Score
        if test_case.expected_tools is not None:
            actual_tools = actual_tools or []
            expected_set = set(test_case.expected_tools)
            actual_set = set(actual_tools)
            overlap = expected_set.intersection(actual_set)
            tool_score = len(overlap) / len(expected_set) if expected_set else 1.0
            metric_scores["tool_accuracy"] = tool_score

        # 4. Latency Score (passes if <= target latency, default 5000ms)
        target_latency = test_case.metadata.get("max_latency_ms", 5000.0)
        latency_score = 1.0 if latency_ms <= target_latency else max(0.0, round(target_latency / max(1.0, latency_ms), 2))
        metric_scores["latency_score"] = latency_score

        # Overall aggregate score
        avg_score = round(sum(metric_scores.values()) / len(metric_scores), 4) if metric_scores else 1.0
        passed = avg_score >= test_case.metadata.get("min_pass_score", 0.7)

        return EvalResult(
            test_case_id=test_case.test_case_id,
            score=avg_score,
            passed=passed,
            metric_scores=metric_scores,
            details={
                "actual_output": actual_output,
                "actual_tools": actual_tools,
                "latency_ms": latency_ms,
            },
        )

    async def evaluate_suite(
        self,
        test_cases: list[TestCase],
        runner_fn: Callable[[TestCase], Awaitable[tuple[str, list[str], float]]],
    ) -> list[EvalResult]:
        results: list[EvalResult] = []
        for tc in test_cases:
            actual_output, actual_tools, latency_ms = await runner_fn(tc)
            res = await self.evaluate_test_case(
                test_case=tc,
                actual_output=actual_output,
                actual_tools=actual_tools,
                latency_ms=latency_ms,
            )
            results.append(res)
        return results
