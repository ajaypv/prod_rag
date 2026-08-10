from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from prodrag.config import get_settings


def require_admin_key(
    provided_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> None:
    configured = get_settings().admin_api_key
    if configured is None and get_settings().environment != "production":
        return
    if configured is None or provided_key is None or not secrets.compare_digest(
        configured.get_secret_value(), provided_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-Admin-Key header is required",
        )


def require_query_key(
    provided_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    configured = get_settings().query_api_key
    if configured is None and get_settings().environment != "production":
        return
    if configured is None or provided_key is None or not secrets.compare_digest(
        configured.get_secret_value(), provided_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-API-Key header is required",
        )
