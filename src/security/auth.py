from __future__ import annotations

import logging

from src.domain.exceptions import AuthenticationError
from src.domain.security import TenantContext

logger = logging.getLogger("llm_orchestrator.security.auth")


class TokenAuthenticator:
    """Enterprise Bearer token authenticator resolving API tokens to TenantContext."""

    def __init__(self):
        self._tokens: dict[str, TenantContext] = {}

    def register_token(self, token: str, context: TenantContext) -> None:
        self._tokens[token] = context
        logger.info(f"Registered token for tenant '{context.tenant_id}', user '{context.user_id}'")

    def authenticate(self, token: str | None) -> TenantContext:
        if not token:
            raise AuthenticationError("Missing Bearer API token")

        # Support "Bearer <token>" header prefix
        clean_token = token.removeprefix("Bearer ").strip()

        if clean_token not in self._tokens:
            raise AuthenticationError(f"Invalid API token: {clean_token[:4]}***")

        context = self._tokens[clean_token]
        logger.info(f"Authenticated request for tenant '{context.tenant_id}', user '{context.user_id}'")
        return context
