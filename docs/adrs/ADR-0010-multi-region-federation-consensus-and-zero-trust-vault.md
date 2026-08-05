# ADR-0010: Multi-Region Active-Active Federation, Raft Consensus & Zero-Trust Vault

## Status
Accepted

## Date
2026-08-05

## Context & Problem Statement
To ensure multi-datacenter high availability and key security across global enterprises:
1. **Multi-Region Active-Active Federation**: Latency-aware routing across global region nodes (`MultiRegionNodeManager`).
2. **Federated Raft Consensus**: Multi-node leader election and state synchronization (`RaftConsensusEngine`).
3. **Zero-Trust Key Vault**: In-memory key isolation and field encryption (`ZeroTrustKeyVault`).

## Decision Drivers
- **Zero External SDK Dependencies**: All federation, consensus, and vault primitives live in `src/domain/federation.py`.
- **Latency-Based Active-Active Routing**: Requests route to the lowest-latency active region node automatically.
- **Payload Field Encryption**: Sensitive attributes are encrypted using zero-trust key isolation.

## Federation & Security Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MultiRegionNodeManager                           │
├──────────────────────────────┬──────────────────────────────┬───────────────┤
│ Region US-East (15ms)        │ Region EU-West (85ms)        │ Region AP-East│
│ [Status: ACTIVE]             │ [Status: ACTIVE]             │ [Status: STBY]│
└──────────────────────────────┴──────────────┬───────────────┴───────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RaftConsensusEngine                              │
├─────────────────────────────────────────────┬───────────────────────────────┤
│ Term Election (Leader / Follower)           │ Cluster State Synchronization │
└─────────────────────────────────────────────┴───────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ZeroTrustKeyVault                                │
├─────────────────────────────────────────────┬───────────────────────────────┤
│ In-Memory Key Isolation                     │ Payload Field Encryption      │
└─────────────────────────────────────────────┴───────────────────────────────┘
```

## Consequences
### Positive
- Global active-active multi-region failover.
- Guaranteed consensus across distributed agent nodes.
- Zero-trust key security protecting credentials in memory.
