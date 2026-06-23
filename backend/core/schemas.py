"""
Pydantic schemas for API request/response bodies.

Keeping these separate from route handlers keeps the API contract
explicit and lets FastAPI auto-generate accurate OpenAPI docs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UploadedFileInfo(BaseModel):
    filename: str
    size_bytes: int
    language: str


class UploadResponse(BaseModel):
    session_id: str
    files: list[UploadedFileInfo]
    message: str = "Files uploaded and validated successfully."


class TestResultRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="File Name")
    test_case_no: str = Field(alias="Test Case No")
    result: str = Field(alias="Result")
    stage: str | None = None
    error_message: str | None = None


class ExecuteResponse(BaseModel):
    session_id: str
    total: int
    passed: int
    failed: int
    results: list[TestResultRow]
    report_ready: bool = True


class HealthResponse(BaseModel):
    status: str
    docker_sandbox_available: bool
    version: str
