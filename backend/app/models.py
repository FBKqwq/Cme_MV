from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PatientCase(Base):
    """患者病例。"""

    __tablename__ = "patient_cases"

    id: Mapped[int] = mapped_column(primary_key=True)

    case_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    age: Mapped[int] = mapped_column(nullable=False)

    gender: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )

    fever_duration: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    max_temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # 后续增加的完整模型字段可以放在这里。
    features: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )

    annotations: Mapped[list[Annotation]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )


class Prediction(Base):
    """模型预测记录。"""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)

    case_id: Mapped[int] = mapped_column(
        ForeignKey(
            "patient_cases.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    predicted_label: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    probabilities: Mapped[dict[str, float]] = mapped_column(
        JSONB,
        nullable=False,
    )

    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    case: Mapped[PatientCase] = relationship(
        back_populates="predictions",
    )


class Annotation(Base):
    """医生真实诊断标注。"""

    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(primary_key=True)

    case_id: Mapped[int] = mapped_column(
        ForeignKey(
            "patient_cases.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    true_label: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    doctor_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="已确认",
        nullable=False,
    )

    remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    case: Mapped[PatientCase] = relationship(
        back_populates="annotations",
    )
    training_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    trained_model_version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    validated_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
class ModelVersion(Base):
    """模型版本记录。"""

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    version: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="candidate",
        nullable=False,
    )

    sample_count: Mapped[int] = mapped_column(
        nullable=False,
    )

    macro_f1: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    balanced_accuracy: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    log_loss: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    parent_version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class TrainingJob(Base):
    """自动训练任务。"""

    __tablename__ = "training_jobs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="queued",
        nullable=False,
    )

    trigger_type: Mapped[str] = mapped_column(
        String(30),
        default="annotation_threshold",
        nullable=False,
    )

    annotation_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    candidate_version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )