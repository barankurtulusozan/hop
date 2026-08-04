# ADR-0004: Multi-Agent Workflow & Conversation Memory Architecture

## Status
Accepted

## Date
2026-08-04

## Context & Problem Statement
As enterprise AI applications scale, single-prompt completions and simple tool execution loops become insufficient for complex multi-step reasoning, long-running agentic conversations, and multi-persona workflows. Key challenges include:
1. **Context Window Exhaustion**: Long-running conversations exceed LLM context windows or incur exorbitant token costs without automated memory management.
2. **Subagent Orchestration**: Complex tasks (e.g. Research $\rightarrow$ Review $\rightarrow$ Summarize) require coordinating multiple specialized agents with distinct system prompts, tools, and routing logic.
3. **Decoupled Architecture**: Workflow state transitions and memory management must adhere strictly to Hexagonal Architecture without hardcoding vendor SDK dependencies into domain logic.

## Decision Drivers
- **Memory Flexibility**: Support multiple memory compaction strategies (`FULL_HISTORY`, `SLIDING_WINDOW`, `TOKEN_BUDGET`, `SUMMARIZED`, `HYBRID_VECTOR`).
- **Graph Orchestration**: Graph-based node/edge execution pipeline supporting sequential, parallel, conditional branching, and supervisor routing.
- **Safety Guardrails**: Loop termination safety (`max_steps`) preventing infinite cycles in non-deterministic agent workflows.

## Component Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                WorkflowGraph                                 │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ State Propagation
                                       ▼
                  ┌────────────────────┴────────────────────┐
                  ▼                                         ▼
┌───────────────────────────────────┐     ┌───────────────────────────────────┐
│        Agent (Researcher)         │     │         Agent (Summarizer)        │
├───────────────────────────────────┤     ├───────────────────────────────────┤
│ - MemoryManager                   │     │ - MemoryManager                   │
│ - ToolExecutor (RAG Search)       │     │ - LLMOrchestrator                 │
└───────────────────────────────────┘     └───────────────────────────────────┘
```

### Key Components:
- **`MemoryManager`**: Handles session turn state, sliding window turn retention, token budget pruning, rolling summarization via `LLMOrchestrator`, and hybrid semantic memory injection via Phase 3 `DenseRetriever`.
- **`Agent`**: Encapsulates `AgentConfig`, `LLMOrchestrator`, optional `ToolExecutor`, and `MemoryManager`.
- **`WorkflowGraph`**: Directed execution graph executing `WorkflowNode` steps connected by `WorkflowEdge` transitions with conditional predicates.

## Consequences
### Positive
- Stateful multi-turn agent conversations without manual history management.
- Dynamic routing across subagents with parallel and supervisor delegation capabilities.
- Full compatibility with Phase 1 resilience features and Phase 3 vector RAG retrieval tools.

### Negative / Trade-offs
- Rolling summarization adds an extra LLM completion step when memory threshold boundaries are breached.
