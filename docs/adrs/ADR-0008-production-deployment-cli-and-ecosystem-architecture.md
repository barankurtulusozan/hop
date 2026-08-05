# ADR-0008: Production Deployment, CLI & Ecosystem Architecture

## Status
Accepted

## Date
2026-08-05

## Context & Problem Statement
To transition the platform into a production-ready enterprise solution, the platform requires:
1. **Command Line Operations**: Unified CLI tool (`hop`) for serving API gateways, benchmarking evaluations, inspecting queue health, and auditing tenant costs.
2. **Infrastructure Automation**: Production-ready multi-stage `Dockerfile`, local `docker-compose.yml`, and Kubernetes manifests (`deploy/k8s/`) with horizontal autoscaling (HPA) and probe endpoints.
3. **OpenAPI Specification**: Formal OpenAPI 3.0 specification (`docs/openapi.yaml`) defining chat completions, agent workflows, shadow evals, and queue task endpoints.

## Decision Drivers
- **Hexagonal CLI Isolation**: CLI subcommands execute through public domain ports without direct private state mutation.
- **Production Containerization**: Multi-stage Docker build producing lightweight runtime images under non-root permissions.
- **Kubernetes Cloud Standard**: High-availability Kubernetes manifests with CPU utilization autoscaling (75% threshold) and probe healthchecks.

## Production Ecosystem Diagram

```
                               ┌───────────────────────────┐
                               │   OpenAPI 3.0 Contract    │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            HOP CLI Engine (`hop`)                           │
├─────────────┬─────────────┬─────────────────┬──────────────┬────────────────┤
│    serve    │  eval_run   │  queue_status   │ cost_summary │security_verify │
└─────────────┴─────────────┴─────────────────┴──────────────┴────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Kubernetes Production Deployment Stack                   │
│  - Deployment (3-10 Replicas HPA)   - ClusterIP Service                     │
│  - Multi-stage Docker Runtime       - Liveness & Readiness Probes         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Consequences
### Positive
- One-command operations via `hop` CLI.
- Standardized container builds ready for AWS EKS, GCP GKE, or Azure AKS.
- Complete API discovery via OpenAPI 3.0 contract.
