from __future__ import annotations

import json
import os
import threading
import uuid
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models import (
    Annotation,
    ModelVersion,
    PatientCase,
    Prediction,
    TrainingJob,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _datetime_or_none(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime) or value is None:
        return value
    return datetime.fromisoformat(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


class FileRepository:
    """Atomic JSON persistence rooted at a project-relative data directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.clinical_path = root / "clinical_records.json"
        self.training_path = root / "training_state.json"
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def _empty_clinical() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sequences": {"case": 0, "prediction": 0, "annotation": 0},
            "cases": [],
            "predictions": [],
            "annotations": [],
        }

    @staticmethod
    def _empty_training() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sequences": {"training_job": 0, "model_version": 0},
            "training_jobs": [],
            "model_versions": [],
        }

    def _initialize(self) -> None:
        with self._lock:
            if not self.clinical_path.exists():
                self._write(self.clinical_path, self._empty_clinical())
            if not self.training_path.exists():
                self._write(self.training_path, self._empty_training())

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(_json_value(payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    @staticmethod
    def _next_id(payload: dict[str, Any], key: str) -> int:
        value = int(payload["sequences"].get(key, 0)) + 1
        payload["sequences"][key] = value
        return value

    @staticmethod
    def _prediction(row: dict[str, Any]) -> Prediction:
        return Prediction(
            **{
                **row,
                "created_at": _datetime_or_none(row.get("created_at")),
            }
        )

    @staticmethod
    def _annotation(row: dict[str, Any]) -> Annotation:
        return Annotation(
            **{
                **row,
                "created_at": _datetime_or_none(row.get("created_at")),
                "validated_at": _datetime_or_none(row.get("validated_at")),
            }
        )

    @staticmethod
    def _case(
        row: dict[str, Any],
        predictions: list[dict[str, Any]],
        annotations: list[dict[str, Any]],
    ) -> PatientCase:
        case_id = int(row["id"])
        return PatientCase(
            **{
                **row,
                "created_at": _datetime_or_none(row.get("created_at")),
                "predictions": [
                    FileRepository._prediction(item)
                    for item in predictions
                    if int(item["case_id"]) == case_id
                ],
                "annotations": [
                    FileRepository._annotation(item)
                    for item in annotations
                    if int(item["case_id"]) == case_id
                ],
            }
        )

    def list_cases(self) -> list[PatientCase]:
        with self._lock:
            data = self._read(self.clinical_path)
            return sorted(
                [
                    self._case(row, data["predictions"], data["annotations"])
                    for row in data["cases"]
                ],
                key=lambda item: item.id,
                reverse=True,
            )

    def get_case(self, case_id: int) -> PatientCase | None:
        return next(
            (item for item in self.list_cases() if item.id == case_id),
            None,
        )

    def existing_case_codes(self, case_codes: list[str]) -> list[str]:
        expected = set(case_codes)
        return sorted(
            item.case_code
            for item in self.list_cases()
            if item.case_code in expected
        )

    def create_case_with_prediction(
        self,
        case: PatientCase,
        prediction: Prediction,
    ) -> tuple[PatientCase, Prediction]:
        created = self.create_cases_with_predictions([(case, prediction)])
        return created[0]

    def create_cases_with_predictions(
        self,
        records: list[tuple[PatientCase, Prediction]],
    ) -> list[tuple[PatientCase, Prediction]]:
        with self._lock:
            data = self._read(self.clinical_path)
            existing = {str(row["case_code"]) for row in data["cases"]}
            incoming = [case.case_code for case, _ in records]
            duplicate_incoming = {
                value for value in incoming if incoming.count(value) > 1
            }
            duplicates = sorted((set(incoming) & existing) | duplicate_incoming)
            if duplicates:
                raise ValueError("病例编号已经存在：" + "、".join(duplicates))

            updated = deepcopy(data)
            created: list[tuple[PatientCase, Prediction]] = []
            now = utc_now()
            for case, prediction in records:
                case.id = self._next_id(updated, "case")
                case.created_at = now
                prediction.id = self._next_id(updated, "prediction")
                prediction.case_id = case.id
                prediction.created_at = now
                updated["cases"].append(
                    _json_value(
                        {
                            key: value
                            for key, value in asdict(case).items()
                            if key not in {"predictions", "annotations"}
                        }
                    )
                )
                updated["predictions"].append(_json_value(asdict(prediction)))
                case.predictions = [prediction]
                created.append((case, prediction))
            self._write(self.clinical_path, updated)
            return created

    def add_annotation(self, annotation: Annotation) -> Annotation:
        with self._lock:
            data = self._read(self.clinical_path)
            if not any(int(row["id"]) == annotation.case_id for row in data["cases"]):
                raise KeyError(annotation.case_id)
            annotation.id = self._next_id(data, "annotation")
            annotation.created_at = utc_now()
            data["annotations"].append(_json_value(asdict(annotation)))
            self._write(self.clinical_path, data)
            return annotation

    def confirmed_annotation_pairs(self) -> list[tuple[Annotation, PatientCase]]:
        cases = {item.id: item for item in self.list_cases()}
        pairs: list[tuple[Annotation, PatientCase]] = []
        for case in cases.values():
            for annotation in case.annotations:
                if annotation.status == "已确认":
                    pairs.append((annotation, case))
        return sorted(pairs, key=lambda item: item[0].id)

    def pending_annotation_count(self) -> int:
        return sum(
            annotation.status == "已确认"
            and annotation.training_status == "pending"
            for case in self.list_cases()
            for annotation in case.annotations
        )

    def create_training_job(self, job: TrainingJob) -> TrainingJob:
        with self._lock:
            data = self._read(self.training_path)
            job.id = self._next_id(data, "training_job")
            job.created_at = utc_now()
            data["training_jobs"].append(_json_value(asdict(job)))
            self._write(self.training_path, data)
            return job

    def get_training_job(self, job_id: int) -> TrainingJob | None:
        with self._lock:
            data = self._read(self.training_path)
            row = next(
                (item for item in data["training_jobs"] if int(item["id"]) == job_id),
                None,
            )
            if row is None:
                return None
            return TrainingJob(
                **{
                    **row,
                    "created_at": _datetime_or_none(row.get("created_at")),
                    "started_at": _datetime_or_none(row.get("started_at")),
                    "finished_at": _datetime_or_none(row.get("finished_at")),
                }
            )

    def has_running_training_job(self) -> bool:
        with self._lock:
            data = self._read(self.training_path)
            return any(
                row.get("status") in {"queued", "running"}
                for row in data["training_jobs"]
            )

    def save_training_job(self, job: TrainingJob) -> None:
        with self._lock:
            data = self._read(self.training_path)
            for index, row in enumerate(data["training_jobs"]):
                if int(row["id"]) == job.id:
                    data["training_jobs"][index] = _json_value(asdict(job))
                    self._write(self.training_path, data)
                    return
            raise KeyError(job.id)

    def complete_training(
        self,
        job: TrainingJob,
        model_version: ModelVersion,
        annotation_ids: list[int],
    ) -> None:
        with self._lock:
            training = self._read(self.training_path)
            clinical = self._read(self.clinical_path)
            model_version.id = self._next_id(training, "model_version")
            model_version.created_at = utc_now()
            training["model_versions"].append(_json_value(asdict(model_version)))
            for index, row in enumerate(training["training_jobs"]):
                if int(row["id"]) == job.id:
                    training["training_jobs"][index] = _json_value(asdict(job))
                    break
            selected = set(annotation_ids)
            for annotation in clinical["annotations"]:
                if int(annotation["id"]) in selected:
                    annotation["training_status"] = "included"
                    annotation["trained_model_version"] = model_version.version
            self._write(self.clinical_path, clinical)
            self._write(self.training_path, training)


settings = get_settings()
file_repository = FileRepository(settings.runtime_data_path)
