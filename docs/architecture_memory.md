# Principal AI Engineer Apprenticeship Memory & State Tracker

## Candidate Overview
- **Candidate Level Baseline**: L4 / L5 (Software Engineer / Senior Software Engineer)
- **Target Level**: L6 / L7 (Staff Engineer / Principal AI Engineer)
- **Current Phase**: Phase 1 — Core LLM Orchestrator Service (Completed)
- **Current Operating Level**: L6 (Staff Engineer Standards Met)

---

## 🏛️ Architecture Decision Records (ADR Index)
| ADR ID | Title | Status | Date |
|--------|-------|--------|------|
| [ADR-0001](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0001-llm-provider-abstraction.md) | LLM Provider Abstraction via Hexagonal Ports & Adapters | Accepted | 2026-08-02 |

---

## 🚨 Production Incident History
| Incident ID | Severity | Summary | RCA Status | Date |
|-------------|----------|---------|------------|------|
| *No incidents recorded yet* | | | |

---

## 🔀 Pull Request History
| PR # | Phase | Title | Review Status | Operating Level Demonstrated |
|------|-------|-------|---------------|------------------------------|
| PR-001 | Phase 1 | Core LLM Provider Orchestrator & Isolation Layer | ✅ Approved (All 7 Blockers Resolved) | **L6 (Staff Engineer)** |

---

## 📐 System Architecture & Module Evolution
```
/hop
├── pyproject.toml                         # Project build system & dependencies
├── docs/                                  # Persistent Architectural Memory & ADRs
│   ├── adrs/
│   │   └── ADR-0001-llm-provider-abstraction.md
│   └── architecture_memory.md
├── src/                                   # Enterprise AI Platform Core
│   ├── py.typed                            # PEP 561 type marker
│   ├── config.py                          # Immutable settings & secret containers
│   ├── domain/                            # Hexagonal Port Boundary (No SDK imports)
│   │   ├── exceptions.py
│   │   ├── interfaces.py
│   │   └── models.py
│   ├── adapters/                          # Vendor Adapters (OpenAI, Anthropic, Mock)
│   │   ├── mock_adapter.py
│   │   ├── openai_adapter.py
│   │   └── anthropic_adapter.py
│   └── orchestrator/                      # Execution Engine & Reliability Subsystems
│       ├── circuit_breaker.py             # Fail-fast Circuit Breaker state machine
│       └── pipeline.py                    # Backoff+Jitter Retry & JSON Logger
└── tests/                                 # Unit & Resilience Integration Suite
    ├── unit/
    └── integration/
```

---

## 📓 AI Engineering Journal

### Phase 1: Core LLM Provider Orchestrator & Isolation Layer (Completed)
- **Lessons Learned & Architectural Insights**:
  - Isolating vendor SDKs behind a Hexagonal Port (`LLMProvider`) keeps domain code independent from rapid vendor API changes.
  - Adding a Circuit Breaker (`CLOSED` $\rightarrow$ `OPEN` $\rightarrow$ `HALF_OPEN`) prevents failure amplification under load when an upstream LLM API is dead.
  - Request timeouts (`asyncio.timeout`) are mandatory to stop hanging TCP streams from blocking task pools indefinitely.
  - Standard library logging with `extra={}` is lost unless formatted into valid JSON (`JsonFormatter`) for Datadog/CloudWatch indexers.
- **Trade-offs Made**:
  - Direct vendor options (`provider_options`) are allowed as a controlled escape hatch, but domain code never inspects them.
  - Streaming retries are only executed before yielding the first chunk; mid-stream failures propagate immediately to avoid duplicate partial outputs to clients.
- **Benchmark & Performance Metrics**:
  - Unit/Integration test suite execution time: **0.70 seconds** (17 tests passing, 100% deterministic backoff using fast-sleep injection).
- **Interview & Leadership Takeaways**:
  - *Staff Engineer Question*: "How do you handle rate limits and 5xx errors across multiple LLM vendors?"
  - *Answer*: Hexagonal Ports & Adapters translate vendor exceptions into domain errors at the boundary. An orchestrator wraps execution with exponential backoff, AWS full jitter, per-request timeouts, and a per-provider circuit breaker to eliminate cascading failures.
