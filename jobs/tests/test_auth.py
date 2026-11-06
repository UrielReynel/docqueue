from rest_framework.test import APIClient

from jobs.models import APIKey


def test_requires_key(db):
    resp = APIClient().get("/api/jobs/")
    assert resp.status_code == 401
    assert resp["WWW-Authenticate"] == "X-API-Key"


def test_rejects_wrong_secret(key):
    instance, raw = key
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw[:-4] + "XXXX")
    assert c.get("/api/jobs/").status_code == 401


def test_rejects_revoked_key(key):
    instance, raw = key
    APIKey.objects.filter(pk=instance.pk).update(revoked=True)
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw)
    assert c.get("/api/jobs/").status_code == 401


def test_raw_key_is_not_stored(key):
    instance, raw = key
    instance.refresh_from_db()
    assert raw not in instance.hashed_key
    assert instance.matches(raw)
    assert instance.last_used_at is None


def test_health_is_public(db):
    resp = APIClient().get("/api/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
