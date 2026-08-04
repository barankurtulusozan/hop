# ADR-0003: Vector Store & Dense Retrieval Engine Architecture

## Status
Accepted

## Date
2026-08-04

## Context & Problem Statement
To support Retrieval-Augmented Generation (RAG) and domain-specific knowledge integration, the platform requires dense semantic vector search, document chunking, payload filtering, and vendor-agnostic embedding interfaces. High-level requirements include:
1. Zero vendor SDK lock-in in core domain abstractions.
2. In-memory and external vector store interoperability.
3. Configurable distance metrics (Cosine Similarity, Dot Product, Euclidean L2 Distance).
4. Rich payload metadata filtering ($eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $contains).
5. Seamless integration with the existing `ToolRegistry` and `ToolOrchestrator` self-correction loop.

## Decision Drivers
- **Hexagonal Integrity**: Core domain vector models (`Document`, `Chunk`, `VectorRecord`, `VectorSearchResult`, `MetadataFilter`) and ports (`EmbeddingProvider`, `VectorStore`) must live inside `src/domain/` with zero vendor imports.
- **Fast Local Testing**: Need zero-network, deterministic embedding generation (`MockEmbeddingAdapter`) and fast in-memory indexing (`InMemoryVectorStore`) for unit and integration testing.
- **RAG Execution Integration**: Dense retrieval must expose standard tool signatures that `ToolExecutor` and `ToolOrchestrator` can invoke dynamically.

## Considered Options
1. Require heavyweight external vector databases (Qdrant, Pinecone) as strict dependencies.
2. Direct embedding provider calls inside application pipelines without hexagonal port boundaries.
3. Decoupled Hexagonal Ports (`EmbeddingProvider`, `VectorStore`) + `InMemoryVectorStore` + `RecursiveCharacterTextSplitter` + RAG tool integration (Selected).

## Architecture & Component Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ToolOrchestrator                               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Tool Call: search_knowledge_base
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DenseRetriever (Tool)                            │
└──────────────────┬──────────────────────────────────────┬───────────────────┘
                   │ Query Embed                          │ Similarity Search
                   ▼                                      ▼
┌─────────────────────────────────────┐ ┌─────────────────────────────────────┐
│       EmbeddingProvider (Port)      │ │          VectorStore (Port)         │
├─────────────────────────────────────┤ ├─────────────────────────────────────┤
│ - MockEmbeddingAdapter              │ │ - InMemoryVectorStore               │
│ - OpenAIEmbeddingAdapter            │ │ - (PGVector/Qdrant Future Adapters) │
└─────────────────────────────────────┘ └─────────────────────────────────────┘
```

### Key Components:
- **`EmbeddingProvider` (Port)**: Defines contract `async def embed(request: EmbeddingRequest) -> EmbeddingResponse` with `dimension` metadata property.
- **`VectorStore` (Port)**: Abstract interface for vector indexing (`upsert`), search (`search`), and cleanup (`delete`).
- **`InMemoryVectorStore`**: Thread-safe vector index supporting Cosine, Dot Product, and Euclidean similarity scoring, with predicate payload filtering.
- **`RecursiveCharacterTextSplitter`**: Splits documents recursively along separator boundaries (`\n\n`, `\n`, ` `, `""`) preserving text overlap and chunk lineage metadata.
- **`VectorIngestionPipeline` & `DenseRetriever`**: End-to-end ingestion (chunking -> embedding -> indexing) and search retrieval.
- **`create_vector_search_tool`**: Converts dense retrieval into a Pydantic-validated tool callable by `ToolExecutor`.

## Consequences
### Positive
- Zero external vector database required for unit testing or simple deployments.
- Pluggable architecture allowing seamless swap to PGVector, Qdrant, or Pinecone adapters without changing business logic.
- Full auto-correction support when LLM agents generate tool queries.

### Negative / Trade-offs
- `InMemoryVectorStore` scales up to ~100k vectors per process; larger enterprise datasets require external vector DB adapters.
