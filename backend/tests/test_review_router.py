from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.review import router as review_module


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(review_module.router)
    return TestClient(app)


def test_review_health_is_degraded_without_data(monkeypatch) -> None:
    review_root = Path(".pytest-review-missing").resolve()
    monkeypatch.setattr(review_module, "review_data_root", review_root)
    monkeypatch.setattr(review_module, "repository", None)
    monkeypatch.setattr(review_module, "repository_batch", "1")
    monkeypatch.setattr(
        review_module,
        "startup_error",
        "未找到复验批次目录",
    )

    with make_client() as client:
        health = client.get("/api/review/health")
        task = client.get("/api/review/task")

    assert health.status_code == 200
    assert health.json() == {
        "status": "degraded",
        "error": "复验批次 1 不存在。",
        "batch": "1",
    }
    assert task.status_code == 404
    assert task.json()["detail"]["code"] == "BATCH_NOT_FOUND"


def test_review_health_is_ok_with_repository(monkeypatch, tmp_path) -> None:
    from tests.test_review_repository import make_task

    repository = make_task(tmp_path, with_pdf=True)
    review_root = tmp_path / "review-batches"
    (review_root / "1" / "current").mkdir(parents=True)
    monkeypatch.setattr(review_module, "review_data_root", review_root)
    monkeypatch.setattr(review_module, "repository", repository)
    monkeypatch.setattr(review_module, "repository_batch", "1")
    monkeypatch.setattr(review_module, "startup_error", None)

    with make_client() as client:
        health = client.get("/api/review/health")
        task = client.get("/api/review/task")
        pdf = client.get("/api/review/pdf/TEST")

    assert health.json() == {"status": "ok", "error": "", "batch": "1"}
    assert task.json()["documents"][0]["document_id"] == "TEST"
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline;")


def test_load_repository_uses_numbered_batch_directory(
    monkeypatch,
    tmp_path,
) -> None:
    from tests.test_review_repository import make_task

    make_task(tmp_path)
    review_root = tmp_path / "data" / "review"
    batch_root = review_root / "1"
    batch_root.mkdir()
    (review_root / "current").rename(batch_root / "current")
    (review_root / "state").rename(batch_root / "state")
    monkeypatch.setattr(
        review_module,
        "review_data_root",
        review_module.REVIEW_DATA_ROOT,
    )
    monkeypatch.setattr(review_module, "repository", None)
    monkeypatch.setattr(review_module, "repository_batch", None)
    monkeypatch.setattr(review_module, "startup_error", None)

    review_module.load_repository(review_root)

    assert review_module.startup_error is None
    assert review_module.repository is not None
    assert review_module.repository_batch == "1"
    assert review_module.repository.inbox_root == batch_root / "current"
    assert review_module.repository.result_root == batch_root / "state" / "results"
    assert review_module.repository.schema_path == (
        batch_root / "current" / "graph_property_schema_v3_6.json"
    )


def test_batch_query_switches_repository(monkeypatch, tmp_path) -> None:
    from tests.test_review_repository import make_task

    first = make_task(tmp_path / "first")
    second = make_task(tmp_path / "second")
    monkeypatch.setattr(review_module, "_batch_ids", lambda root=None: ["1", "2"])
    monkeypatch.setattr(
        review_module,
        "_build_repository",
        lambda batch_id: first if batch_id == "1" else second,
    )
    monkeypatch.setattr(review_module, "repository", first)
    monkeypatch.setattr(review_module, "repository_batch", "1")
    monkeypatch.setattr(review_module, "startup_error", None)

    with make_client() as client:
        response = client.get("/api/review/task?batch=2")
        saved = client.put(
            "/api/review/chunks/TEST_CH01/entities?batch=2",
            json={
                "base_version": 0,
                "entities": [
                    {
                        "entity_id": "E01",
                        "name": "白塞综合征",
                        "entity_type": "sub_diseases",
                        "evidence_text": "白塞综合征",
                    },
                    {
                        "entity_id": "E02",
                        "name": "第2批口腔溃疡",
                        "entity_type": "symptoms",
                        "evidence_text": "反复口腔溃疡",
                    },
                ],
            },
        )

    assert response.status_code == 200
    assert saved.status_code == 200
    assert review_module.repository is second
    assert review_module.repository_batch == "2"
    assert first.version() == 0
    assert second.version() == 1
    assert not list(first.delta_root.rglob("*.review.json"))
    assert list(second.delta_root.rglob("*.review.json"))
