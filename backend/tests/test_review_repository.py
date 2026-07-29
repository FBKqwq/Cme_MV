import json
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.review.repository import ReviewRepository


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
        encoding="utf-8",
    )


def make_task(
    tmp_path: Path,
    *,
    invalid_chunk: bool = False,
    with_pdf: bool = False,
) -> ReviewRepository:
    review_root = tmp_path / "data" / "review"
    inbox = review_root / "current"
    chunks_dir = inbox / "chunks"
    nodes_dir = inbox / "entity_nodes"
    raw_pdf_dir = inbox / "raw_pdf"
    chunks_dir.mkdir(parents=True)
    nodes_dir.mkdir()
    raw_pdf_dir.mkdir()

    schema = {
        "schema_version": "3.6",
        "entities": {
            "sub_diseases": {"label": "Sub_disease"},
            "symptoms": {"label": "Symptom"},
        },
        "relationships": {
            "manifests_as": {
                "enabled": True,
                "label_zh": "表现为",
                "source_entity_type": "Sub_disease",
                "target_entity_type": "Symptom",
            }
        },
    }
    chunks = {
        "doc_id": "TEST",
        "source_title": "测试共识",
        "total_pages": 1,
        "chunks": [
            {
                "chunk_id": "CH01",
                "section_title": "临床表现",
                "page_start": 1,
                "page_end": 1,
                "text": "白塞综合征主要表现为反复口腔溃疡。",
            }
        ],
    }
    entities = [
        {
            "entity_id": "E01",
            "chunk_id": "UNKNOWN" if invalid_chunk else "CH01",
            "entity_type": "sub_diseases",
            "name": "白塞综合征",
            "evidence_text": "白塞综合征",
        },
        {
            "entity_id": "E02",
            "chunk_id": "CH01",
            "entity_type": "symptoms",
            "name": "口腔溃疡",
            "evidence_text": "反复口腔溃疡",
        },
    ]

    (chunks_dir / "测试共识_chunk.json").write_text(
        json.dumps(chunks, ensure_ascii=False),
        encoding="utf-8",
    )
    write_jsonl(
        nodes_dir / "测试共识.entity_nodes.base.jsonl",
        entities,
    )
    schema_path = inbox / "graph_property_schema_v3_6.json"
    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False),
        encoding="utf-8",
    )
    if with_pdf:
        (raw_pdf_dir / "测试共识.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")

    return ReviewRepository(
        project_root=tmp_path,
        inbox_root=inbox,
        result_root=review_root / "state" / "results",
        export_root=review_root / "state" / "exports",
        schema_path=schema_path,
    )


def test_import_and_task_hash_are_stable(tmp_path: Path) -> None:
    repository = make_task(tmp_path)
    first_hash = repository.task()["input_hash"]
    reloaded = ReviewRepository(
        project_root=tmp_path,
        inbox_root=repository.inbox_root,
        result_root=repository.result_root,
        export_root=repository.export_root,
        schema_path=repository.schema_path,
    )
    task = reloaded.task()

    assert task["input_hash"] == first_hash
    assert task["document"]["title"] == "多文档复验"
    assert task["document"]["total_chunks"] == 1
    assert task["documents"] == [
        {
            "document_id": "TEST",
            "title": "测试共识",
            "chunk_count": 1,
            "pdf_available": False,
        }
    ]


def test_entity_edit_creates_conflict_and_rejects_stale_version(
    tmp_path: Path,
) -> None:
    repository = make_task(tmp_path)
    result = repository.update_entity(
        "E02",
        {
            "base_version": 0,
            "chunk_id": "TEST_CH01",
            "scope": "current",
            "name": "复发性口腔溃疡",
        },
    )
    detail = repository.chunk_detail("TEST_CH01")
    edited = next(item for item in detail["entities"] if item["entity_id"] == "E02")

    assert result["version"] == 1
    assert edited["name"] == "复发性口腔溃疡"
    assert edited["review_canonical_id"].startswith("REVIEW_CANON_")
    assert detail["relationships"][0]["conflicts"][0]["code"] == "needs_rebind"
    result_file = repository.result_root / "测试共识.review.json"
    persisted = json.loads(result_file.read_text(encoding="utf-8"))
    persisted_entity = next(
        item for item in persisted["entities"] if item["entity_id"] == "E02"
    )
    assert persisted_entity["name"] == "口腔溃疡"
    assert persisted_entity["review_flag"] == "modified"
    assert persisted_entity["corrected_values"]["name"] == "复发性口腔溃疡"
    assert not (repository.result_root.parent / "review.sqlite3").exists()

    with pytest.raises(HTTPException) as stale:
        repository.update_entity(
            "E02",
            {
                "base_version": 0,
                "chunk_id": "TEST_CH01",
                "scope": "current",
                "name": "旧标签页修改",
            },
        )
    assert stale.value.status_code == 409


def test_soft_delete_restore_and_relation_conflict(tmp_path: Path) -> None:
    repository = make_task(tmp_path)
    deleted = repository.delete_entity(
        "E02",
        chunk_id="TEST_CH01",
        base_version=0,
    )
    detail = repository.chunk_detail("TEST_CH01")
    entity = next(item for item in detail["entities"] if item["entity_id"] == "E02")

    assert entity["_review"]["deleted"] is True
    assert detail["relationships"][0]["conflicts"][0]["code"] == "missing_endpoint"

    repository.restore_entity(
        "E02",
        chunk_id="TEST_CH01",
        base_version=deleted["version"],
    )
    restored = repository.chunk_detail("TEST_CH01")
    entity = next(item for item in restored["entities"] if item["entity_id"] == "E02")
    assert entity["_review"]["deleted"] is False
    assert restored["relationships"][0]["conflicts"] == []


def test_approve_reload_and_final_export(tmp_path: Path) -> None:
    repository = make_task(tmp_path)
    approved = repository.approve_chunk("TEST_CH01", base_version=0)
    reloaded = ReviewRepository(
        project_root=tmp_path,
        inbox_root=repository.inbox_root,
        result_root=repository.result_root,
        export_root=repository.export_root,
        schema_path=repository.schema_path,
    )

    assert reloaded.task()["progress"]["approved"] == 1
    path = reloaded.build_export(final=True)
    assert path.exists()
    with zipfile.ZipFile(path) as bundle:
        assert {
            "reviewed_entities.jsonl",
            "reviewed_canonical_entities.jsonl",
            "reviewed_relationships.jsonl",
            "review_manifest.json",
            "change_log.json",
            "review_checklist.json",
            "results/测试共识.review.json",
        }.issubset(bundle.namelist())
        assert "review_state.db" not in bundle.namelist()
        manifest = json.loads(bundle.read("review_manifest.json"))
        assert manifest["final"] is True
        assert manifest["review_version"] == approved["version"]


def test_pdf_mapping_is_document_scoped(tmp_path: Path) -> None:
    repository = make_task(tmp_path, with_pdf=True)
    task = repository.task()

    assert task["document"]["pdf_available"] is True
    assert task["documents"][0]["pdf_available"] is True
    assert repository.source_pdf("TEST").name == "测试共识.pdf"

    with pytest.raises(HTTPException) as unknown:
        repository.source_pdf("UNKNOWN")
    assert unknown.value.status_code == 404


def test_import_rejects_unknown_entity_chunk(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未知 chunk"):
        make_task(tmp_path, invalid_chunk=True)
