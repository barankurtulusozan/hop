from __future__ import annotations

import asyncio
import logging
import time

from src.domain.exceptions import RateLimitViolationError
from src.domain.security import RateLimitTier

logger = logging.getLogger("llm_orchestrator.security.rate_limiter")

DEFAULT_TIER_RPM: dict[RateLimitTier, int] = {
    RateLimitTier.FREE: 10,
    RateLimitTier.STANDARD: 60,
    RateLimitTier.ENTERPRISE: 1000,
}


class TokenBucketRateLimiter:
    """Sliding-window token bucket rate limiter enforcing tenant Requests-Per-Minute (RPM) ceilings."""

    def __init__(self, tier_rpm: dict[RateLimitTier, int] | None = None):
        self.tier_rpm = tier_rpm or DEFAULT_TIER_RPM
        self._requests: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, tenant_id: str, tier: RateLimitTier = RateLimitTier.STANDARD) -> bool:
        max_rpm = self.tier_rpm.get(tier, 60)
        now = time.time()
        window_start = now - 60.0

        async with self._lock:
            timestamps = self._requests.setdefault(tenant_id, [])
            # Prune expired timestamps outside 60s sliding window
            valid_timestamps = [t for t in timestamps if t >= window_start]

            if len(valid_timestamps) >= max_rpm:
                self._requests[tenant_id] = valid_timestamps
                return False

            valid_timestamps.append(now)
            self._requests[tenant_id] = valid_timestamps
            return True

    async def enforce(self, tenant_id: str, tier: RateLimitTier = RateLimitTier.STANDARD) -> None:
        if not await self.acquire(tenant_id, tier):
            max_rpm = self.tier_rpm.get(tier, 60)
            msg = f"Tenant '{tenant_id}' exceeded rate limit ceiling of {max_rpm} RPM for tier '{tier.value}'"
            logger.warning(f"Rate limit violation: {msg}")
            raise RateLimitViolationError(msg)
