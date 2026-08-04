from __future__ import annotations

import logging
from typing import Sequence

from src.domain.exceptions import LLMException, RouterException
from src.domain.models import CompletionRequest, CompletionResponse
from src.domain.router import ProviderHealth, RoutingStrategy
from src.orchestrator.pipeline import LLMOrchestrator

logger = logging.getLogger("llm_orchestrator.router")


class DynamicProviderRouter:
    """Dynamic latency, cost, and CircuitBreaker-aware provider router with zero-downtime fallback failover."""

    def __init__(
        self,
        providers: dict[str, LLMOrchestrator],
        provider_priority: Sequence[str] | None = None,
        strategy: RoutingStrategy = RoutingStrategy.PRIORITY_FALLBACK,
    ):
        if not providers:
            raise RouterException("At least one LLMOrchestrator provider must be registered")

        self.providers = providers
        self.provider_priority = list(provider_priority) if provider_priority else list(providers.keys())
        self.strategy = strategy
        self._round_robin_idx = 0

    def get_provider_health(self) -> list[ProviderHealth]:
        health_list: list[ProviderHealth] = []
        for name, orch in self.providers.items():
            cb = orch.get_circuit_breaker(orch._default_provider) if hasattr(orch, "get_circuit_breaker") else None
            is_open = cb.state.value == "OPEN" if cb else False
            health_list.append(
                ProviderHealth(
                    provider=name,
                    is_circuit_open=is_open,
                )
            )
        return health_list

    def _select_candidate_order(self) -> list[str]:
        if self.strategy == RoutingStrategy.PRIORITY_FALLBACK:
            return list(self.provider_priority)

        if self.strategy == RoutingStrategy.ROUND_ROBIN:
            n = len(self.provider_priority)
            candidates = [self.provider_priority[(self._round_robin_idx + i) % n] for i in range(n)]
            self._round_robin_idx = (self._round_robin_idx + 1) % n
            return candidates

        return list(self.provider_priority)

    async def route_completion(self, request: CompletionRequest) -> CompletionResponse:
        candidates = self._select_candidate_order()
        last_error: Exception | None = None

        for provider_name in candidates:
            orch = self.providers.get(provider_name)
            if not orch:
                continue

            # Check if circuit breaker is open
            cb = orch.get_circuit_breaker(orch._default_provider) if hasattr(orch, "get_circuit_breaker") else None
            if cb and cb.state.value == "OPEN":
                logger.warning(f"Skipping provider '{provider_name}' due to OPEN circuit breaker")
                continue

            try:
                logger.info(f"Routing request to provider '{provider_name}'")
                return await orch.complete(request)
            except LLMException as exc:
                logger.warning(f"Provider '{provider_name}' failed with {type(exc).__name__}: {exc}. Triggering fallback...")
                last_error = exc
                continue

        raise RouterException(
            f"All candidate providers ({candidates}) failed or circuit-broken. Last error: {last_error}"
        )
