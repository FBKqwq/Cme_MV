from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query
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

repository: ReviewRepository | None = None
startup_error: str | None = None


def load_repository(data_root: Path | None = None) -> None:
    global repository, startup_error
    root = (data_root or REVIEW_DATA_ROOT).resolve()
    try:
        repository = ReviewRepository(
            project_root=root.parents[1],
            inbox_root=root / "current",
            result_root=root / "state" / "results",
            export_root=root / "state" / "exports",
            schema_path=(
                root / "current"
                / "graph_property_schema_v3_6.json"
            ),
        )
        startup_error = None
    except Exception as exc:  # surfaced as an actionable API state
        repository = None
        startup_error = str(exc)


def repo() -> ReviewRepository:
    if repository is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "TASK_UNAVAILABLE",
                "message": startup_error or "复验任务尚未准备好。",
            },
        )
    return repository


@router.get("/api/review/health")
def health() -> dict[str, str]:
    return {"status": "ok" if repository else "degraded", "error": startup_error or ""}


@router.get("/api/review/task")
def get_task():
    return repo().task()


@router.get("/api/review/chunks")
def get_chunks(pending_only: bool = Query(default=False)):
    return {"items": repo().chunk_summaries(pending_only=pending_only)}


@router.get("/api/review/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    return repo().chunk_detail(chunk_id)


@router.put("/api/review/chunks/{chunk_id}/entities")
def save_chunk_entities(chunk_id: str, body: ChunkEntitySave):
    return repo().save_chunk_entities(chunk_id, body.model_dump())


@router.post("/api/review/entities", status_code=201)
def create_entity(body: EntityCreate):
    return repo().create_entity(body.model_dump())


@router.patch("/api/review/entities/{entity_id}")
def update_entity(entity_id: str, body: EntityUpdate):
    return repo().update_entity(entity_id, body.model_dump(exclude_none=True))


@router.delete("/api/review/entities/{entity_id}")
def delete_entity(
    entity_id: str,
    base_version: int = Body(embed=True),
    chunk_id: str = Body(embed=True),
):
    return repo().delete_entity(
        entity_id, chunk_id=chunk_id, base_version=base_version
    )


@router.post("/api/review/entities/{entity_id}/restore")
def restore_entity(entity_id: str, body: RestoreRequest):
    return repo().restore_entity(
        entity_id, chunk_id=body.chunk_id, base_version=body.base_version
    )


@router.post("/api/review/relationships", status_code=201)
def create_relationship(body: RelationCreate):
    return repo().create_relationship(body.model_dump())


@router.patch("/api/review/relationships/{relation_id}")
def update_relationship(relation_id: str, body: RelationUpdate):
    return repo().update_relationship(
        relation_id, body.model_dump(exclude_none=True)
    )


@router.delete("/api/review/relationships/{relation_id}")
def delete_relationship(
    relation_id: str,
    base_version: int = Body(embed=True),
    chunk_id: str = Body(embed=True),
):
    return repo().delete_relationship(
        relation_id, chunk_id=chunk_id, base_version=base_version
    )


@router.post("/api/review/relationships/{relation_id}/restore")
def restore_relationship(relation_id: str, body: RestoreRequest):
    return repo().restore_relationship(
        relation_id, chunk_id=body.chunk_id, base_version=body.base_version
    )


@router.post("/api/review/chunks/{chunk_id}/approve")
def approve_chunk(chunk_id: str, body: ApproveRequest):
    return repo().approve_chunk(chunk_id, body.base_version)


@router.post("/api/review/finalize")
def finalize(body: MutationRequest):
    current = repo()
    current._assert_version(body.base_version)
    path = current.build_export(final=True)
    return {"filename": path.name, "version": current.version()}


@router.get("/api/review/pdf/{document_id}")
def get_pdf(document_id: str):
    path = repo().source_pdf(document_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.post("/api/review/import")
async def import_review(file: bytes = Body(..., media_type="application/octet-stream")):
    """Import a previously exported review session ZIP to continue reviewing."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(file)
    try:
        result = repo().import_review(tmp)
        return {"message": "复验状态已成功导入", **result}
    finally:
        if tmp.exists():
            tmp.unlink()

@router.get("/api/review/export")
def export_review(final: bool = Query(default=False)):
    path: Path = repo().build_export(final=final)
    return FileResponse(path, media_type="application/zip", filename=path.name)
