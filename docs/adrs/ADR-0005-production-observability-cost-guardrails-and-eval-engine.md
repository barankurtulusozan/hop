# ADR-0005: Production Observability, Cost Guardrails & Evaluation Architecture

## Status
Accepted

## Date
2026-08-04

## Context & Problem Statement
Operating LLMs and autonomous multi-agent systems in enterprise production environments exposes platforms to three critical operational risks:
1. **Unbounded Financial Spend**: Runaway agent loops or API key leaks can consume thousands of dollars in minutes without automated real-time spend limits.
2. **Data Leakage & Prompt Injection**: Sensitive PII (emails, SSNs, credit cards, API keys) can leak into LLM logs or prompts, and hostile user inputs can inject prompt overrides.
3. **Black-Box Trajectory Failures**: Without distributed tracing across LLM calls, tools, vector searches, and agent graph nodes, diagnosing failures or latency bottlenecks is impossible.

## Decision Drivers
- **Real-Time Cost Control**: Enforce daily dollar limits and per-minute token rate ceilings per tenant.
- **Zero Vendor Lock-in Telemetry**: Define `Span` and `Tracer` hexagonal interfaces with OpenTelemetry compatibility.
- **Defend-in-Depth Safety**: Automated regex PII redaction and prompt injection checks before prompts enter LLMs or logging pipelines.
- **Shadow Evaluation Benchmarking**: Automated evaluation engine (`ShadowEvaluator`) measuring semantic relevance, exact match, tool call precision, and latency SLAs.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             LLMOrchestrator / Agent                         │
└──────┬──────────────────────────────┬──────────────────────────────┬────────┘
       │ Tracing                      │ Budget & Rate Checks         │ PII Redaction
       ▼                              ▼                              ▼
┌──────────────┐              ┌──────────────┐               ┌──────────────┐
│    Tracer    │              │CostGuardrail │               │PIIRedactor & │
│ (OTel Spans) │              │ ($ Spend/TPM)│               │SafetyGuardrail│
└──────────────┘              └──────────────┘               └──────────────┘
                                                                     │
                                                                     ▼
                                                             ┌──────────────┐
                                                             │ShadowEvaluator│
                                                             └──────────────┘
```

### Key Components:
- **`Tracer`**: Generates OpenTelemetry-compliant trace spans tracking start/end times, durations, status codes, and attributes.
- **`CostGuardrail`**: Enforces tenant-level daily USD budgets and per-minute token rate limits (`CostBudgetExceeded`).
- **`PIIRedactor` & `SafetyGuardrail`**: Sanitizes sensitive fields (`[REDACTED_API_KEY]`, `[REDACTED_EMAIL]`, etc.) and flags prompt injection signals.
- **`ShadowEvaluator`**: Benchmarks accuracy, cosine semantic similarity, tool precision, and latency budgets against test case suites.

## Consequences
### Positive
- Prevents runaway billing spikes and accidental API key/PII leaks.
- Complete distributed tracing across complex multi-agent execution graphs.
- Continuous quality assurance via automated evaluation benchmark suites.
