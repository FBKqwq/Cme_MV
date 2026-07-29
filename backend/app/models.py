from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Prediction:
    case_id: int
    predicted_label: str
    probabilities: dict[str, float]
    model_version: str
    id: int = 0
    created_at: datetime | None = None


@dataclass
class Annotation:
    case_id: int
    true_label: str
    doctor_name: str
    status: str = "已确认"
    remark: str | None = None
    training_status: str = "pending"
    trained_model_version: str | None = None
    validated_by: str | None = None
    validated_at: datetime | None = None
    id: int = 0
    created_at: datetime | None = None


@dataclass
class PatientCase:
    case_code: str
    age: int
    gender: str
    fever_duration: float
    max_temperature: float
    features: dict[str, Any] = field(default_factory=dict)
    id: int = 0
    created_at: datetime | None = None
    predictions: list[Prediction] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)


@dataclass
class ModelVersion:
    version: str
    model_name: str
    file_path: str
    status: str
    sample_count: int
    macro_f1: float | None = None
    balanced_accuracy: float | None = None
    log_loss: float | None = None
    parent_version: str | None = None
    failure_reason: str | None = None
    id: int = 0
    created_at: datetime | None = None
    deployed_at: datetime | None = None


@dataclass
class TrainingJob:
    status: str = "queued"
    trigger_type: str = "annotation_threshold"
    annotation_count: int = 0
    candidate_version: str | None = None
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    id: int = 0
    created_at: datetime | None = None
