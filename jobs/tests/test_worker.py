from datetime import timedelta

from django.utils import timezone

from jobs import worker
from jobs.models import Job
from jobs.processors import text_quality

from .conftest import text_file


def upload(client, f, **extra):
    return Job.objects.get(
        pk=client.post("/api/jobs/", {"file": f, **extra}, format="multipart").json()["id"]
    )


def test_processes_pdf(client, pdf_file):
    upload(client, pdf_file)
    job = worker.run_once()
    assert job.status == Job.Status.DONE
    assert job.result["pages"] == 1
    assert job.result["title"] == "Test document"


def test_processes_image(client, png_file):
    upload(client, png_file)
    job = worker.run_once()
    assert job.result == {"format": "PNG", "width": 40, "height": 30, "mode": "RGB", "has_exif": False}


def test_processes_text_and_detects_mojibake(client):
    upload(client, text_file("InformaciÃ³n del cliente\n"))  # "Información" decoded wrongly
    job = worker.run_once()
    assert job.result["encoding"] == "utf-8"
    assert job.result["quality"]["looks_broken"] is True


def test_falls_back_to_cp1252(client):
    upload(client, text_file("Año 2026, señal clara\n", encoding="cp1252"))
    job = worker.run_once()
    assert job.result["encoding"] == "cp1252"
    assert job.result["quality"]["looks_broken"] is False
    assert "señal" in job.result["preview"]


def test_text_quality_clean():
    assert text_quality("Información correcta")["looks_broken"] is False


def test_nightly_jobs_wait_for_their_window(client):
    job = upload(client, text_file("later"), mode="nightly")
    assert worker.run_once() is None
    Job.objects.filter(pk=job.pk).update(run_after=timezone.now() - timedelta(seconds=1))
    assert worker.run_once().status == Job.Status.DONE


def test_failed_job_is_retried_with_backoff_then_fails(client, settings):
    settings.DOCQUEUE_MAX_ATTEMPTS = 2
    job = upload(client, text_file("ok"))
    Job.objects.filter(pk=job.pk).update(kind="pdf")  # force the PDF parser on plain text

    first = worker.run_once()
    assert first.status == Job.Status.QUEUED
    assert first.attempts == 1
    assert first.run_after > timezone.now()
    assert first.error

    Job.objects.filter(pk=job.pk).update(run_after=timezone.now())
    second = worker.run_once()
    assert second.status == Job.Status.FAILED
    assert second.attempts == 2


def test_a_job_is_claimed_only_once(client):
    upload(client, text_file("once"))
    first = worker.claim_next()
    assert first is not None
    assert worker.claim_next() is None  # already processing


def test_retry_delay_doubles(settings):
    settings.DOCQUEUE_RETRY_BASE_SECONDS = 30
    assert [worker.retry_delay(n).seconds for n in (1, 2, 3)] == [30, 60, 120]
