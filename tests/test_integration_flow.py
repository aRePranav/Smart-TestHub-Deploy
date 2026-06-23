"""
Integration tests for the FastAPI app, covering the full
upload -> execute -> download-report flow plus validation/security
rejections.

These tests rely on the LOCAL FALLBACK execution path (no Docker
required) since CI/sandboxed test environments frequently lack a
Docker daemon. The fallback uses the same pytest/gcc/javac toolchain
present in the dev environment. In an environment with Docker
available, these same endpoints exercise the real sandbox path
transparently (the executor decides at call time).
"""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "docker_sandbox_available" in body


def test_upload_rejects_disallowed_extension() -> None:
    files = [("files", ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream"))]
    response = client.post("/api/upload", files=files)
    assert response.status_code == 400
    assert "disallowed extension" in response.json()["detail"]


def test_upload_rejects_dangerous_python_pattern() -> None:
    source = b"import os\nos.system('echo hi')\n"
    files = [("files", ("bad_test.py", io.BytesIO(source), "text/x-python"))]
    response = client.post("/api/upload", files=files)
    assert response.status_code == 400
    assert "disallowed pattern" in response.json()["detail"]


def test_full_flow_passing_python_test() -> None:
    source = b"def test_addition():\n    assert 1 + 1 == 2\n"
    files = [("files", ("test_math.py", io.BytesIO(source), "text/x-python"))]

    upload_response = client.post("/api/upload", files=files)
    assert upload_response.status_code == 200
    session_id = upload_response.json()["session_id"]

    execute_response = client.post(f"/api/execute/{session_id}")
    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["total"] == 1
    assert body["passed"] == 1
    assert body["results"][0]["Result"] == "PASS"
    assert body["results"][0]["Test Case No"] == "TC001"

    download_response = client.get(f"/api/download-report/{session_id}")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith(
        "application/vnd.openxmlformats"
    )


def test_full_flow_failing_python_test() -> None:
    source = b"def test_will_fail():\n    assert 1 == 2\n"
    files = [("files", ("test_fail.py", io.BytesIO(source), "text/x-python"))]

    upload_response = client.post("/api/upload", files=files)
    session_id = upload_response.json()["session_id"]

    execute_response = client.post(f"/api/execute/{session_id}")
    body = execute_response.json()
    assert body["passed"] == 0
    assert body["failed"] == 1
    assert body["results"][0]["Result"] == "FAIL"


def test_zip_upload_with_zip_slip_is_rejected() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("../../evil.py", b"print('pwned')")
    buffer.seek(0)

    files = [("files", ("payload.zip", buffer, "application/zip"))]
    response = client.post("/api/upload", files=files)
    assert response.status_code == 400


def test_execute_unknown_session_returns_404() -> None:
    response = client.post("/api/execute/does-not-exist")
    assert response.status_code == 404


def test_download_report_before_execute_returns_404() -> None:
    source = b"def test_ok():\n    assert True\n"
    files = [("files", ("test_pending.py", io.BytesIO(source), "text/x-python"))]
    upload_response = client.post("/api/upload", files=files)
    session_id = upload_response.json()["session_id"]

    response = client.get(f"/api/download-report/{session_id}")
    assert response.status_code == 404
