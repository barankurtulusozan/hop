# 🚀 HOP — Enterprise AI Platform Core

**HOP** is a production-grade, multi-tenant, multi-provider LLM orchestration, security, streaming gateway, and evaluation platform built with **Strict Hexagonal Architecture (Ports & Adapters)** in Python 3.13+.

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://python.org)
[![Architecture](https://img.shields.io/badge/architecture-Hexagonal%20Ports%20%26%20Adapters-green.svg)](#-hexagonal-architecture)
[![Test Suite](https://img.shields.io/badge/tests-100%25%20passing-brightgreen.svg)](#-testing)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

---

## 🏛️ Platform Architectural Highlights

- **Strict Hexagonal Isolation**: Zero vendor SDK imports (`openai`, `anthropic`, etc.) in `src/domain/`. All domain contracts are pure Python & Pydantic models.
- **Fail-Fast Circuit Breakers & Backoff**: Exponential backoff with full jitter and per-provider Circuit Breakers (`CLOSED` $\rightarrow$ `OPEN` $\rightarrow$ `HALF_OPEN`).
- **Sandboxed Tool Engine**: Defensive Pydantic schema validation, sandboxed execution timeouts, and agentic auto-correction loops.
- **Dense Vector Retrieval Engine**: Embeddings port, `InMemoryVectorStore` supporting Cosine, Dot Product, and Euclidean L2 distance metrics with payload predicate filtering and RAG tool integration.
- **Multi-Agent Workflow Engine**: Stateful `MemoryManager` with sliding window, token budget, rolling LLM summaries, and hybrid vector RAG retrieval. Directed `WorkflowGraph` with sequential, parallel, and supervisor routing.
- **Production Governance & Observability**: OpenTelemetry-compatible `Tracer`, real-time `CostGuardrail` budget protection, `PIIRedactor` (masking API keys, SSNs, credit cards, emails), `SafetyGuardrail` (prompt injection detector), and `ShadowEvaluator`.
- **Streaming Gateway & Async Queue**: W3C Server-Sent Events (`SSEStreamFormatter`) streaming, `DynamicProviderRouter` zero-downtime failover, and `AsyncTaskQueue` worker pool with Dead Letter Queue (DLQ).
- **Enterprise Security & Auth**: `TokenAuthenticator` API token resolution, `PolicyEngine` (PBAC & RBAC authorization), `TokenBucketRateLimiter` sliding window token buckets, and `PlatformIntegrationHarness`.
- **Operational CLI & Deployment**: Command-line interface (`hop`), multi-stage production `Dockerfile`, Kubernetes manifests (`deploy/k8s/`), and OpenAPI 3.0 specification (`docs/openapi.yaml`).

---

## 📐 System Architecture

```
                                  ┌─────────────────────────────┐
                                  │       Client Applications   │
                                  └──────────────┬──────────────┘
                                                 │ Bearer Token / HTTP
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    HOP Security & Auth Gateway                              │
├──────────────────────────────┬───────────────────────────────┬──────────────────────────────┤
│ TokenAuthenticator (Auth)    │ PolicyEngine (RBAC / PBAC)    │ TokenBucketRateLimiter (RPM) │
└──────────────────────────────┴──────────────┬────────────────┴──────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Governance & Observability Layer                            │
├──────────────────────────────┬───────────────────────────────┬──────────────────────────────┤
│ OpenTelemetry Tracer Spans   │ Real-time CostGuardrail ($)   │ PIIRedactor & Safety Guard   │
└──────────────────────────────┴──────────────┬────────────────┴──────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                              Dynamic Provider Router & Failover                             │
├─────────────────────────────────────────────┬───────────────────────────────────────────────┤
│ Primary Provider (OpenAI)                   │ Secondary Fallback (Anthropic)                │
│ [CircuitBreaker: CLOSED]                    │ [CircuitBreaker: CLOSED]                      │
└─────────────────────────────────────────────┴───────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                              Multi-Agent Workflow & Memory Engine                           │
├─────────────────────────────────────────────┬───────────────────────────────────────────────┤
│ MemoryManager (Context Compaction)          │ WorkflowGraph (Sequential/Parallel/Supervisor)│
└─────────────────────────────────────────────┴───────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                            Streaming Gateway & Async Queue Engine                           │
├─────────────────────────────────────────────┬───────────────────────────────────────────────┤
│ SSEStreamFormatter (W3C text/event-stream)  │ AsyncTaskQueue & Dead Letter Queue (DLQ)      │
└─────────────────────────────────────────────┴───────────────────────────────────────────────┘
```

---

## ⚙️ Installation & Quickstart

```bash
# Clone repository
git clone https://github.com/user/hop.git
cd hop

# Install package with all dependencies in editable mode
pip install -e ".[all]"
```

---

## 💻 CLI Usage (`hop`)

The platform includes a CLI runner for operations, benchmarking, and status inspection:

```bash
# Start production streaming gateway server
hop serve --port 8000

# Execute shadow evaluation benchmark suite
hop eval_run --suite default

# Inspect async task queue depth & DLQ status
hop queue_status

# Generate tenant spending summary
hop cost_summary --tenant tenant_acme

# Verify API security token & PBAC permissions
hop security_verify --token Bearer_secret_123
```

---

## 🧪 Testing & Verification

Run unit and integration test suite across all 8 architectural phases:

```bash
python -m pytest tests/ -v
```

---

## 🐳 Production Deployment

### Docker Compose
```bash
docker-compose -f deploy/docker-compose.yml up -d
```

### Kubernetes (K8s)
```bash
kubectl apply -f deploy/k8s/deployment.yaml
```

---

## 📄 Architectural Decision Records (ADRs)

| ADR ID | Title | Status |
|--------|-------|--------|
| [ADR-0001](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0001-llm-provider-abstraction.md) | LLM Provider Abstraction via Hexagonal Ports & Adapters | Accepted |
| [ADR-0002](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0002-tool-schema-normalization-and-execution-sandbox.md) | Tool Schema Normalization & Sandboxed Execution Engine | Accepted |
| [ADR-0003](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0003-vector-store-and-dense-retrieval-engine.md) | Vector Store & Dense Retrieval Engine Architecture | Accepted |
| [ADR-0004](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0004-multi-agent-workflow-and-conversation-memory-engine.md) | Multi-Agent Workflow & Conversation Memory Architecture | Accepted |
| [ADR-0005](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0005-production-observability-cost-guardrails-and-eval-engine.md) | Production Observability, Cost Guardrails & Evaluation Architecture | Accepted |
| [ADR-0006](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0006-streaming-gateway-dynamic-router-and-async-queue.md) | Streaming Gateway, Dynamic Router & Async Queue Architecture | Accepted |
| [ADR-0007](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0007-enterprise-security-pbac-auth-and-verification-harness.md) | Enterprise Security, PBAC Auth & Verification Harness Architecture | Accepted |
| [ADR-0008](file:///Users/barankurtulusozan/hop/docs/adrs/ADR-0008-production-deployment-cli-and-ecosystem-architecture.md) | Production Deployment, CLI & Ecosystem Architecture | Accepted |
