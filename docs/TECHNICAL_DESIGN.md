# 🏛️ Technical Design Document: Enterprise AI Engineering Enhancements

## 1. Overview
This technical design details 5 advanced AI/ML infrastructure components integrated into **HOP — Enterprise AI Platform Core**, adhering strictly to Hexagonal Ports & Adapters architecture.

---

## 2. Component Design & Architecture

### Phase 1: Hybrid Search RAG (BM25 + Dense Vector + Reciprocal Rank Fusion)
* **Goal**: Combine sparse lexical term frequency searching (BM25) with dense vector embedding similarity search using Reciprocal Rank Fusion (RRF).
* **Ports**: Extended `VectorStorePort` in `src/vector/hybrid.py`.
* **RRF Formula**:
  $$\text{RRF\_Score}(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  where $k = 60$, $r_m(d)$ is the rank position of document $d$ in retrieval system $m$.
* **Key Classes**:
  - `BM25Retriever`: Tokenizer, term frequency, inverse document frequency index builder.
  - `ReciprocalRankFusion`: Merges dense vector results and BM25 search scores deterministically.
  - `HybridVectorStore`: Unified adapter coordinating embedding search and sparse lexical search.

---

### Phase 2: Grammar-Constrained Decoding & Structured JSON Engine
* **Goal**: Validate and guarantee structured JSON responses matching Pydantic schemas or JSON Schemas, with automatic error recovery and repair.
* **Location**: `src/agent/grammar.py`.
* **Key Classes**:
  - `StructuredOutputPort`: Port definition for constrained output generation.
  - `JSONSchemaValidatorEngine`: Validates output against JSON schema; auto-fixes minor JSON syntax errors (trailing commas, unquoted keys, markdown code fences).

---

### Phase 3: Ragas-Style Automated LLM-as-a-Judge Evaluation Engine
* **Goal**: Perform automated evaluation of RAG responses against retrieved contexts and user prompts.
* **Location**: `src/evals/judge.py`.
* **Key Metrics**:
  - **Faithfulness**: Measures context grounding (detects hallucination).
  - **Answer Relevance**: Measures prompt-to-response alignment.
  - **Context Precision**: Measures signal-to-noise ratio in retrieved context chunks.

---

### Phase 4: Real-Time Embedding & Concept Drift Detection Engine
* **Goal**: Detect semantic drift and query distribution shifts using statistical distance metrics.
* **Location**: `src/observability/drift.py`.
* **Key Metrics**:
  - **Population Stability Index (PSI)**: Quantifies shift between baseline query embeddings and current window embeddings.
  - **Kolmogorov-Smirnov (KS) Test**: Evaluates empirical distribution shifts in similarity scores.

---

### Phase 5: Local & Air-Gapped Engine Adapter (Ollama Adapter)
* **Goal**: Add zero-dependency native adapter for local open-source models via Ollama API (`http://localhost:11434`).
* **Location**: `src/adapters/ollama_adapter.py`.
* **Capabilities**: Complies with `LLMProviderPort`, supports SSE streaming, tool schema formatting, and circuit breaker protection.
