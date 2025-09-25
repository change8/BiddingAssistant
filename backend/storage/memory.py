"""In-memory storage for analysis jobs.

This module keeps the implementation intentionally simple so it can be
replaced later by a persistent backend (Redis, SQL, etc.).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class AnalysisJobRecord:
    job_id: str
    status: str
    source: str
    filename: Optional[str] = None
    text_length: int = 0
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    source_text: Optional[str] = None


class InMemoryJobStore:
    """Thread-safe in-memory job store."""

    def __init__(self) -> None:
        self._jobs: Dict[str, AnalysisJobRecord] = {}
        self._lock = threading.Lock()

    # Basic CRUD -----------------------------------------------------------
    def create(self, job: AnalysisJobRecord) -> AnalysisJobRecord:
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[AnalysisJobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields: Any) -> Optional[AnalysisJobRecord]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            return job

    def delete(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def list(self) -> List[AnalysisJobRecord]:
        with self._lock:
            return list(self._jobs.values())

    # Helpers --------------------------------------------------------------
    def __len__(self) -> int:  # pragma: no cover - convenience
        with self._lock:
            return len(self._jobs)

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
