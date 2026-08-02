# Principal AI Engineer Apprenticeship Memory & State Tracker

## Candidate Overview
- **Candidate Level Baseline**: L4 / L5 (Software Engineer / Senior Software Engineer)
- **Target Level**: L6 / L7 (Staff Engineer / Principal AI Engineer)
- **Current Phase**: Phase 2 — Structured Tool & Function Calling Engine (Completed)
- **Current Operating Level**: L6+ (Staff Engineer Maturity Demonstrated)

---

## 🏛️ Architecture Decision Records (ADR Index)
| ADR ID | Title | Status | Date |
|--------|-------|--------|------|
| [ADR-0001](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0001-llm-provider-abstraction.md) | LLM Provider Abstraction via Hexagonal Ports & Adapters | Accepted | 2026-08-02 |
| [ADR-0002](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0002-tool-schema-normalization-and-execution-sandbox.md) | Tool Schema Normalization & Sandboxed Execution Engine | Accepted | 2026-08-03 |

---

## 🚨 Production Incident History
| Incident ID | Severity | Summary | RCA Status | Date |
|-------------|----------|---------|------------|------|
| *No incidents recorded yet* | | | |

---

## 🔀 Pull Request History
| PR # | Phase | Title | Review Status | Operating Level Demonstrated |
|------|-------|-------|---------------|------------------------------|
| PR-001 | Phase 1 | Core LLM Provider Orchestrator & Isolation Layer | ✅ Approved | **L6 (Staff Engineer)** |
| PR-002 | Phase 2 | Structured Tool & Function Calling Engine with Sandbox | ✅ Approved | **L6+ (Staff Engineer)** |

---

## 📐 System Architecture & Module Evolution
```
/hop
├── pyproject.toml                         # Project build system & dependencies
├── docs/                                  # Persistent Architectural Memory & ADRs
│   ├── adrs/
│   │   ├── ADR-0001-llm-provider-abstraction.md
│   │   └── ADR-0002-tool-schema-normalization-and-execution-sandbox.md
│   └── architecture_memory.md
├── src/                                   # Enterprise AI Platform Core
│   ├── py.typed                            # PEP 561 type marker
│   ├── config.py                          # Immutable settings & secret containers
│   ├── domain/                            # Hexagonal Port Boundary (No SDK imports)
│   │   ├── exceptions.py
│   │   ├── interfaces.py
│   │   ├── models.py                      # Message, CompletionRequest/Response with Tools
│   │   └── tools.py                       # ToolDefinition, ToolCall, ToolResult, ToolExceptions
│   ├── tools/                             # Tool Subsystem & Security Sandbox
│   │   ├── registry.py                    # Function & Pydantic auto-schema registry
│   │   └── executor.py                    # Sandboxed Tool Executor (Timeout & Exception boundary)
│   ├── adapters/                          # Vendor Adapters (OpenAI, Anthropic, Mock)
│   │   ├── mock_adapter.py
│   │   ├── openai_adapter.py              # Function tools <-> OpenAI tools translation
│   │   └── anthropic_adapter.py           # Tool_use blocks <-> Anthropic input_schema translation
│   └── orchestrator/                      # Execution Engine & Reliability Subsystems
│       ├── circuit_breaker.py             # Fail-fast Circuit Breaker state machine
│       ├── pipeline.py                    # Backoff+Jitter Retry & JSON Logger
│       └── tool_runner.py                 # Tool Execution Orchestrator & Auto-Correction Loop
└── tests/                                 # Unit & Resilience Integration Suite
    ├── unit/
    │   ├── test_backoff.py
    │   ├── test_domain.py
    │   ├── test_resilience_b3_b7.py
    │   └── test_tools.py                  # Registry & Sandbox unit tests
    └── integration/
        ├── test_resilience.py
        └── test_tool_execution.py         # End-to-end tool execution & self-correction loop
```

---

## 📓 AI Engineering Journal

### Phase 2: Structured Tool & Function Calling Engine (Completed)
- **Lessons Learned & Architectural Insights**:
  - Never allow raw LLM JSON payloads directly into tool handler functions. Enforce a defensive validation boundary (`Pydantic model_validate`) to catch malformed argument types before function execution.
  - Implement an **Agentic Auto-Correction Loop**: When an LLM generates invalid tool parameters, construct a `Role.TOOL` turn containing the validation error message and re-prompt the LLM. LLMs consistently correct their parameters on the second attempt.
  - Separate tool schema generation (`ToolRegistry`) from tool execution (`ToolExecutor`). This enforces Single Responsibility and simplifies unit testing.
- **Trade-offs Made**:
  - Python type hints are inspected to auto-generate JSON schemas, avoiding duplicate manual JSON schema definitions.
  - Async and sync tool handlers are normalized in `ToolExecutor` via `asyncio.to_thread` to ensure zero blocking calls on event loops.
- **Benchmark & Performance Metrics**:
  - Test Suite: **26 passing tests in 0.79s** (100% passing across unit and integration coverage).
- **Interview & Leadership Takeaways**:
  - *Staff Engineer Question*: "How do you protect an enterprise platform against malformed tool calls and prompt injection from LLMs?"
  - *Answer*: By establishing an Anti-Corruption Layer for tools. The `ToolRegistry` converts functions/models into vendor-agnostic `ToolDefinition` schemas. Before invocation, `ToolExecutor` validates arguments against Pydantic schemas within an isolated execution boundary (with timeouts and exception catching). If validation fails, `ToolOrchestrator` triggers a self-correction loop to re-prompt the model safely without crashing the service.
