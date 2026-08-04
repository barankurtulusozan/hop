# Principal AI Engineer Apprenticeship Memory & State Tracker

## Candidate Overview
- **Candidate Level Baseline**: L4 / L5 (Software Engineer / Senior Software Engineer)
- **Target Level**: L6 / L7 (Staff Engineer / Principal AI Engineer)
- **Current Phase**: Phase 4 — Multi-Agent Workflow Engine & Conversation Memory Management (Completed)
- **Current Operating Level**: L7 (Principal AI Engineer)

---

## 🏛️ Architecture Decision Records (ADR Index)
| ADR ID | Title | Status | Date |
|--------|-------|--------|------|
| [ADR-0001](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0001-llm-provider-abstraction.md) | LLM Provider Abstraction via Hexagonal Ports & Adapters | Accepted | 2026-08-02 |
| [ADR-0002](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0002-tool-schema-normalization-and-execution-sandbox.md) | Tool Schema Normalization & Sandboxed Execution Engine | Accepted | 2026-08-03 |
| [ADR-0003](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0003-vector-store-and-dense-retrieval-engine.md) | Vector Store & Dense Retrieval Engine Architecture | Accepted | 2026-08-04 |
| [ADR-0004](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0004-multi-agent-workflow-and-conversation-memory-engine.md) | Multi-Agent Workflow & Conversation Memory Architecture | Accepted | 2026-08-04 |

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
| PR-004 | Phase 4 | Multi-Agent Workflow Engine & Memory Compaction | ✅ Approved | **L7 (Principal AI Engineer)** |

---

## 📐 System Architecture & Module Evolution
```
/hop
├── pyproject.toml                         # Project build system & dependencies
├── docs/                                  # Persistent Architectural Memory & ADRs
│   ├── adrs/
│   │   ├── ADR-0001-llm-provider-abstraction.md
│   │   ├── ADR-0002-tool-schema-normalization-and-execution-sandbox.md
│   │   ├── ADR-0003-vector-store-and-dense-retrieval-engine.md
│   │   └── ADR-0004-multi-agent-workflow-and-conversation-memory-engine.md
│   └── architecture_memory.md
├── src/                                   # Enterprise AI Platform Core
│   ├── py.typed                            # PEP 561 type marker
│   ├── config.py                          # Immutable settings & secret containers
│   ├── domain/                            # Hexagonal Port Boundary (No SDK imports)
│   │   ├── exceptions.py                  # Domain exception hierarchy (LLM, Vector, Agent, Memory, Workflow)
│   │   ├── interfaces.py                  # LLMProvider, EmbeddingProvider, VectorStore ports
│   │   ├── models.py                      # Message, CompletionRequest/Response with Tools
│   │   ├── vector.py                      # VectorRecord, Chunk, Document, MetadataFilter
│   │   ├── memory.py                      # ConversationTurn, SessionState, MemoryStrategy
│   │   ├── agent.py                       # AgentConfig, AgentResponse, WorkflowResult, WorkflowStatus
│   │   └── tools.py                       # ToolDefinition, ToolCall, ToolResult
│   ├── agent/                             # Stateful Agent Core
│   │   └── agent.py                       # Agent runner encapsulating LLM, Tools, & Memory
│   ├── memory/                            # Stateful Conversation Memory Engine
│   │   └── manager.py                     # MemoryManager (Sliding window, token budget, summary, hybrid vector)
│   ├── tools/                             # Tool Subsystem & Security Sandbox
│   │   ├── registry.py                    # Function & Pydantic auto-schema registry
│   │   └── executor.py                    # Sandboxed Tool Executor (Timeout & Exception boundary)
│   ├── adapters/                          # Vendor Adapters (LLM & Embeddings)
│   │   ├── mock_adapter.py
│   │   ├── openai_adapter.py              # Function tools <-> OpenAI tools translation
│   │   ├── anthropic_adapter.py           # Tool_use blocks <-> Anthropic translation
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
│       ├── tool_runner.py                 # Tool Execution Orchestrator & Auto-Correction Loop
│       └── workflow.py                    # WorkflowGraph, WorkflowNode, WorkflowEdge orchestrator
└── tests/                                 # Unit & Resilience Integration Suite
    ├── unit/
    │   ├── test_backoff.py
    │   ├── test_domain.py
    │   ├── test_resilience_b3_b7.py
    │   ├── test_tools.py                  # Registry & Sandbox unit tests
    │   ├── test_vector.py                 # VectorStore, Chunker, & Embedding unit tests
    │   ├── test_memory.py                 # MemoryManager strategy unit tests
    │   └── test_workflow.py               # Agent & WorkflowGraph unit tests
    └── integration/
        ├── test_resilience.py
        ├── test_tool_execution.py         # End-to-end tool execution & self-correction loop
        ├── test_rag_pipeline.py           # End-to-end RAG ingestion & tool search integration
        └── test_multi_agent_workflow.py   # Multi-agent workflow integration with RAG & memory
```

---

## 📓 AI Engineering Journal

### Phase 3: Vector Store & Dense Retrieval Engine (Completed)
- **Lessons Learned & Architectural Insights**:
  - Strictly enforce Hexagonal Architecture boundaries for vector primitives. Domain models (`Document`, `Chunk`, `VectorRecord`, `MetadataFilter`) and ports (`EmbeddingProvider`, `VectorStore`) live in `src/domain/` with zero vendor SDK imports.
  - Build an in-memory vector store (`InMemoryVectorStore`) with support for multiple distance metrics (Cosine Similarity, Dot Product, Euclidean L2 Distance) and granular metadata filtering.

### Phase 4: Multi-Agent Workflow Engine & Conversation Memory (Completed)
- **Lessons Learned & Architectural Insights**:
  - Build a stateful `MemoryManager` with multiple compaction strategies (`SLIDING_WINDOW`, `TOKEN_BUDGET`, `SUMMARIZED`, `HYBRID_VECTOR`). Rolling summarization uses `LLMOrchestrator` to distill long conversation turns into concise state summaries without exceeding context windows.
  - Model multi-agent pipelines using a directed graph abstraction (`WorkflowGraph`, `WorkflowNode`, `WorkflowEdge`). Nodes can be stateful `Agent` instances or Python callables, connected by directed edges with optional conditional evaluation functions.
  - Enforce strict loop safety limits (`max_steps`) on graph traversals to guarantee termination in complex or cyclic multi-agent routing.
- **Interview & Leadership Takeaways**:
  - *Principal AI Engineer Question*: "How do you coordinate long-running multi-agent tasks without hitting LLM context limits or infinite execution loops?"
  - *Answer*: By combining stateful conversation memory management (`MemoryManager`) with a graph-based workflow engine (`WorkflowGraph`). The `MemoryManager` prunes or compacts history using token budgets, rolling LLM summaries, or hybrid RAG retrieval. The `WorkflowGraph` executes subagents in sequential, parallel, or supervisor-delegated nodes with explicit conditional edge predicates and hard `max_steps` safeguards to prevent infinite execution cycles.


