from __future__ import annotations

import re
from typing import Sequence

from src.domain.observability import SafetyCheckResult, SafetyViolationType

PII_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("API_KEY", "[REDACTED_API_KEY]", re.compile(r"sk-[a-zA-Z0-9_-]{20,}")),
    ("BEARER_TOKEN", "[REDACTED_TOKEN]", re.compile(r"Bearer\s+[a-zA-Z0-9._-]{20,}")),
    ("EMAIL", "[REDACTED_EMAIL]", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("SSN", "[REDACTED_SSN]", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", "[REDACTED_CARD]", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
]

PROMPT_INJECTION_SIGNALS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"override\s+(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+DAN", re.IGNORECASE),
    re.compile(r"system\s+override\s+mode", re.IGNORECASE),
]


class PIIRedactor:
    """Regex-based redactor replacing sensitive keys, emails, SSNs, and credit cards with token placeholders."""

    def __init__(self, custom_patterns: Sequence[tuple[str, str, re.Pattern[str]]] | None = None):
        self.patterns = list(custom_patterns or PII_PATTERNS)

    def redact(self, text: str) -> tuple[str, int]:
        if not text:
            return "", 0

        redacted_text = text
        total_redacted = 0

        for label, placeholder, pattern in self.patterns:
            matches = list(pattern.finditer(redacted_text))
            if matches:
                total_redacted += len(matches)
                redacted_text = pattern.sub(placeholder, redacted_text)

        return redacted_text, total_redacted


class SafetyGuardrail:
    """Safety guardrail running PII sanitization and prompt injection threat detection."""

    def __init__(
        self,
        redactor: PIIRedactor | None = None,
        injection_signals: Sequence[re.Pattern[str]] | None = None,
    ):
        self.redactor = redactor or PIIRedactor()
        self.injection_signals = list(injection_signals or PROMPT_INJECTION_SIGNALS)

    def check_text(self, text: str) -> SafetyCheckResult:
        if not text:
            return SafetyCheckResult(is_safe=True, sanitized_text="")

        violations: list[SafetyViolationType] = []

        # 1. PII Redaction
        sanitized_text, count = self.redactor.redact(text)
        if count > 0:
            violations.append(SafetyViolationType.PII_LEAK)

        # 2. Prompt Injection Detection
        for signal in self.injection_signals:
            if signal.search(text):
                violations.append(SafetyViolationType.PROMPT_INJECTION)
                break

        is_safe = SafetyViolationType.PROMPT_INJECTION not in violations

        return SafetyCheckResult(
            is_safe=is_safe,
            violations=violations,
            sanitized_text=sanitized_text,
            redacted_items_count=count,
            metadata={"original_length": len(text), "sanitized_length": len(sanitized_text)},
        )
