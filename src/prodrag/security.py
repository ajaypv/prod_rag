from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status
from pydantic import SecretStr

from prodrag.config import get_settings


@dataclass(frozen=True, slots=True)
class AuthContext:
    tenant_id: str | None


def _authenticate(
    provided_key: str | None,
    tenant_keys: dict[str, SecretStr],
    legacy_key: SecretStr | None,
    *,
    header_name: str,
) -> AuthContext:
    if provided_key is not None:
        for tenant_id, configured in tenant_keys.items():
            if secrets.compare_digest(configured.get_secret_value(), provided_key):
                return AuthContext(tenant_id=tenant_id)

    settings = get_settings()
    if settings.environment != "production":
        if legacy_key is None and not tenant_keys:
            return AuthContext(tenant_id=None)
        if legacy_key is not None and provided_key is not None and secrets.compare_digest(
            legacy_key.get_secret_value(), provided_key
        ):
            return AuthContext(tenant_id=None)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"A valid {header_name} header is required",
    )


def authorize_tenant(auth: AuthContext, requested_tenant: str) -> None:
    if auth.tenant_id is not None and not secrets.compare_digest(
        auth.tenant_id, requested_tenant
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The authenticated key is not authorized for this tenant",
        )


def require_admin_key(
    provided_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> AuthContext:
    settings = get_settings()
    return _authenticate(
        provided_key,
        settings.tenant_admin_api_keys,
        settings.admin_api_key,
        header_name="X-Admin-Key",
    )


def require_query_key(
    provided_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthContext:
    settings = get_settings()
    return _authenticate(
        provided_key,
        settings.tenant_query_api_keys,
        settings.query_api_key,
        header_name="X-API-Key",
    )
