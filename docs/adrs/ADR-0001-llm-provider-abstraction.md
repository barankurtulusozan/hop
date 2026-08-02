# ADR-0001: LLM Provider Abstraction via Hexagonal Ports & Adapters

**Status:** Accepted
**Date:** 2026-08-02
**Deciders:** Platform team (Phase 1, PLAT-101)

## Context & Problem Statement

Multiple product teams currently import `openai` or `anthropic` SDKs directly
inside business/product code. This has produced three concrete failure modes
observed in production incidents:

1. **Vendor lock-in.** Swapping providers, or even swapping models within the
   same provider's newer SDK version, requires coordinated edits across every
   downstream service that imports the SDK directly.
2. **Fragile error handling.** `429` and `5xx` responses are handled
   inconsistently (or not at all) per call site, so transient failures
   surface as user-facing errors instead of being retried.
3. **Zero observability.** Latency, token usage, and failure rate are not
   captured anywhere centrally, so there is no way to answer "which provider
   is costing us the most" or "is our p99 latency getting worse" without
   grepping individual service logs.
4. **Security risk.** API keys are passed as plain strings through multiple
   layers, and at least one incident involved a raw key appearing in an
   error-log stack trace.

We need a single, provider-agnostic execution layer that all product code
depends on, so vendor SDKs are isolated behind a stable internal contract.

## Alternatives Considered

**1. Direct SDK calls per service (status quo).**
Zero migration cost, but does not solve any of the four problems above; each
service continues to reinvent retry/backoff and logging independently, with
inconsistent quality.

**2. Adopt LangChain or LlamaIndex as the abstraction layer.**
Gets us a provider abstraction for free and a large ecosystem of integrations.
Rejected for this use case because:
- These frameworks bundle a large surface area (agents, memory, vector
  stores, prompt templates) we do not need; our requirement is narrowly
  "one completion/streaming contract with retries and telemetry."
- Their abstractions change quickly across releases, which reintroduces a
  vendor-lock-in problem one layer up (lock-in to the framework instead of
  to OpenAI/Anthropic).
- Debugging retry/backoff behavior inside a third-party framework is harder
  than owning \~200 lines of retry logic we wrote and fully understand.
- We still need to write custom exception translation and telemetry either
  way, since neither framework's error types map cleanly onto our internal
  domain exceptions.

**3. Hexagonal Ports & Adapters (chosen).**
A small `LLMProvider` interface (the port) that all adapters implement, with
domain models (`CompletionRequest`, `CompletionResponse`, `TokenUsage`,
`StreamChunk`) that contain zero vendor types. Business code and the
orchestrator depend only on the port; the port has two implementations today
(OpenAI, Anthropic) and a deterministic `MockAdapter` for tests.

## Decision

Adopt Hexagonal Ports & Adapters, as implemented in `src/domain`,
`src/adapters`, and `src/orchestrator`.

**Enforced boundary rule:** only files under `src/adapters/` may import
`openai`, `anthropic`, or `httpx`. This is currently enforced by convention
and verified in code review; a lint rule (e.g. `import-linter` contract) is
the recommended Phase 2 follow-up to make the boundary machine-checked
instead of review-checked.

**Trade-off matrix:**

| Criterion | Direct SDK calls | LangChain/LlamaIndex | Hex Ports & Adapters |
|---|---|---|---|
| Migration cost | None | Medium | Medium |
| Vendor lock-in | High | Medium (framework lock-in) | Low |
| Retry/observability consistency | None (per-service) | Partial, framework-owned | Full, owned & testable |
| Surface area / cognitive load | Low | High | Low–Medium |
| Debuggability of failures | N/A | Low (third-party internals) | High (our code) |
| Extensibility to a 3rd provider | Rewrite call sites | Add integration | Add one adapter file |

## Consequences

**Positive:**
- Adding a new provider (e.g. a self-hosted vLLM endpoint) means writing one
  new adapter file; the orchestrator, retry logic, and telemetry are unchanged.
- All resilience behavior (backoff, jitter, retry budget) lives in one place
  (`orchestrator/pipeline.py`) and is unit-testable without live API calls,
  via `MockAdapter`'s scripted failure sequences.
- Secrets are wrapped in `SecretStr` at the config boundary and only unwrapped
  once, inside the adapter constructor, at the point of handing the key to
  the vendor SDK's own transport.

**Negative / accepted costs:**
- Every new field a vendor API exposes (e.g. a new OpenAI response field)
  requires a deliberate decision: extend the domain model, or leave it
  unmapped. This is intentional friction — it prevents vendor-specific
  concepts leaking into domain code — but it does mean the domain model
  needs active maintenance as vendor APIs evolve.
- Streaming retry semantics are more restrictive than a naive "retry
  anything": we only retry a connection failure that happens *before* the
  first chunk is yielded, since a partially-streamed response cannot be
  safely replayed to a caller mid-render. Call sites that need resumable
  streaming will need an additional buffering layer on top of this
  orchestrator, not inside it.

## Future Extension Rules

1. **No vendor imports outside `src/adapters/`.** Any PR introducing an
   `import openai` / `import anthropic` / `import httpx` outside that
   directory should fail review. A CI import-linter contract is the
   recommended way to make this automatic rather than reviewer-dependent.
2. **New failure modes get a domain exception first.** If a vendor
   introduces a new error class we care about (e.g. content-policy
   rejection), add it to `domain/exceptions.py` before wiring adapter
   translation for it — the domain model should never be inferred backwards
   from a single vendor's exception taxonomy.
3. **Routing beyond "one active provider" (e.g. cost-based or
   latency-based multi-provider routing) belongs in the orchestrator, not
   in adapters or business code.** Adapters must stay dumb translators.
4. **Any new adapter must ship with a corresponding entry in
   `MockAdapter`-based integration tests** demonstrating at least one
   retryable and one non-retryable failure path, before merge.
