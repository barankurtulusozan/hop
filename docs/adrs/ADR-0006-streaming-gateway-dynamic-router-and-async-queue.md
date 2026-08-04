# ADR-0006: Streaming Gateway, Dynamic Router & Async Queue Architecture

## Status
Accepted

## Date
2026-08-04

## Context & Problem Statement
To support production multi-tenant web applications and real-time client UIs, the platform requires:
1. **Low-Latency Streaming**: Standardized Server-Sent Events (SSE) streaming format with backpressure and heartbeat support.
2. **Zero-Downtime Fallback Routing**: Dynamic provider routing that inspects provider health scores and `CircuitBreaker` states, failing over automatically when primary providers encounter rate limits or outages.
3. **Background Job Processing**: Prioritized async worker pool and Dead Letter Queue (DLQ) isolation for heavy multi-agent workflows off the main HTTP event loop.

## Decision Drivers
- **W3C SSE Standard**: Stream events formatted strictly per W3C Server-Sent Events specification (`event: chunk\ndata: ...\n\n`).
- **Resilient Fallback**: `DynamicProviderRouter` evaluates `CircuitBreaker` state (`CLOSED`/`OPEN`) to redirect traffic seamlessly.
- **DLQ Failure Safety**: Tasks exceeding maximum retries are moved to a inspectable Dead Letter Queue without crashing workers.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AsyncTaskQueue (DLQ)                             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Worker Dispatch
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DynamicProviderRouter                             │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ - Primary Provider (OpenAI)          │ - Secondary Fallback (Anthropic)     │
│   [CircuitBreaker: OPEN]             │   [CircuitBreaker: CLOSED]           │
└──────────────────────────────────────┴──────────────────────────────────────┘
                                       │ Stream Output
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SSEStreamFormatter                               │
│                         (W3C text/event-stream)                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components:
- **`SSEStreamFormatter`**: Serializes streaming delta chunks and tool calls into SSE format with periodic heartbeats.
- **`DynamicProviderRouter`**: Dynamically routes completion requests according to strategy (`PRIORITY_FALLBACK`, `ROUND_ROBIN`), triggering failover when upstream provider circuits are open.
- **`AsyncTaskQueue`**: Prioritized queue executing background agent tasks with retries and DLQ dead-lettering.

## Consequences
### Positive
- Real-time responsive user experience via SSE streaming.
- Enterprise resilience: primary provider outages do not degrade end-user service availability.
- Reliable background job execution with DLQ inspection.
