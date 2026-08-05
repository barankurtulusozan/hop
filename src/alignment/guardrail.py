from __future__ import annotations

import logging

from src.domain.alignment import AlignmentPolicy, AlignmentStatus, AlignmentVerificationResult
from src.domain.exceptions import AlignmentViolationError

logger = logging.getLogger("llm_orchestrator.alignment")


class ModelAlignmentGuardrail:
    """Real-time RLHF/DPO policy verification and alignment enforcement guardrail."""

    def __init__(self, policy: AlignmentPolicy | None = None):
        self.policy = policy or AlignmentPolicy(
            policy_id="default_rlhf_policy",
            forbidden_terms=["unsafe_exploit", "malicious_payload"],
        )

    def verify_alignment(self, content: str) -> AlignmentVerificationResult:
        violations: list[str] = []
        sanitized = content

        for term in self.policy.forbidden_terms:
            if term in content:
                violations.append(f"Forbidden term '{term}' detected")
                sanitized = sanitized.replace(term, "[BLOCKED_BY_ALIGNMENT_POLICY]")

        if violations:
            logger.warning(f"Alignment Policy '{self.policy.policy_id}' flagged {len(violations)} violations")
            return AlignmentVerificationResult(
                status=AlignmentStatus.SANITIZED if sanitized != content else AlignmentStatus.VIOLATION_BLOCKED,
                is_aligned=False,
                violations=violations,
                sanitized_content=sanitized,
            )

        return AlignmentVerificationResult(
            status=AlignmentStatus.ALIGNED,
            is_aligned=True,
            violations=[],
            sanitized_content=content,
        )

    def enforce_strict_alignment(self, content: str) -> str:
        res = self.verify_alignment(content)
        if not res.is_aligned and res.status == AlignmentStatus.VIOLATION_BLOCKED:
            raise AlignmentViolationError(f"Content failed alignment check: {res.violations}")
        return res.sanitized_content
