from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response

_DURATION_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "tenant_id",
            "product",
            "version",
            "candidate_count",
            "retrieval_scores",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Counter[tuple[str, str, int]] = Counter()
        self._duration_seconds: Counter[tuple[str, str]] = Counter()
        self._duration_counts: Counter[tuple[str, str]] = Counter()
        self._duration_buckets: Counter[tuple[str, str, float]] = Counter()

    def observe(self, method: str, path: str, status_code: int, duration: float) -> None:
        with self._lock:
            self._requests[(method, path, status_code)] += 1
            self._duration_seconds[(method, path)] += duration
            self._duration_counts[(method, path)] += 1
            for upper_bound in _DURATION_BUCKETS:
                if duration <= upper_bound:
                    self._duration_buckets[(method, path, upper_bound)] += 1

    def render(self) -> str:
        lines = [
            "# HELP prodrag_http_requests_total Total HTTP requests.",
            "# TYPE prodrag_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), value in sorted(self._requests.items()):
                lines.append(
                    "prodrag_http_requests_total"
                    f'{{method="{method}",path="{path}",status="{status}"}} {value}'
                )
            lines.extend(
                [
                    "# HELP prodrag_http_request_duration_seconds HTTP request duration.",
                    "# TYPE prodrag_http_request_duration_seconds histogram",
                ]
            )
            for method, path in sorted(self._duration_counts):
                for upper_bound in _DURATION_BUCKETS:
                    value = self._duration_buckets[(method, path, upper_bound)]
                    lines.append(
                        "prodrag_http_request_duration_seconds_bucket"
                        f'{{method="{method}",path="{path}",le="{upper_bound:g}"}} {value}'
                    )
                count = self._duration_counts[(method, path)]
                total = self._duration_seconds[(method, path)]
                lines.append(
                    "prodrag_http_request_duration_seconds_bucket"
                    f'{{method="{method}",path="{path}",le="+Inf"}} {count}'
                )
                lines.append(
                    "prodrag_http_request_duration_seconds_count"
                    f'{{method="{method}",path="{path}"}} {count}'
                )
                lines.append(
                    "prodrag_http_request_duration_seconds_sum"
                    f'{{method="{method}",path="{path}"}} {total:.6f}'
                )
        return "\n".join(lines) + "\n"


metrics = RequestMetrics()
logger = logging.getLogger("prodrag.http")


async def request_observability_middleware(request: Request, call_next) -> Response:
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_id if 0 < len(supplied_id) <= 128 else str(uuid.uuid4())
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration = time.perf_counter() - started
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        metrics.observe(request.method, path, status_code, duration)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 3),
            },
        )
