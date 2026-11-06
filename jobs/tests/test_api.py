from rest_framework.test import APIClient

from jobs.models import APIKey, Job

from .conftest import text_file


def test_upload_returns_202_and_queues(client, pdf_file):
    resp = client.post("/api/jobs/", {"file": pdf_file}, format="multipart")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["kind"] == "pdf"
    assert body["mode"] == "now"


def test_rejects_unsupported_file(client):
    resp = client.post("/api/jobs/", {"file": text_file("MZ\x00binary", name="app.exe")}, format="multipart")
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["file"][0]


def test_rejects_oversized_file(client, settings):
    settings.DOCQUEUE_MAX_UPLOAD_MB = 0
    resp = client.post("/api/jobs/", {"file": text_file("hello")}, format="multipart")
    assert resp.status_code == 400


def test_nightly_mode_is_scheduled_later(client):
    resp = client.post("/api/jobs/", {"file": text_file("hi"), "mode": "nightly"}, format="multipart")
    job = Job.objects.get(pk=resp.json()["id"])
    assert job.run_after > job.created_at


def test_keys_only_see_their_own_jobs(client, png_file):
    client.post("/api/jobs/", {"file": png_file}, format="multipart")
    _, other_raw = APIKey.generate("other")
    other = APIClient()
    other.credentials(HTTP_X_API_KEY=other_raw)
    assert other.get("/api/jobs/").json()["count"] == 0
    job_id = Job.objects.get().pk
    assert other.get(f"/api/jobs/{job_id}/").status_code == 404


def test_filter_by_status(client, png_file):
    client.post("/api/jobs/", {"file": png_file}, format="multipart")
    assert client.get("/api/jobs/?status=queued").json()["count"] == 1
    assert client.get("/api/jobs/?status=done").json()["count"] == 0


def test_retry_only_failed_jobs(client, png_file):
    job_id = client.post("/api/jobs/", {"file": png_file}, format="multipart").json()["id"]
    assert client.post(f"/api/jobs/{job_id}/retry/").status_code == 409
    Job.objects.filter(pk=job_id).update(status=Job.Status.FAILED, attempts=3, error="boom")
    resp = client.post(f"/api/jobs/{job_id}/retry/")
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"
    assert resp.json()["attempts"] == 0
