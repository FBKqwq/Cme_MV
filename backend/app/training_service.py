from app.config import get_settings
from app.file_repository import FileRepository, file_repository
from app.models import TrainingJob


settings = get_settings()


def get_pending_annotation_count(
    repository: FileRepository = file_repository,
) -> int:
    return repository.pending_annotation_count()


def has_running_training_job(
    repository: FileRepository = file_repository,
) -> bool:
    return repository.has_running_training_job()


def create_training_job_if_needed(
    repository: FileRepository = file_repository,
) -> TrainingJob | None:
    if not settings.auto_training_enabled:
        return None
    if has_running_training_job(repository):
        return None

    pending_count = get_pending_annotation_count(repository)
    if pending_count < settings.auto_training_annotation_threshold:
        return None

    return repository.create_training_job(
        TrainingJob(
            status="queued",
            trigger_type="annotation_threshold",
            annotation_count=pending_count,
            message="已达到自动训练触发阈值，等待后台执行",
        )
    )
