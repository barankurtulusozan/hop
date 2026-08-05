import pytest

from src.domain.exceptions import AuthenticationError, AuthorizationError, RateLimitViolationError
from src.domain.security import Permission, RateLimitTier, Role, TenantContext
from src.security.auth import TokenAuthenticator
from src.security.policy import PolicyEngine
from src.security.rate_limiter import TokenBucketRateLimiter


def test_token_authenticator():
    auth = TokenAuthenticator()
    ctx = TenantContext(
        tenant_id="tenant_acme",
        user_id="user_john",
        roles=[Role.DEVELOPER],
        permissions=[Permission.AGENT_RUN],
    )
    auth.register_token("secret_token_123", ctx)

    res = auth.authenticate("Bearer secret_token_123")
    assert res.tenant_id == "tenant_acme"
    assert res.user_id == "user_john"

    with pytest.raises(AuthenticationError, match="Invalid API token"):
        auth.authenticate("Bearer invalid_token")

    with pytest.raises(AuthenticationError, match="Missing Bearer API token"):
        auth.authenticate(None)


def test_policy_engine_pbac():
    engine = PolicyEngine()
    dev_ctx = TenantContext(
        tenant_id="t1",
        user_id="u1",
        roles=[Role.DEVELOPER],
        permissions=[Permission.AGENT_RUN],
    )
    admin_ctx = TenantContext(
        tenant_id="t2",
        user_id="u2",
        roles=[Role.ADMIN],
        permissions=[],
    )

    # Permission explicitly granted
    assert engine.check_permission(dev_ctx, Permission.AGENT_RUN) is True
    engine.enforce(dev_ctx, Permission.AGENT_RUN)

    # Permission missing
    assert engine.check_permission(dev_ctx, Permission.CONFIG_MANAGE) is False
    with pytest.raises(AuthorizationError, match="lacks required permission"):
        engine.enforce(dev_ctx, Permission.CONFIG_MANAGE)

    # Admin bypasses all checks
    assert engine.check_permission(admin_ctx, Permission.CONFIG_MANAGE) is True
    engine.enforce(admin_ctx, Permission.CONFIG_MANAGE)


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter():
    # Set FREE tier to 2 RPM for testing
    limiter = TokenBucketRateLimiter(tier_rpm={RateLimitTier.FREE: 2})

    # First 2 requests succeed
    await limiter.enforce("tenant_free", RateLimitTier.FREE)
    await limiter.enforce("tenant_free", RateLimitTier.FREE)

    # 3rd request breaches RPM ceiling
    with pytest.raises(RateLimitViolationError, match="exceeded rate limit ceiling"):
        await limiter.enforce("tenant_free", RateLimitTier.FREE)
