# ADR-0007: Enterprise Security, PBAC Auth & Verification Harness Architecture

## Status
Accepted

## Date
2026-08-05

## Context & Problem Statement
For enterprise deployment, the platform requires multi-tenant authentication, granular policy enforcement, rate limiting, and an end-to-end verification harness:
1. **Authentication & Identity Resolution**: Bearer token authentication resolving API tokens to `TenantContext`.
2. **Policy-Based Access Control (PBAC / RBAC)**: Strict permission checks (`Permission.AGENT_RUN`, `Permission.TOOL_INVOKE`, etc.) preventing unauthorized tenant operations.
3. **Sliding-Window Rate Limiting**: Per-tenant requests-per-minute (RPM) token bucket rate limiting based on `RateLimitTier`.
4. **End-to-End Platform Verification Harness**: `PlatformIntegrationHarness` validating the full request execution stack.

## Decision Drivers
- **Hexagonal Security Boundary**: Zero external identity provider SDK dependencies in `src/domain/security.py`.
- **RBAC/PBAC Authorization**: Roles (`ADMIN`, `DEVELOPER`, `OPERATOR`) and permissions checked explicitly before tool execution or agent turns.
- **Unified Production Verification**: `PlatformIntegrationHarness` exercises auth, rate limiting, safety, cost guardrails, routing, agent workflows, streaming, and evaluations in a single testable pipeline.

## System Integration Flow

```
   Bearer Token ──► TokenAuthenticator ──► TenantContext
                           │
                           ▼
                 TokenBucketRateLimiter ──► (RPM Check)
                           │
                           ▼
                      PolicyEngine ──► (PBAC Permission Check)
                           │
                           ▼
                   SafetyGuardrail ──► (PII Redaction & Injection Detection)
                           │
                           ▼
                    CostGuardrail ──► (Daily USD & Token Ceiling Check)
                           │
                           ▼
                 DynamicProviderRouter ──► (CircuitBreaker Failover)
                           │
                           ▼
                 Agent / WorkflowGraph ──► (OpenTelemetry Tracer Span)
                           │
                           ▼
                  SSEStreamFormatter ──► (W3C text/event-stream)
                           │
                           ▼
                    ShadowEvaluator ──► (Quality & Latency Scoring)
```

## Consequences
### Positive
- Enterprise-grade security boundary isolating tenants and enforcing granular policy contracts.
- Rate limiting prevents API resource exhaustion.
- End-to-end harness guarantees complete platform integration stability across all 7 architectural phases.
