# docqueue

An async file-processing API built with **Django REST Framework**. Clients upload a PDF, image or text file with an API key; a worker processes it in the background (right away, or in a nightly batch window) and the client polls for the result.

It also checks extracted text for **encoding damage** (mojibake like `InformaciÃ³n` instead of `Información`, or `�` replacement characters), the kind of problem that silently breaks search and RAG pipelines.

![CI](https://github.com/UrielReynel/docqueue/actions/workflows/ci.yml/badge.svg)

## How it works

```
 client ──POST /api/jobs/ (X-API-Key, file)──▶ Django API ──▶ jobs table (status=queued)
                                                                     │
                                       worker (manage.py run_worker) │ claims one job at a time
                                                                     ▼
                                          processor (pdf / image / text) ──▶ result JSON
 client ◀──GET /api/jobs/{id}/ (status, result)──────────────────────┘
```

- **API-key auth.** Keys look like `dq_<prefix>_<secret>`. Only a SHA-256 hash is stored, the raw key is shown once, and it's checked with a constant-time comparison. Every query is scoped to the calling key, so one client never sees another client's jobs.
- **Database-backed queue, no broker.** A worker claims a job with a compare-and-set `UPDATE ... WHERE status='queued'`. If two workers race for the same job, only one update succeeds, so each job is processed once, on any database Django supports.
- **On-demand or nightly.** `mode=now` jobs are eligible immediately. `mode=nightly` jobs wait for the next batch window (`DOCQUEUE_NIGHTLY_HOUR`, 02:00 by default).
- **Retries with exponential backoff.** A failing job goes back to the queue after 30 s, 60 s, 120 s… and is marked `failed` after `DOCQUEUE_MAX_ATTEMPTS`. Failed jobs can be re-queued through the API.
- **Content sniffing.** The file kind comes from its first bytes (`%PDF-`, PNG/JPEG/GIF/WebP signatures), not only from the extension. Unsupported or oversized files are rejected at upload.

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py create_api_key my-laptop   # prints the key once
uv run python manage.py runserver                  # terminal 1
uv run python manage.py run_worker                 # terminal 2
```

## API

All endpoints except `/api/health/` need the `X-API-Key` header.

| Method | Endpoint | What it does |
|---|---|---|
| `POST` | `/api/jobs/` | Upload a file (`file`, optional `mode=now\|nightly`). Returns `202` with the queued job |
| `GET` | `/api/jobs/` | List your jobs (paginated, `?status=queued\|processing\|done\|failed`) |
| `GET` | `/api/jobs/{id}/` | Job status and result |
| `POST` | `/api/jobs/{id}/retry/` | Re-queue a failed job (`409` if it isn't failed) |
| `GET` | `/api/health/` | Liveness and job counts per status |

```bash
export KEY=dq_...   # from create_api_key

curl -H "X-API-Key: $KEY" -F "file=@report.pdf" http://127.0.0.1:8000/api/jobs/
curl -H "X-API-Key: $KEY" http://127.0.0.1:8000/api/jobs/<id>/
```

Example result for a text file with broken encoding:

```json
{
  "status": "done",
  "result": {
    "encoding": "utf-8",
    "chars": 25,
    "words": 3,
    "preview": "InformaciÃ³n del cliente\n",
    "quality": { "replacement_chars": 0, "mojibake_hits": 1, "looks_broken": true }
  }
}
```

## Configuration

Set through environment variables (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `DOCQUEUE_MAX_UPLOAD_MB` | `10` | Largest accepted upload |
| `DOCQUEUE_NIGHTLY_HOUR` | `2` | Local hour when nightly jobs become eligible |
| `DOCQUEUE_MAX_ATTEMPTS` | `3` | Tries before a job is marked failed |
| `DOCQUEUE_RETRY_BASE_SECONDS` | `30` | First retry delay (doubles each attempt) |
| `DOCQUEUE_TIME_ZONE` | `America/Merida` | Time zone for the nightly window |

## Tests

```bash
uv run pytest -q        # 21 tests: auth, API scoping, processors, queue, retries
uv run ruff check .
```

CI runs lint, a missing-migrations check and the test suite on every push.

## Project layout

```
config/          settings and root URLs
jobs/
  models.py      APIKey (hashed) and Job (status, mode, attempts, result)
  auth.py        X-API-Key authentication for DRF
  processors.py  file-type detection, PDF / image / text processors, encoding checks
  worker.py      claim → process → retry/backoff
  views.py       REST endpoints
  management/commands/  create_api_key, run_worker
  tests/
```

## Trade-offs and next steps

- **Why not Celery + Redis?** For a single service with modest volume, a database queue removes a moving part and is easy to inspect from the admin. At higher throughput, swapping `worker.py` for Celery or RQ is the natural next step.
- **SQLite by default** to keep setup to one command. For concurrent workers in production, use PostgreSQL.
- **Ideas:** audio/video metadata processors, a webhook when a job finishes, per-key rate limits, Docker Compose.
