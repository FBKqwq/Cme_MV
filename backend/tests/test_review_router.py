from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.review import router as review_module


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(review_module.router)
    return TestClient(app)


def test_review_health_is_degraded_without_data(monkeypatch) -> None:
    monkeypatch.setattr(review_module, "repository", None)
    monkeypatch.setattr(
        review_module,
        "startup_error",
        "未找到chunks目录：data/review/current/chunks",
    )

    with make_client() as client:
        health = client.get("/api/review/health")
        task = client.get("/api/review/task")

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert task.status_code == 503
    assert task.json()["detail"]["code"] == "TASK_UNAVAILABLE"


def test_review_health_is_ok_with_repository(monkeypatch, tmp_path) -> None:
    from tests.test_review_repository import make_task

    repository = make_task(tmp_path, with_pdf=True)
    monkeypatch.setattr(review_module, "repository", repository)
    monkeypatch.setattr(review_module, "startup_error", None)

    with make_client() as client:
        health = client.get("/api/review/health")
        task = client.get("/api/review/task")
        pdf = client.get("/api/review/pdf/TEST")

    assert health.json() == {"status": "ok", "error": ""}
    assert task.json()["documents"][0]["document_id"] == "TEST"
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline;")
