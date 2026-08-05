import pytest

from src.alignment.guardrail import ModelAlignmentGuardrail
from src.domain.alignment import AlignmentPolicy, AlignmentStatus
from src.domain.exceptions import AlignmentViolationError


def test_model_alignment_guardrail():
    policy = AlignmentPolicy(
        policy_id="test_safety_policy",
        forbidden_terms=["malicious_payload"],
    )
    guardrail = ModelAlignmentGuardrail(policy=policy)

    # 1. Compliant content -> ALIGNED
    res1 = guardrail.verify_alignment("Safe helpful answer.")
    assert res1.is_aligned is True
    assert res1.status == AlignmentStatus.ALIGNED

    # 2. Non-compliant content -> Sanitized
    res2 = guardrail.verify_alignment("Here is a malicious_payload snippet.")
    assert res2.is_aligned is False
    assert res2.status == AlignmentStatus.SANITIZED
    assert "[BLOCKED_BY_ALIGNMENT_POLICY]" in res2.sanitized_content

    # 3. Enforce strict alignment -> Sanitizes content
    sanitized = guardrail.enforce_strict_alignment("Here is a malicious_payload snippet.")
    assert "malicious_payload" not in sanitized
