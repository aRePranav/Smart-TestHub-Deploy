# Automated Test Execution Platform

A production-grade platform that automates execution of uploaded software
test case files (Python, C, Java), determines PASS/FAIL per file, and
generates a structured, downloadable Excel report — turning a process
that normally takes QA teams hours into one that takes minutes.

---

## ⚠️ Read this before deploying

The original spec for this platform asked for a Python-keyword
blocklist (rejecting `os.system`, `eval`, `subprocess`, etc.) as a
**security control**. That alone is not a security boundary — it's
trivially bypassed (`__import__('os').system(...)`, encoded payloads,
string concatenation) — and the platform's whole job is executing
**arbitrary, untrusted, user-uploaded code**.

So this build keeps that scan, but reframes it honestly:

- **Pre-filter (`backend/core/security.py`)** — a cheap heuristic that
  rejects obviously hostile Python uploads early, with a clear error.
  Convenience only. Not relied upon for isolation.
- **Real security boundary (`backend/executors/base_executor.py`)** —
  every execution runs inside a **fresh, locked-down Docker
  container**: `--network none`, `--read-only` root filesystem,
  `--cap-drop ALL`, `--security-opt no-new-privileges`, hard
  memory/CPU/PID limits, non-root user, auto-removed (`--rm`) after
  each run.

**If Docker is not available on the host, the platform automatically
falls back to a local subprocess execution path.** This fallback is
clearly logged and surfaced via `GET /api/health`
(`docker_sandbox_available: false`) — it does **not** provide real
isolation and should not be used in production with genuinely
untrusted users. Always run this platform with Docker available (see
deployment instructions below) for real-world use.

---

## What it does

1. Accepts single files, multiple files, or a `.zip` archive (`.py`, `.c`, `.java`).
2. Auto-detects the language of each file.
3. Routes each file to the matching sandboxed executor.
4. Executes the file and determines PASS / FAIL.
5. Generates a structured `.xlsx` report: `File Name | Test Case No | Result`.
6. Serves the report for download.

| Language | Pipeline |
|---|---|
| Python | `pytest <file>` — exit 0 = PASS |
| C | `gcc file.c -o file.out` then `./file.out` — both stages exit 0 = PASS |
| Java | `javac File.java` then `java File` — both stages exit 0 = PASS |

---

## Architecture

```
project/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, exception handling, static frontend mount
│   ├── routes/
│   │   ├── upload.py             # POST /api/upload
│   │   ├── execute.py             # POST /api/execute/{session_id}
│   │   ├── report.py              # GET /api/download-report/{session_id}
│   │   └── health.py              # GET /api/health
│   ├── core/
│   │   ├── config.py               # All tunables: limits, timeouts, paths
│   │   ├── exceptions.py            # Typed exception hierarchy
│   │   ├── file_validator.py        # Extension + size validation
│   │   ├── security.py               # Pre-filter heuristic scan (see warning above)
│   │   ├── detector.py                # Extension -> Language mapping
│   │   ├── excel_generator.py          # pandas + openpyxl report builder
│   │   ├── session_manager.py           # In-memory session store
│   │   └── schemas.py                    # Pydantic request/response models
│   ├── executors/
│   │   ├── base_executor.py         # THE security boundary: Docker sandbox + local fallback
│   │   ├── python_executor.py        # pytest pipeline
│   │   ├── c_executor.py              # gcc compile + run pipeline
│   │   └── java_executor.py            # javac compile + run pipeline
│   ├── utils/
│   │   ├── zip_handler.py            # Zip-slip / zip-bomb safe extraction
│   │   └── cleanup.py                 # Guaranteed temp-dir deletion
│   ├── uploads/reports/               # Generated .xlsx reports (gitignored)
│   └── temp/                           # Per-session scratch dirs (gitignored)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/                              # pytest unit + integration tests
├── requirements.txt
├── Dockerfile                          # App server image
├── sandbox.Dockerfile                  # Untrusted-code execution image
├── docker-compose.yml
└── README.md
```

Adding a new language (e.g. C++) means: one new `core/detector.py`
mapping entry, one new `executors/cpp_executor.py` class, one new
entry in `executors/__init__.py`'s factory map. No other file changes.

---

## Security model in detail

| Layer | What it does |
|---|---|
| File type allow-list | Only `.py`, `.c`, `.java`, `.zip` accepted; everything else rejected (400) |
| Size limit | 100 MB per file (raised from the original 50 MB spec per request) |
| Zip-slip protection | Every ZIP member's resolved path is checked against the extraction root before writing; traversal attempts are rejected |
| Zip-bomb protection | Uncompressed size and entry-count ceilings checked before extraction |
| Pre-filter scan | Heuristic rejection of `os.system`, `subprocess`, `socket`, `eval`, `exec`, etc. in `.py` uploads — convenience, not the security boundary |
| **Docker sandbox** | **The real boundary**: no network, read-only rootfs, dropped capabilities, non-root, memory/CPU/PID limits, ephemeral container per run |
| Execution timeout | 5s run / 15s compile, enforced both by the container lifecycle and the host-side `subprocess` timeout |
| No persistent storage | Session work directories are deleted immediately after report generation |

---

## Running locally (with Docker — recommended)

```bash
# 1. Build the sandbox image used for executing untrusted code
docker build -f sandbox.Dockerfile -t test-platform-sandbox:latest .

# 2. Build and start the app stack
docker compose up --build
```

Visit **http://localhost:8000**. `GET /api/health` will report
`"docker_sandbox_available": true"` once both images are built and the
app container can reach the Docker socket.

## Running locally (without Docker — degraded isolation, dev only)

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

You'll see a warning in logs and `docker_sandbox_available: false` in
`/api/health` — this mode is fine for local development, not for
serving untrusted users.

## Running tests

```bash
pip install -r requirements.txt pytest httpx
python3 -m pytest tests/ -v
```

24 tests covering: language detection, zip-slip/zip-bomb rejection,
pre-filter scanning, Excel report structure (column names + sequential
TC numbering), and full upload → execute → download integration flows
(including failure and rejection paths).

---

## API reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/upload` | Upload one or more files (multipart `files` field); returns `session_id` |
| `POST` | `/api/execute/{session_id}` | Execute all staged files in the session; returns PASS/FAIL summary + generates report |
| `GET` | `/api/download-report/{session_id}` | Download the generated `.xlsx` report |
| `GET` | `/api/health` | Liveness check + sandbox availability flag |

Full interactive docs (OpenAPI/Swagger) are available at `/docs` once
the server is running.

---

## Known limitations / honest notes for whoever maintains this next

- **Session store is in-memory.** Restarting the app loses in-flight
  sessions. For multi-instance production deployment, swap
  `backend/core/session_manager.py`'s dict for Redis — the function
  signatures (`create_session`, `get_session`, `delete_session`) are
  designed so call sites wouldn't need to change.
- **Java's "main class" detection is filename-based** (Java requires
  the public class name to match the filename), which is correct for
  the vast majority of real test files but won't handle a file with
  no public class or a mismatched name — that fails cleanly as FAIL
  with a clear stage/error message rather than crashing.
- **Pre-filter is a heuristic, not a guarantee** — see the security
  section above. Don't let anyone convince you it's "the" security
  layer; the Docker sandbox is.
- **Docker-out-of-Docker via the mounted socket** means the app
  container can start sibling containers on the host. This is
  intentional (it's what lets execution containers be properly
  sandboxed rather than nested inside the app's own container) but it
  does mean the app container itself must be a trusted component of
  your deployment.
