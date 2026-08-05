from __future__ import annotations

import logging

from src.domain.exceptions import AuthorizationError
from src.domain.security import Permission, Role, TenantContext

logger = logging.getLogger("llm_orchestrator.security.policy")


class PolicyEngine:
    """Policy-Based (PBAC) & Role-Based (RBAC) access control enforcement engine."""

    def check_permission(self, context: TenantContext, permission: Permission) -> bool:
        # Admin role grants all permissions
        if Role.ADMIN in context.roles:
            return True

        return permission in context.permissions

    def enforce(self, context: TenantContext, permission: Permission) -> None:
        if not self.check_permission(context, permission):
            msg = f"Tenant '{context.tenant_id}', user '{context.user_id}' lacks required permission '{permission.value}'"
            logger.warning(f"Authorization failed: {msg}")
            raise AuthorizationError(msg)

        logger.info(f"Authorization granted: '{permission.value}' for tenant '{context.tenant_id}'")
