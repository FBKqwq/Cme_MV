import json

import pytest

from app.file_repository import FileRepository
from app.models import Annotation, PatientCase, Prediction, TrainingJob


def make_case(code: str) -> PatientCase:
    return PatientCase(
        case_code=code,
        age=30,
        gender="男",
        fever_duration=2,
        max_temperature=38.5,
        features={"年龄": 30},
    )


def make_prediction() -> Prediction:
    return Prediction(
        case_id=0,
        predicted_label="感染",
        probabilities={"感染": 1.0},
        model_version="test-v1",
    )


def test_clinical_records_survive_repository_reload(tmp_path) -> None:
    repository = FileRepository(tmp_path / "data" / "runtime")
    case, prediction = repository.create_case_with_prediction(
        make_case("CASE-001"),
        make_prediction(),
    )
    annotation = repository.add_annotation(
        Annotation(
            case_id=case.id,
            true_label="感染",
            doctor_name="测试医生",
        )
    )

    reloaded = FileRepository(repository.root)
    restored = reloaded.get_case(case.id)

    assert restored is not None
    assert restored.case_code == "CASE-001"
    assert restored.predictions[0].id == prediction.id
    assert restored.annotations[0].id == annotation.id


def test_batch_write_is_atomic_when_case_code_conflicts(tmp_path) -> None:
    repository = FileRepository(tmp_path / "data" / "runtime")
    repository.create_case_with_prediction(make_case("EXISTS"), make_prediction())
    before = repository.clinical_path.read_bytes()

    with pytest.raises(ValueError, match="病例编号已经存在"):
        repository.create_cases_with_predictions(
            [
                (make_case("NEW"), make_prediction()),
                (make_case("EXISTS"), make_prediction()),
            ]
        )

    assert repository.clinical_path.read_bytes() == before
    assert repository.get_case(2) is None


def test_training_state_is_json_and_uses_monotonic_ids(tmp_path) -> None:
    repository = FileRepository(tmp_path / "data" / "runtime")
    first = repository.create_training_job(TrainingJob(annotation_count=1))
    second = repository.create_training_job(TrainingJob(annotation_count=2))
    payload = json.loads(repository.training_path.read_text(encoding="utf-8"))

    assert (first.id, second.id) == (1, 2)
    assert payload["training_jobs"][1]["annotation_count"] == 2
    assert not list(repository.root.rglob("*.db"))
    assert not list(repository.root.rglob("*.sqlite*"))
