from __future__ import annotations

import asyncio
import time
from typing import Any

from src.domain.exceptions import CostBudgetExceeded
from src.domain.observability import CostLimit

DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    # model: (prompt_cost_per_1k_usd, completion_cost_per_1k_usd)
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "text-embedding-3-small": (0.00002, 0.0),
    "mock-model": (0.00001, 0.00001),
}


class CostGuardrail:
    """Real-time token cost calculation and tenant budget enforcement guardrail."""

    def __init__(self, pricing_table: dict[str, tuple[float, float]] | None = None):
        self.pricing_table = dict(pricing_table or DEFAULT_PRICING)
        self._limits: dict[str, CostLimit] = {}
        self._token_rate_window: dict[str, list[tuple[float, int]]] = {}
        self._lock = asyncio.Lock()

    async def set_limit(self, tenant_id: str, limit: CostLimit) -> None:
        async with self._lock:
            self._limits[tenant_id] = limit

    async def get_spend(self, tenant_id: str) -> float:
        async with self._lock:
            limit = self._limits.get(tenant_id)
            return limit.current_daily_spend_usd if limit else 0.0

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        prompt_rate, completion_rate = self.pricing_table.get(model, (0.001, 0.002))
        cost_prompt = (prompt_tokens / 1000.0) * prompt_rate
        cost_completion = (completion_tokens / 1000.0) * completion_rate
        return round(cost_prompt + cost_completion, 6)

    async def check_and_record_usage(
        self,
        tenant_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens)
        now = time.time()
        total_tokens = prompt_tokens + completion_tokens

        async with self._lock:
            limit = self._limits.get(tenant_id)
            if not limit:
                # Default unlimited limit container
                limit = CostLimit(tenant_id=tenant_id, max_daily_budget_usd=100.0)
                self._limits[tenant_id] = limit

            # 1. Rate Limit Window Check (per-minute sliding window)
            window = self._token_rate_window.setdefault(tenant_id, [])
            # Prune events older than 60 seconds
            window = [(t, count) for t, count in window if now - t <= 60.0]
            current_tpm = sum(count for _, count in window)

            if current_tpm + total_tokens > limit.max_tokens_per_minute:
                raise CostBudgetExceeded(
                    message=f"Per-minute token rate limit exceeded ({current_tpm + total_tokens} > {limit.max_tokens_per_minute})",
                    tenant_id=tenant_id,
                )

            # 2. Daily USD Budget Check
            new_daily_spend = limit.current_daily_spend_usd + cost
            if new_daily_spend > limit.max_daily_budget_usd:
                raise CostBudgetExceeded(
                    message=f"Daily spending budget exceeded (${new_daily_spend:.4f} > ${limit.max_daily_budget_usd:.2f})",
                    tenant_id=tenant_id,
                )

            # Record spend and token window event
            window.append((now, total_tokens))
            self._token_rate_window[tenant_id] = window
            self._limits[tenant_id] = CostLimit(
                tenant_id=limit.tenant_id,
                max_daily_budget_usd=limit.max_daily_budget_usd,
                max_tokens_per_minute=limit.max_tokens_per_minute,
                current_daily_spend_usd=new_daily_spend,
            )

        return cost
