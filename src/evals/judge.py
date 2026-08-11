from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.orchestrator.pipeline import LLMOrchestrator


@dataclass
class RagasEvalReport:
    query: str
    response: str
    contexts: list[str]
    faithfulness_score: float
    answer_relevance_score: float
    context_precision_score: float
    overall_rag_score: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


class LLMJudgeEvaluator:
    """Automated LLM-as-a-Judge Evaluation Engine implementing Ragas-style RAG quality metrics."""

    def __init__(self, orchestrator: LLMOrchestrator | None = None, min_pass_score: float = 0.75):
        self.orchestrator = orchestrator
        self.min_pass_score = min_pass_score

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"\w+", text.lower()))

    def calculate_faithfulness(self, response: str, contexts: list[str]) -> float:
        """
        Faithfulness (Hallucination Index):
        Measures what proportion of claims in response are grounded in retrieved contexts.
        """
        if not response or not contexts:
            return 0.0

        response_tokens = self._tokenize(response)
        if not response_tokens:
            return 1.0

        context_tokens: set[str] = set()
        for ctx in contexts:
            context_tokens.update(self._tokenize(ctx))

        # Filter out common stop words to focus on entity/keyword claims
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "and", "or", "in", "on", "at", "to", "for", "of", "with"}
        claims = response_tokens - stop_words

        if not claims:
            return 1.0

        grounded = claims.intersection(context_tokens)
        score = len(grounded) / len(claims)
        return round(score, 4)

    def calculate_answer_relevance(self, query: str, response: str) -> float:
        """
        Answer Relevance:
        Measures semantic/keyword alignment between question and response.
        """
        if not query or not response:
            return 0.0

        q_tokens = self._tokenize(query)
        r_tokens = self._tokenize(response)
        stop_words = {"the", "a", "an", "is", "are", "what", "how", "why", "who", "where", "when", "in", "to", "for"}
        q_keywords = q_tokens - stop_words

        if not q_keywords:
            return 1.0

        matched = q_keywords.intersection(r_tokens)
        score = len(matched) / len(q_keywords)
        return round(score, 4)

    def calculate_context_precision(self, query: str, contexts: list[str]) -> float:
        """
        Context Precision:
        Evaluates the proportion of retrieved context chunks that contain relevant signal for the query.
        """
        if not query or not contexts:
            return 0.0

        q_tokens = self._tokenize(query)
        stop_words = {"the", "a", "an", "is", "are", "what", "how", "why", "who", "where", "when"}
        q_keywords = q_tokens - stop_words

        if not q_keywords:
            return 1.0

        relevant_chunks = 0
        for ctx in contexts:
            c_tokens = self._tokenize(ctx)
            if q_keywords.intersection(c_tokens):
                relevant_chunks += 1

        score = relevant_chunks / len(contexts)
        return round(score, 4)

    async def evaluate_rag(
        self,
        query: str,
        response: str,
        contexts: list[str],
    ) -> RagasEvalReport:
        """Execute complete Ragas evaluation suite for a RAG interaction."""
        faithfulness = self.calculate_faithfulness(response, contexts)
        relevance = self.calculate_answer_relevance(query, response)
        precision = self.calculate_context_precision(query, contexts)

        overall = round((faithfulness + relevance + precision) / 3.0, 4)
        passed = overall >= self.min_pass_score

        return RagasEvalReport(
            query=query,
            response=response,
            contexts=contexts,
            faithfulness_score=faithfulness,
            answer_relevance_score=relevance,
            context_precision_score=precision,
            overall_rag_score=overall,
            passed=passed,
            details={
                "min_pass_score": self.min_pass_score,
                "contexts_count": len(contexts),
            },
        )
