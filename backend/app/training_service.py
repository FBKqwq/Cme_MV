from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Annotation, TrainingJob


settings = get_settings()


def get_pending_annotation_count(db: Session) -> int:
    count = db.scalar(
        select(func.count(Annotation.id)).where(
            Annotation.status == "已确认",
            Annotation.training_status == "pending",
        )
    )
    return int(count or 0)


def has_running_training_job(db: Session) -> bool:
    job = db.scalar(
        select(TrainingJob).where(
            TrainingJob.status.in_(["queued", "running"])
        )
    )
    return job is not None


def create_training_job_if_needed(db: Session) -> TrainingJob | None:
    if not settings.auto_training_enabled:
        return None

    if has_running_training_job(db):
        return None

    pending_count = get_pending_annotation_count(db)
    if pending_count < settings.auto_training_annotation_threshold:
        return None

    job = TrainingJob(
        status="queued",
        trigger_type="annotation_threshold",
        annotation_count=pending_count,
        message="已达到自动训练触发阈值，等待后台执行",
    )

    db.add(job)
    db.commit()
    db.refresh(job)
    return job
