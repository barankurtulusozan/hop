import pytest
from src.evals.judge import LLMJudgeEvaluator, RagasEvalReport


def test_faithfulness_calculation():
    evaluator = LLMJudgeEvaluator()
    contexts = [
        "HOP uses Hexagonal Architecture with Python 3.13.",
        "Semantic cache returns results in sub-milliseconds.",
    ]
    response = "HOP uses Hexagonal Architecture in Python 3.13."
    score = evaluator.calculate_faithfulness(response, contexts)
    assert score >= 0.8


def test_faithfulness_hallucination():
    evaluator = LLMJudgeEvaluator()
    contexts = ["HOP uses Python 3.13."]
    response = "HOP is written in Java 21 and runs on WebSphere server."
    score = evaluator.calculate_faithfulness(response, contexts)
    assert score < 0.5


def test_answer_relevance():
    evaluator = LLMJudgeEvaluator()
    query = "How does HOP enforce enterprise PII safety?"
    response = "HOP enforces PII safety by redacting sensitive credit card numbers and SSNs."
    score = evaluator.calculate_answer_relevance(query, response)
    assert score >= 0.5


def test_context_precision():
    evaluator = LLMJudgeEvaluator()
    query = "vector similarity search"
    contexts = [
        "Dense vector similarity search uses cosine distance.",
        "Unrelated log file entry 2026-08-11.",
    ]
    score = evaluator.calculate_context_precision(query, contexts)
    assert score == 0.5


@pytest.mark.asyncio
async def test_evaluate_rag_suite():
    evaluator = LLMJudgeEvaluator(min_pass_score=0.70)
    query = "What architecture does HOP use?"
    response = "HOP uses Hexagonal Architecture."
    contexts = ["HOP is built with Hexagonal Architecture."]

    report: RagasEvalReport = await evaluator.evaluate_rag(query, response, contexts)
    assert report.passed is True
    assert report.overall_rag_score >= 0.70
    assert report.faithfulness_score > 0.0
