import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

DATABASE_ENV = ("DB_USER", "DB_PASSWORD", "DB_NAME")
env_file = Path(__file__).resolve().parents[1] / ".env"
database_settings = {
    **dotenv_values(env_file),
    **os.environ,
}
database_configured = all(
    database_settings.get(name)
    for name in DATABASE_ENV
)

if database_configured:
    from app.main import app
else:
    app = None

pytestmark = pytest.mark.skipif(
    not database_configured,
    reason="诊断 API 集成测试需要配置 PostgreSQL 环境变量",
)


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200


def test_database_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/db-health")

    assert response.status_code == 200


def test_model_info_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/model/info")

    assert response.status_code == 200

    data = response.json()

    assert data["loaded"] is True
    assert data["feature_count"] == 27
    assert len(data["feature_columns"]) == 27
    assert len(data["feature_schema"]) == 27

    assert set(data["class_labels"]) == {
        "其他",
        "炎症",
        "感染",
        "肿瘤",
    }
import uuid


def test_real_prediction_endpoint() -> None:
    case_code = f"TEST-{uuid.uuid4().hex[:10]}"

    payload = {
        "case_code": case_code,
        "age": 45,
        "gender": "男",
        "fever_duration": 3,
        "max_temperature": 38.6,
        "features": {},
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/cases/predict",
            json=payload,
        )

    assert response.status_code == 201

    data = response.json()

    assert data["case"]["case_code"] == case_code

    prediction = data["prediction"]

    assert prediction["predicted_label"] in {
        "其他",
        "炎症",
        "感染",
        "肿瘤",
    }

    probabilities = prediction["probabilities"]

    assert set(probabilities.keys()) == {
        "其他",
        "炎症",
        "感染",
        "肿瘤",
    }

    probability_sum = sum(
        float(value)
        for value in probabilities.values()
    )

    assert abs(probability_sum - 1.0) < 0.01
    assert prediction["model_version"] != "mock-v0.1.0"
