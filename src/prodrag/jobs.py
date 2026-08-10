from __future__ import annotations

from redis import Redis

from prodrag.models import JobStatus


class RedisJobStore:
    def __init__(self, redis_url: str, *, ttl_seconds: int) -> None:
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(job_id: str) -> str:
        return f"prodrag:ingestion:{job_id}"

    def put(self, status: JobStatus) -> None:
        self.client.setex(
            self._key(status.job_id),
            self.ttl_seconds,
            status.model_dump_json(),
        )

    def get(self, job_id: str) -> JobStatus | None:
        payload = self.client.get(self._key(job_id))
        return JobStatus.model_validate_json(payload) if payload else None

    def ping(self) -> bool:
        return bool(self.client.ping())

