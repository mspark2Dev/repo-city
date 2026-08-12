"""Analysis jobs.

Analysis is fast but not instant, and a UI that freezes for a few seconds on a large
repository looks broken. Running it as a job with progress lets the canvas show what is
happening instead of nothing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

Status = Literal["running", "done", "error"]


@dataclass(slots=True)
class Job:
    id: str
    project_id: str
    path: str
    status: Status = "running"
    done: int = 0
    total: int = 0
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "jobId": self.id,
            "projectId": self.project_id,
            "status": self.status,
            "done": self.done,
            "total": self.total,
            "error": self.error,
        }


@dataclass(slots=True)
class JobRegistry:
    _jobs: dict[str, Job] = field(default_factory=dict)

    def create(self, project_id: str, path: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], project_id=project_id, path=path)
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
