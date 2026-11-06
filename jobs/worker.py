"""Database-backed job queue.

Claiming uses a compare-and-set UPDATE (`WHERE status='queued'`), so two workers
can poll the same table and a job is still processed only once, on any database
Django supports, without Redis or a message broker.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Job
from .processors import PROCESSORS

log = logging.getLogger(__name__)


def claim_next() -> Job | None:
    """Atomically move the oldest eligible job from queued to processing."""
    now = timezone.now()
    candidates = (
        Job.objects.filter(status=Job.Status.QUEUED, run_after__lte=now)
        .order_by("run_after", "created_at")
        .values_list("pk", flat=True)[:10]
    )
    for pk in candidates:
        claimed = Job.objects.filter(pk=pk, status=Job.Status.QUEUED).update(
            status=Job.Status.PROCESSING, started_at=now
        )
        if claimed:  # another worker did not get there first
            return Job.objects.get(pk=pk)
    return None


def retry_delay(attempt: int) -> timedelta:
    """Exponential backoff: base, 2x base, 4x base, ..."""
    return timedelta(seconds=settings.DOCQUEUE_RETRY_BASE_SECONDS * 2 ** (attempt - 1))


def run_job(job: Job) -> Job:
    job.attempts += 1
    try:
        processor = PROCESSORS[job.kind]
        with job.file.open("rb") as fh:
            job.result = processor(fh)
    except Exception as exc:  # any failure is recorded on the job, never crashes the worker
        log.warning("job %s failed (attempt %s): %s", job.pk, job.attempts, exc)
        job.error = f"{type(exc).__name__}: {exc}"
        if job.attempts < settings.DOCQUEUE_MAX_ATTEMPTS:
            job.status = Job.Status.QUEUED
            job.run_after = timezone.now() + retry_delay(job.attempts)
        else:
            job.status = Job.Status.FAILED
            job.finished_at = timezone.now()
    else:
        job.status = Job.Status.DONE
        job.error = ""
        job.finished_at = timezone.now()
    job.save()
    return job


def run_once() -> Job | None:
    """Claim and process a single job. Returns it, or None if the queue is empty."""
    job = claim_next()
    return run_job(job) if job else None
