from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prodrag.models import FlowEvent, FlowStatus

FlowCallback = Callable[[FlowEvent], None]


def emit_flow_event(
    callback: FlowCallback | None,
    *,
    operation_id: str,
    stage: str,
    status: FlowStatus,
    message: str,
    duration_ms: float | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Publish an optional diagnostic event without making tracing a failure path."""
    if callback is None:
        return
    event = FlowEvent(
        operation_id=operation_id,
        stage=stage,
        status=status,
        message=message,
        duration_ms=round(duration_ms, 3) if duration_ms is not None else None,
        data=data or {},
    )
    try:
        callback(event)
    except Exception:
        # A disconnected browser or unavailable progress store must never break
        # ingestion, retrieval, or grounded answer generation.
        return
