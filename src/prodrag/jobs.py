from __future__ import annotations

from redis import Redis

from prodrag.models import EvaluationJobStatus, JobStatus


class RedisJobStore:
    def __init__(self, redis_url: str, *, ttl_seconds: int) -> None:
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(job_id: str) -> str:
        return f"prodrag:ingestion:{job_id}"

    @staticmethod
    def _evaluation_key(job_id: str) -> str:
        return f"prodrag:evaluation:{job_id}"

    def put(self, status: JobStatus) -> None:
        self.client.setex(
            self._key(status.job_id),
            self.ttl_seconds,
            status.model_dump_json(),
        )

    def get(self, job_id: str) -> JobStatus | None:
        payload = self.client.get(self._key(job_id))
        return JobStatus.model_validate_json(payload) if payload else None

    def put_evaluation(self, status: EvaluationJobStatus) -> None:
        self.client.setex(
            self._evaluation_key(status.job_id),
            self.ttl_seconds,
            status.model_dump_json(),
        )

    def get_evaluation(self, job_id: str) -> EvaluationJobStatus | None:
        payload = self.client.get(self._evaluation_key(job_id))
        return EvaluationJobStatus.model_validate_json(payload) if payload else None

    def ping(self) -> bool:
        return bool(self.client.ping())

