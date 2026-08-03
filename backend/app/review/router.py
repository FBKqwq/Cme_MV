import re
import threading
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from .models import (
    ApproveRequest,
    ChunkEntitySave,
    EntityCreate,
    EntityUpdate,
    MutationRequest,
    RelationCreate,
    RelationUpdate,
    RestoreRequest,
)
from .config import REVIEW_DATA_ROOT
from .repository import ReviewRepository


router = APIRouter(tags=["knowledge-review"])

DEFAULT_BATCH_ID = "1"
_BATCH_ID_PATTERN = re.compile(r"^[1-9]\d*$")

repository: ReviewRepository | None = None
repository_batch: str | None = None
startup_error: str | None = None
review_data_root = REVIEW_DATA_ROOT
_repository_lock = threading.RLock()


def _batch_ids(root: Path | None = None) -> list[str]:
    base = (root or review_data_root).resolve()
    if not base.exists():
        return []
    return sorted(
        (
            child.name
            for child in base.iterdir()
            if child.is_dir()
            and _BATCH_ID_PATTERN.fullmatch(child.name)
            and (child / "current").is_dir()
        ),
        key=int,
    )


def _batch_root(batch_id: str) -> Path:
    return review_data_root / batch_id


def _build_repository(batch_id: str) -> ReviewRepository:
    root = _batch_root(batch_id)
    return ReviewRepository(
        project_root=review_data_root.parents[1],
        inbox_root=root / "current",
        result_root=root / "state" / "results",
        export_root=root / "state" / "exports",
        schema_path=(
            root
            / "current"
            / "graph_property_schema_v3_6.json"
        ),
    )


def load_repository(
    data_root: Path | None = None,
    batch_id: str = DEFAULT_BATCH_ID,
) -> None:
    global repository, repository_batch, startup_error, review_data_root
    review_data_root = (data_root or REVIEW_DATA_ROOT).resolve()
    try:
<<<<<<< HEAD
        repository = ReviewRepository(
            project_root=root.parents[1],
            inbox_root=root / "current",
            result_root=root / "state" / "results",
            export_root=root / "state" / "exports",
            schema_path=(
                root 
                / "current"
                / "graph_property_schema_v3_6.json"
            ),
        )
=======
        if batch_id not in _batch_ids():
            raise ValueError(f"未找到复验批次目录：{review_data_root / batch_id}")
        repository = _build_repository(batch_id)
        repository_batch = batch_id
>>>>>>> upstream/main
        startup_error = None
    except Exception as exc:  # surfaced as an actionable API state
        repository = None
        repository_batch = batch_id
        startup_error = str(exc)


def repo(batch_id: str = DEFAULT_BATCH_ID) -> ReviewRepository:
    global repository, repository_batch, startup_error
    if not _BATCH_ID_PATTERN.fullmatch(batch_id) or batch_id not in _batch_ids():
        raise HTTPException(
            status_code=404,
            detail={
                "code": "BATCH_NOT_FOUND",
                "message": f"复验批次 {batch_id} 不存在。",
            },
        )

    if repository is not None and repository_batch == batch_id:
        return repository

    with _repository_lock:
        if repository is not None and repository_batch == batch_id:
            return repository
        try:
            selected = _build_repository(batch_id)
        except Exception as exc:
            repository = None
            repository_batch = batch_id
            startup_error = str(exc)
        else:
            repository = selected
            repository_batch = batch_id
            startup_error = None

    if repository is None or repository_batch != batch_id:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "TASK_UNAVAILABLE",
                "message": startup_error or "复验任务尚未准备好。",
            },
        )
    return repository


def request_repository(
    batch: str = Query(
        default=DEFAULT_BATCH_ID,
        pattern=r"^[1-9]\d*$",
        description="复验批次编号",
    ),
) -> ReviewRepository:
    return repo(batch)


CurrentRepository = Annotated[ReviewRepository, Depends(request_repository)]


@router.get("/api/review/batches")
def get_batches() -> dict[str, object]:
    items = []
    for batch_id in _batch_ids():
        root = _batch_root(batch_id)
        missing = [
            name
            for name, path in (
                ("chunks", root / "current" / "chunks"),
                ("schema", root / "current" / "graph_property_schema_v3_6.json"),
            )
            if not path.exists()
        ]
        items.append(
            {
                "id": batch_id,
                "label": f"第{batch_id}批复验",
                "status": "ready" if not missing else "degraded",
                "error": (
                    ""
                    if not missing
                    else f"缺少批次数据：{', '.join(missing)}"
                ),
            }
        )
    return {
        "items": items,
        "default_batch": (
            DEFAULT_BATCH_ID
            if DEFAULT_BATCH_ID in _batch_ids()
            else (items[0]["id"] if items else "")
        ),
    }


@router.get("/api/review/health")
def health(
    batch: str = Query(
        default=DEFAULT_BATCH_ID,
        pattern=r"^[1-9]\d*$",
    ),
) -> dict[str, str]:
    try:
        repo(batch)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {
            "status": "degraded",
            "error": str(detail.get("message") or exc.detail),
            "batch": batch,
        }
    return {"status": "ok", "error": "", "batch": batch}


@router.get("/api/review/task")
def get_task(current: CurrentRepository):
    return current.task()


@router.get("/api/review/chunks")
def get_chunks(
    current: CurrentRepository,
    pending_only: bool = Query(default=False),
):
    return {"items": current.chunk_summaries(pending_only=pending_only)}


@router.get("/api/review/chunks/{chunk_id}")
def get_chunk(chunk_id: str, current: CurrentRepository):
    return current.chunk_detail(chunk_id)


@router.put("/api/review/chunks/{chunk_id}/entities")
def save_chunk_entities(
    chunk_id: str,
    body: ChunkEntitySave,
    current: CurrentRepository,
):
    return current.save_chunk_entities(chunk_id, body.model_dump())


@router.post("/api/review/entities", status_code=201)
def create_entity(body: EntityCreate, current: CurrentRepository):
    return current.create_entity(body.model_dump())


@router.patch("/api/review/entities/{entity_id}")
def update_entity(
    entity_id: str,
    body: EntityUpdate,
    current: CurrentRepository,
):
    return current.update_entity(entity_id, body.model_dump(exclude_none=True))


@router.delete("/api/review/entities/{entity_id}")
def delete_entity(
    entity_id: str,
    current: CurrentRepository,
    base_version: int = Body(embed=True),
    chunk_id: str = Body(embed=True),
):
    return current.delete_entity(
        entity_id, chunk_id=chunk_id, base_version=base_version
    )


@router.post("/api/review/entities/{entity_id}/restore")
def restore_entity(
    entity_id: str,
    body: RestoreRequest,
    current: CurrentRepository,
):
    return current.restore_entity(
        entity_id, chunk_id=body.chunk_id, base_version=body.base_version
    )


@router.post("/api/review/relationships", status_code=201)
def create_relationship(body: RelationCreate, current: CurrentRepository):
    return current.create_relationship(body.model_dump())


@router.patch("/api/review/relationships/{relation_id}")
def update_relationship(
    relation_id: str,
    body: RelationUpdate,
    current: CurrentRepository,
):
    return current.update_relationship(
        relation_id, body.model_dump(exclude_none=True)
    )


@router.delete("/api/review/relationships/{relation_id}")
def delete_relationship(
    relation_id: str,
    current: CurrentRepository,
    base_version: int = Body(embed=True),
    chunk_id: str = Body(embed=True),
):
    return current.delete_relationship(
        relation_id, chunk_id=chunk_id, base_version=base_version
    )


@router.post("/api/review/relationships/{relation_id}/restore")
def restore_relationship(
    relation_id: str,
    body: RestoreRequest,
    current: CurrentRepository,
):
    return current.restore_relationship(
        relation_id, chunk_id=body.chunk_id, base_version=body.base_version
    )


@router.post("/api/review/chunks/{chunk_id}/approve")
def approve_chunk(
    chunk_id: str,
    body: ApproveRequest,
    current: CurrentRepository,
):
    return current.approve_chunk(chunk_id, body.base_version)


@router.post("/api/review/finalize")
def finalize(body: MutationRequest, current: CurrentRepository):
    current._assert_version(body.base_version, chunk_id=body.chunk_id)
    path = current.build_export(final=True)
    return {"filename": path.name, "version": current.version()}


@router.get("/api/review/pdf/{document_id}")
def get_pdf(document_id: str, current: CurrentRepository):
    path = current.source_pdf(document_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.post("/api/review/import")
async def import_review(
    current: CurrentRepository,
    file: bytes = Body(..., media_type="application/octet-stream"),
):
    """Import a previously exported review session ZIP to continue reviewing."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(file)
    try:
        result = current.import_review(tmp)
        return {"message": "复验状态已成功导入", **result}
    finally:
        if tmp.exists():
            tmp.unlink()

@router.get("/api/review/export")
def export_review(
    current: CurrentRepository,
    final: bool = Query(default=False),
):
    path: Path = current.build_export(final=final)
    return FileResponse(path, media_type="application/zip", filename=path.name)
