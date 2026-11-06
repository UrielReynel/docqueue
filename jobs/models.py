import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

KEY_PREFIX = "dq"


def hash_secret(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class APIKey(models.Model):
    """An API key. Only its SHA-256 hash is stored; the raw key is shown once."""

    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, unique=True, db_index=True)
    hashed_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix})"

    @classmethod
    def generate(cls, name: str) -> tuple["APIKey", str]:
        """Create a key and return (instance, raw_key). The raw key is never stored."""
        prefix = secrets.token_hex(4)
        raw_key = f"{KEY_PREFIX}_{prefix}_{secrets.token_urlsafe(32)}"
        instance = cls.objects.create(name=name, prefix=prefix, hashed_key=hash_secret(raw_key))
        return instance, raw_key

    def matches(self, raw_key: str) -> bool:
        return secrets.compare_digest(self.hashed_key, hash_secret(raw_key))


def next_nightly_run(now: datetime | None = None) -> datetime:
    """Next occurrence of DOCQUEUE_NIGHTLY_HOUR in the configured local time zone."""
    now = timezone.localtime(now or timezone.now())
    run = now.replace(hour=settings.DOCQUEUE_NIGHTLY_HOUR, minute=0, second=0, microsecond=0)
    if run <= now:
        run += timedelta(days=1)
    return run


def upload_path(instance: "Job", filename: str) -> str:
    return f"uploads/{instance.id}/{filename}"


class Job(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        PROCESSING = "processing"
        DONE = "done"
        FAILED = "failed"

    class Mode(models.TextChoices):
        NOW = "now"  # on-demand: eligible immediately
        NIGHTLY = "nightly"  # batch: eligible at the next nightly window

    class Kind(models.TextChoices):
        PDF = "pdf"
        IMAGE = "image"
        TEXT = "text"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name="jobs")
    file = models.FileField(upload_to=upload_path)
    original_name = models.CharField(max_length=255)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.NOW)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED, db_index=True)
    run_after = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "run_after"])]

    def __str__(self) -> str:
        return f"{self.original_name} [{self.status}]"
