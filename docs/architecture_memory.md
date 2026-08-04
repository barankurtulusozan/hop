# Principal AI Engineer Apprenticeship Memory & State Tracker

## Candidate Overview
- **Candidate Level Baseline**: L4 / L5 (Software Engineer / Senior Software Engineer)
- **Target Level**: L6 / L7 (Staff Engineer / Principal AI Engineer)
- **Current Phase**: Phase 3 — Vector Store & Dense Retrieval Engine (Completed)
- **Current Operating Level**: L6+ / L7 (Principal AI Engineer Maturity)

---

## 🏛️ Architecture Decision Records (ADR Index)
| ADR ID | Title | Status | Date |
|--------|-------|--------|------|
| [ADR-0001](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0001-llm-provider-abstraction.md) | LLM Provider Abstraction via Hexagonal Ports & Adapters | Accepted | 2026-08-02 |
| [ADR-0002](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0002-tool-schema-normalization-and-execution-sandbox.md) | Tool Schema Normalization & Sandboxed Execution Engine | Accepted | 2026-08-03 |
| [ADR-0003](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0003-vector-store-and-dense-retrieval-engine.md) | Vector Store & Dense Retrieval Engine Architecture | Accepted | 2026-08-04 |

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
| PR-003 | Phase 3 | Vector Store & Dense Retrieval Engine with RAG Tool | ✅ Approved | **L6+ / L7 (Principal AI Engineer)** |

---

## 📐 System Architecture & Module Evolution
```
/hop
├── pyproject.toml                         # Project build system & dependencies
├── docs/                                  # Persistent Architectural Memory & ADRs
│   ├── adrs/
│   │   ├── ADR-0001-llm-provider-abstraction.md
│   │   ├── ADR-0002-tool-schema-normalization-and-execution-sandbox.md
│   │   └── ADR-0003-vector-store-and-dense-retrieval-engine.md
│   └── architecture_memory.md
├── src/                                   # Enterprise AI Platform Core
│   ├── py.typed                            # PEP 561 type marker
│   ├── config.py                          # Immutable settings & secret containers
│   ├── domain/                            # Hexagonal Port Boundary (No SDK imports)
│   │   ├── exceptions.py                  # Domain exception hierarchy (LLM, Vector, Embedding)
│   │   ├── interfaces.py                  # LLMProvider, EmbeddingProvider, VectorStore ports
│   │   ├── models.py                      # Message, CompletionRequest/Response with Tools
│   │   ├── vector.py                      # VectorRecord, Chunk, Document, MetadataFilter, Metrics
│   │   └── tools.py                       # ToolDefinition, ToolCall, ToolResult
│   ├── tools/                             # Tool Subsystem & Security Sandbox
│   │   ├── registry.py                    # Function & Pydantic auto-schema registry
│   │   └── executor.py                    # Sandboxed Tool Executor (Timeout & Exception boundary)
│   ├── adapters/                          # Vendor Adapters (LLM & Embeddings)
│   │   ├── mock_adapter.py
│   │   ├── openai_adapter.py              # Function tools <-> OpenAI tools translation
      ├── anthropic_adapter.py           # Tool_use blocks <-> Anthropic translation
│   │   └── embeddings/                    # Vector Embedding Adapters
│   │       ├── mock_adapter.py            # Deterministic, normalized mock embedding generator
│   │       └── openai_adapter.py          # OpenAI text-embedding adapter with exception mapping
│   ├── vector/                            # Vector Subsystem & Dense Retrieval Engine
│   │   ├── store.py                       # InMemoryVectorStore (Cosine/Dot/L2 & metadata filter)
│   │   ├── chunker.py                     # RecursiveCharacterTextSplitter with text overlap
│   │   ├── pipeline.py                    # VectorIngestionPipeline & DenseRetriever
│   │   └── tool.py                        # KnowledgeBaseSearchTool RAG tool factory
│   └── orchestrator/                      # Execution Engine & Reliability Subsystems
│       ├── circuit_breaker.py             # Fail-fast Circuit Breaker state machine
│       ├── pipeline.py                    # Backoff+Jitter Retry & JSON Logger
│       └── tool_runner.py                 # Tool Execution Orchestrator & Auto-Correction Loop
└── tests/                                 # Unit & Resilience Integration Suite
    ├── unit/
    │   ├── test_backoff.py
    │   ├── test_domain.py
    │   ├── test_resilience_b3_b7.py
    │   ├── test_tools.py                  # Registry & Sandbox unit tests
    │   └── test_vector.py                 # VectorStore, Chunker, & Embedding unit tests
    └── integration/
        ├── test_resilience.py
        ├── test_tool_execution.py         # End-to-end tool execution & self-correction loop
        └── test_rag_pipeline.py           # End-to-end RAG ingestion & tool search integration
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

### Phase 3: Vector Store & Dense Retrieval Engine (Completed)
- **Lessons Learned & Architectural Insights**:
  - Strictly enforce Hexagonal Architecture boundaries for vector primitives. Domain models (`Document`, `Chunk`, `VectorRecord`, `MetadataFilter`) and ports (`EmbeddingProvider`, `VectorStore`) live in `src/domain/` with zero vendor SDK imports.
  - Build an in-memory vector store (`InMemoryVectorStore`) with support for multiple distance metrics (Cosine Similarity, Dot Product, Euclidean L2 Distance) and granular metadata filtering ($eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $contains).
  - Connect dense retrieval into the agentic tool workflow using `create_vector_search_tool()`, exposing a knowledge base search tool directly into `ToolRegistry` and `ToolOrchestrator`.
- **Trade-offs Made**:
  - `InMemoryVectorStore` uses standard Python math with thread locks for microsecond local testing and zero external dependencies, while keeping the `VectorStore` interface plug-compatible with enterprise vector databases (e.g. PGVector, Qdrant).
- **Interview & Leadership Takeaways**:
  - *Principal AI Engineer Question*: "How do you integrate dense vector search into an enterprise agent pipeline without creating tight coupling to vector DB vendors?"
  - *Answer*: By isolating `EmbeddingProvider` and `VectorStore` as hexagonal ports inside `src/domain/`. Application code depends solely on `DenseRetriever` and `VectorIngestionPipeline`. Vendor-specific adapters (OpenAI Embeddings, PGVector, Qdrant) implement these ports outside the domain. RAG search is exposed to LLMs as a standard Pydantic tool via `create_vector_search_tool()`, enabling agents to search domain knowledge with full self-correction safety.

