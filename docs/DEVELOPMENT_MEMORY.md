# 🧠 Temporary Development Memory & State Tracking

## Project: HOP — Enterprise AI Platform Core
**Status**: Active Enhancement Phase  
**Target Capabilities**: Hybrid RAG, Grammar-Constrained Decoding, LLM-as-a-Judge Evals, Embedding Drift Detection, Ollama Local Adapter.

---

## Current Roadmap State

| Phase | Description | Status | Review Artifact | Commit Hash |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | Hybrid Search RAG (BM25 + Dense Vector + RRF) | ✅ Completed | `docs/reviews/review_step_1.md` | `1969f85` |
| **Phase 2** | Grammar-Constrained Decoding & Structured Output Engine | ✅ Completed | `docs/reviews/review_step_2.md` | `feat(agent): add grammar-constrained structured output engine` |
| **Phase 3** | Ragas-Style Automated LLM-as-a-Judge Evaluation Engine | ⏳ In Progress | `docs/reviews/review_step_3.md` | Pending |
| **Phase 4** | Real-Time Embedding & Concept Drift Detection Engine | ⏹️ Queued | `docs/reviews/review_step_4.md` | Pending |
| **Phase 5** | Ollama Local Engine Provider Adapter | ⏹️ Queued | `docs/reviews/review_step_5.md` | Pending |

---

## Architectural Rules & Memory
- **Pattern**: Strict Hexagonal Architecture (Ports & Adapters).
- **Core Domain Isolation**: Domain models in `src/domain/` depend on NO external packages.
- **Port Interfaces**: Defined in module core (`ports.py` or base classes).
- **Adapters**: Pluggable concrete implementations.
- **Zero Regression Guarantee**: Every iteration MUST maintain 100% test pass rate across the global test suite (`pytest`).
- **Review & Debug Protocol**: Every step produces a `review_step_X.md`. Code changes are committed to Git only when all review items and tests pass cleanly.
