"""반복 작업의 공통 Prometheus 계측 도구입니다."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.metrics import (
    WORKER_TASK_DURATION,
    WORKER_TASK_IN_PROGRESS,
    WORKER_TASK_LAST_SUCCESS,
    WORKER_TASK_RUNS,
)


@contextmanager
def observe_worker_task(task: str) -> Iterator[None]:
    """서비스와 무관하게 반복 작업의 실행 상태와 결과를 기록합니다."""
    started_at = time.monotonic()
    WORKER_TASK_IN_PROGRESS.labels(task).inc()
    try:
        yield
    except Exception:
        WORKER_TASK_RUNS.labels(task, "error").inc()
        raise
    else:
        WORKER_TASK_RUNS.labels(task, "success").inc()
        WORKER_TASK_LAST_SUCCESS.labels(task).set_to_current_time()
    finally:
        WORKER_TASK_DURATION.labels(task).observe(time.monotonic() - started_at)
        WORKER_TASK_IN_PROGRESS.labels(task).dec()
