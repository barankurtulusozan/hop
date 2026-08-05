import pytest

from src.speculative.engine import SpeculativeExecutionEngine


def test_speculative_execution_engine():
    engine = SpeculativeExecutionEngine()

    prompt = "Predict output tokens for speedup"
    draft_tokens = ["the", "quick", "brown", "fox"]
    verifier_tokens = ["the", "quick", "brown", "dog"]

    draft = engine.execute_speculative_draft(prompt, draft_tokens, verifier_tokens)

    # First 3 tokens match ('the', 'quick', 'brown')
    assert draft.accepted_tokens == ["the", "quick", "brown"]
    assert draft.acceptance_rate == 0.75
    assert draft.latency_savings_pct > 0.0
