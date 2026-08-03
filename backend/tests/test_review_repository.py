import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

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
    with_label_result: bool = False,
    with_second_document: bool = False,
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
    if with_second_document:
        second_chunks = {
            "doc_id": "SECOND",
            "source_title": "第二份共识",
            "total_pages": 1,
            "chunks": [
                {
                    "chunk_id": "CH01",
                    "section_title": "诊断",
                    "page_start": 1,
                    "page_end": 1,
                    "text": "第二种疾病可表现为发热。",
                }
            ],
        }
        (chunks_dir / "第二份共识_chunk.json").write_text(
            json.dumps(second_chunks, ensure_ascii=False),
            encoding="utf-8",
        )
        write_jsonl(
            nodes_dir / "第二份共识.entity_nodes.base.jsonl",
            [
                {
                    "entity_id": "S01",
                    "chunk_id": "CH01",
                    "entity_type": "sub_diseases",
                    "name": "第二种疾病",
                    "evidence_text": "第二种疾病",
                },
                {
                    "entity_id": "S02",
                    "chunk_id": "CH01",
                    "entity_type": "symptoms",
                    "name": "发热",
                    "evidence_text": "表现为发热",
                },
            ],
        )
    if with_label_result:
        write_jsonl(
            nodes_dir / "测试共识.entity_label_result.jsonl",
            [
                *entities,
                {
                    "entity_id": "E03",
                    "chunk_id": "CH01",
                    "entity_type": "",
                    "proposed_entity_type": "symptoms",
                    "name": "待复验症状",
                    "evidence_text": "待复验症状",
                    "status": "review",
                },
                {
                    "entity_id": "E04",
                    "chunk_id": "CH01",
                    "entity_type": "",
                    "teacher_candidate_type": "symptoms",
                    "name": "已拒绝症状",
                    "evidence_text": "已拒绝症状",
                    "status": "rejected",
                },
            ],
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


def test_complete_label_result_overrides_base_file(tmp_path: Path) -> None:
    repository = make_task(tmp_path, with_label_result=True)
    detail = repository.chunk_detail("TEST_CH01")

    assert {entity["entity_id"] for entity in detail["entities"]} == {
        "E01",
        "E02",
        "E03",
        "E04",
    }
    assert {entity.get("status") for entity in detail["entities"]} == {
        None,
        "review",
        "rejected",
    }
    assert {
        entity["entity_type"]
        for entity in detail["entities"]
        if entity["entity_id"] in {"E03", "E04"}
    } == {"symptoms"}
    assert any(
        name.endswith(".entity_label_result.jsonl")
        for name in repository.checksums
    )
    assert not any(
        name.endswith(".entity_nodes.base.jsonl")
        for name in repository.checksums
    )


def test_source_upgrade_preserves_existing_human_review(tmp_path: Path) -> None:
    repository = make_task(tmp_path)
    repository.update_entity(
        "E02",
        {
            "base_version": 0,
            "chunk_id": "TEST_CH01",
            "scope": "current",
            "status": "accepted",
        },
    )
    nodes_dir = repository.inbox_root / "entity_nodes"
    base_entities = [
        json.loads(line)
        for line in (
            nodes_dir / "测试共识.entity_nodes.base.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line
    ]
    write_jsonl(
        nodes_dir / "测试共识.entity_label_result.jsonl",
        [
            *base_entities,
            {
                "entity_id": "E03",
                "chunk_id": "CH01",
                "entity_type": "symptoms",
                "name": "待复验症状",
                "evidence_text": "待复验症状",
                "status": "review",
            },
        ],
    )

    reloaded = ReviewRepository(
        project_root=tmp_path,
        inbox_root=repository.inbox_root,
        result_root=repository.result_root,
        export_root=repository.export_root,
        schema_path=repository.schema_path,
    )
    detail = reloaded.chunk_detail("TEST_CH01")
    approved = next(
        entity for entity in detail["entities"] if entity["entity_id"] == "E02"
    )

    assert approved["_review"]["operation"] == "update"
    assert approved["status"] == "accepted"
    assert any(entity["entity_id"] == "E03" for entity in detail["entities"])


def test_chunk_entity_snapshot_saves_once_and_restores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = make_task(tmp_path)
    save_calls = 0
    original_save = repository._save_result

    def counted_save(document_id: str) -> None:
        nonlocal save_calls
        save_calls += 1
        original_save(document_id)

    monkeypatch.setattr(repository, "_save_result", counted_save)
    saved = repository.save_chunk_entities(
        "TEST_CH01",
        {
            "base_version": 0,
            "entities": [
                {
                    "entity_id": "E01",
                    "name": "白塞综合征",
                    "entity_type": "sub_diseases",
                    "evidence_text": "白塞综合征",
                    "rejected": False,
                },
                {
                    "entity_id": "E02",
                    "name": "复发性口腔溃疡",
                    "entity_type": "symptoms",
                    "evidence_text": "反复口腔溃疡",
                    "rejected": True,
                },
            ],
        },
    )
    detail = repository.chunk_detail("TEST_CH01")
    rejected = next(
        entity for entity in detail["entities"] if entity["entity_id"] == "E02"
    )

    assert saved == {"chunk_id": "TEST_CH01", "changed": 1, "version": 1}
    assert save_calls == 1
    assert rejected["name"] == "复发性口腔溃疡"
    assert rejected["_review"]["deleted"] is True

    restored = repository.save_chunk_entities(
        "TEST_CH01",
        {
            "base_version": 1,
            "entities": [
                {
                    "entity_id": "E01",
                    "name": "白塞综合征",
                    "entity_type": "sub_diseases",
                    "evidence_text": "白塞综合征",
                    "rejected": False,
                },
                {
                    "entity_id": "E02",
                    "name": "复发性口腔溃疡",
                    "entity_type": "symptoms",
                    "evidence_text": "反复口腔溃疡",
                    "rejected": False,
                },
            ],
        },
    )
    detail = repository.chunk_detail("TEST_CH01")
    restored_entity = next(
        entity for entity in detail["entities"] if entity["entity_id"] == "E02"
    )

    assert restored["version"] == 2
    assert save_calls == 2
    assert restored_entity["name"] == "复发性口腔溃疡"
    assert restored_entity["_review"]["deleted"] is False


def test_review_entity_manual_approval_survives_reload_and_can_be_undone(
    tmp_path: Path,
) -> None:
    repository = make_task(tmp_path, with_label_result=True)
    detail = repository.chunk_detail("TEST_CH01")

    def snapshots(*, approved: bool) -> list[dict]:
        return [
            {
                "entity_id": entity["entity_id"],
                "name": entity["name"],
                "entity_type": entity["entity_type"],
                "evidence_text": entity.get("evidence_text") or entity["name"],
                "rejected": False,
                "approved": approved if entity["entity_id"] == "E03" else False,
            }
            for entity in detail["entities"]
        ]

    saved = repository.save_chunk_entities(
        "TEST_CH01",
        {
            "base_version": 0,
            "entities": snapshots(approved=True),
        },
    )
    reloaded = ReviewRepository(
        project_root=tmp_path,
        inbox_root=repository.inbox_root,
        result_root=repository.result_root,
        export_root=repository.export_root,
        schema_path=repository.schema_path,
    )
    approved_entity = next(
        entity
        for entity in reloaded.chunk_detail("TEST_CH01")["entities"]
        if entity["entity_id"] == "E03"
    )

    assert approved_entity["status"] == "review"
    assert approved_entity["_review"]["approved"] is True
    assert approved_entity["_review"]["deleted"] is False

    reloaded.save_chunk_entities(
        "TEST_CH01",
        {
            "base_version": saved["version"],
            "entities": [
                {
                    "entity_id": entity["entity_id"],
                    "name": entity["name"],
                    "entity_type": entity["entity_type"],
                    "evidence_text": entity.get("evidence_text") or entity["name"],
                    "rejected": False,
                    "approved": False,
                }
                for entity in reloaded.chunk_detail("TEST_CH01")["entities"]
            ],
        },
    )
    restored = ReviewRepository(
        project_root=tmp_path,
        inbox_root=repository.inbox_root,
        result_root=repository.result_root,
        export_root=repository.export_root,
        schema_path=repository.schema_path,
    )
    pending_entity = next(
        entity
        for entity in restored.chunk_detail("TEST_CH01")["entities"]
        if entity["entity_id"] == "E03"
    )

    assert pending_entity["status"] == "review"
    assert pending_entity["_review"]["approved"] is False


def test_machine_rejected_entity_can_be_manually_accepted(
    tmp_path: Path,
) -> None:
    repository = make_task(tmp_path, with_label_result=True)
    detail = repository.chunk_detail("TEST_CH01")
    repository.save_chunk_entities(
        "TEST_CH01",
        {
            "base_version": 0,
            "entities": [
                {
                    "entity_id": entity["entity_id"],
                    "name": entity["name"],
                    "entity_type": entity["entity_type"],
                    "evidence_text": entity.get("evidence_text") or entity["name"],
                    "rejected": False,
                    "approved": entity["entity_id"] == "E04",
                }
                for entity in detail["entities"]
            ],
        },
    )

    reloaded = ReviewRepository(
        project_root=tmp_path,
        inbox_root=repository.inbox_root,
        result_root=repository.result_root,
        export_root=repository.export_root,
        schema_path=repository.schema_path,
    )
    accepted = next(
        entity
        for entity in reloaded.chunk_detail("TEST_CH01")["entities"]
        if entity["entity_id"] == "E04"
    )

    assert accepted["status"] == "rejected"
    assert accepted["_review"]["approved"] is True
    assert accepted["_review"]["deleted"] is False


def test_chunk_entity_save_reuses_hot_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = make_task(tmp_path)
    repository.chunk_detail("TEST_CH01")

    def unexpected_rebuild() -> list[dict]:
        raise AssertionError("chunk save should not rebuild the full projection")

    monkeypatch.setattr(repository, "projected_entities", unexpected_rebuild)
    monkeypatch.setattr(repository, "projected_relationships", unexpected_rebuild)

    saved = repository.save_chunk_entities(
        "TEST_CH01",
        {
            "base_version": 0,
            "entities": [
                {
                    "entity_id": "E01",
                    "name": "白塞综合征",
                    "entity_type": "sub_diseases",
                    "evidence_text": "白塞综合征",
                    "rejected": False,
                },
                {
                    "entity_id": "E02",
                    "name": "复发性口腔溃疡",
                    "entity_type": "symptoms",
                    "evidence_text": "反复口腔溃疡",
                    "rejected": False,
                },
            ],
        },
    )
    detail = repository.chunk_detail("TEST_CH01")
    edited = next(item for item in detail["entities"] if item["entity_id"] == "E02")

    assert saved["version"] == 1
    assert detail["version"] == 1
    assert edited["name"] == "复发性口腔溃疡"


def test_chunk_entity_save_rolls_back_memory_when_disk_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = make_task(tmp_path)
    repository.chunk_detail("TEST_CH01")

    def fail_save(document_id: str) -> None:
        raise OSError(f"cannot write {document_id}")

    monkeypatch.setattr(repository, "_save_result", fail_save)

    with pytest.raises(OSError, match="cannot write"):
        repository.save_chunk_entities(
            "TEST_CH01",
            {
                "base_version": 0,
                "entities": [
                    {
                        "entity_id": "E01",
                        "name": "白塞综合征",
                        "entity_type": "sub_diseases",
                        "evidence_text": "白塞综合征",
                        "rejected": False,
                    },
                    {
                        "entity_id": "E02",
                        "name": "不应保留",
                        "entity_type": "symptoms",
                        "evidence_text": "反复口腔溃疡",
                        "rejected": False,
                    },
                ],
            },
        )

    detail = repository.chunk_detail("TEST_CH01")
    entity = next(item for item in detail["entities"] if item["entity_id"] == "E02")
    assert repository.version() == 0
    assert detail["version"] == 0
    assert entity["name"] == "口腔溃疡"


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
    assert detail["relationships"] == []
    result_file = repository._chunk_delta_path("TEST", "TEST_CH01")
    persisted = json.loads(result_file.read_text(encoding="utf-8"))
    persisted_entity = next(
        item for item in persisted["entities"] if item["entity_id"] == "E02"
    )
    assert persisted["format"] == "chunk-review-delta-v1"
    assert persisted_entity["review_flag"] == "modified"
    assert persisted_entity["corrected_values"]["name"] == "复发性口腔溃疡"
    assert "mention_context" not in persisted_entity
    assert not (repository.result_root / "测试共识.review.json").exists()
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


def test_different_pdfs_can_save_concurrently_with_independent_versions(
    tmp_path: Path,
) -> None:
    repository = make_task(tmp_path, with_second_document=True)
    barrier = Barrier(2)

    def save_entity_name(
        chunk_id: str,
        target_id: str,
        target_name: str,
    ) -> dict:
        detail = repository.chunk_detail(chunk_id)
        entities = [
            {
                "entity_id": entity["entity_id"],
                "name": (
                    target_name
                    if entity["entity_id"] == target_id
                    else entity["name"]
                ),
                "entity_type": entity["entity_type"],
                "evidence_text": entity.get("evidence_text") or entity["name"],
                "rejected": False,
                "approved": False,
            }
            for entity in detail["entities"]
        ]
        barrier.wait()
        return repository.save_chunk_entities(
            chunk_id,
            {
                "base_version": detail["version"],
                "entities": entities,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            save_entity_name,
            "TEST_CH01",
            "E02",
            "复发性口腔溃疡",
        )
        second = executor.submit(
            save_entity_name,
            "SECOND_CH01",
            "S02",
            "持续发热",
        )
        results = [first.result(), second.result()]

    assert [result["version"] for result in results] == [1, 1]
    assert repository.document_version("TEST") == 1
    assert repository.document_version("SECOND") == 1
    assert repository.chunk_detail("TEST_CH01")["version"] == 1
    assert repository.chunk_detail("SECOND_CH01")["version"] == 1

    reloaded = ReviewRepository(
        project_root=tmp_path,
        inbox_root=repository.inbox_root,
        result_root=repository.result_root,
        export_root=repository.export_root,
        schema_path=repository.schema_path,
    )
    first_name = next(
        entity["name"]
        for entity in reloaded.chunk_detail("TEST_CH01")["entities"]
        if entity["entity_id"] == "E02"
    )
    second_name = next(
        entity["name"]
        for entity in reloaded.chunk_detail("SECOND_CH01")["entities"]
        if entity["entity_id"] == "S02"
    )

    assert first_name == "复发性口腔溃疡"
    assert second_name == "持续发热"


def test_soft_delete_restore_and_relation_conflict(tmp_path: Path) -> None:
    repository = make_task(tmp_path)
    created = repository.create_relationship(
        {
            "base_version": 0,
            "chunk_id": "TEST_CH01",
            "start_entity_id": "E01",
            "relation_type": "manifests_as",
            "end_entity_id": "E02",
            "evidence_text": "主要表现为反复口腔溃疡",
        }
    )
    deleted = repository.delete_entity(
        "E02",
        chunk_id="TEST_CH01",
        base_version=created["version"],
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


def test_entities_do_not_create_synthetic_relationships(tmp_path: Path) -> None:
    repository = make_task(tmp_path)

    detail = repository.chunk_detail("TEST_CH01")
    summary = repository.chunk_summaries()[0]

    assert detail["relationships"] == []
    assert summary["relation_count"] == 0
    assert summary["issue_count"] == 0


def test_chunk_detail_omits_heavy_inference_fields(tmp_path: Path) -> None:
    repository = make_task(tmp_path)
    repository.entities[0]["mention_context"] = {"trace": "x" * 100_000}
    repository.entities[0]["llm_views"] = [{"prompt": "y" * 100_000}]

    detail = repository.chunk_detail("TEST_CH01")
    entity = next(item for item in detail["entities"] if item["entity_id"] == "E01")

    assert entity["name"] == "白塞综合征"
    assert "mention_context" not in entity
    assert "llm_views" not in entity
    assert len(json.dumps(detail, ensure_ascii=False)) < 10_000


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


def test_review_snapshot_is_reused_and_invalidated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = make_task(tmp_path)
    calls = {"entities": 0, "canonicals": 0, "relationships": 0}

    for name, key in (
        ("projected_entities", "entities"),
        ("projected_canonical_entities", "canonicals"),
        ("projected_relationships", "relationships"),
    ):
        original = getattr(repository, name)

        def counted(original=original, key=key):
            calls[key] += 1
            return original()

        monkeypatch.setattr(repository, name, counted)

    repository.chunk_summaries()
    repository.chunk_detail("TEST_CH01")
    repository.chunk_detail("TEST_CH01")

    assert calls == {"entities": 1, "canonicals": 1, "relationships": 1}

    approved = repository.approve_chunk("TEST_CH01", base_version=0)
    detail = repository.chunk_detail("TEST_CH01")

    assert approved["version"] == 1
    assert detail["version"] == 1
    assert detail["review"]["status"] == "approved"
    assert calls == {"entities": 2, "canonicals": 2, "relationships": 2}


def test_chunk_summary_keeps_chunks_without_entities(tmp_path: Path) -> None:
    repository = make_task(tmp_path)
    empty_chunk = {
        "chunk_id": "TEST_CH02",
        "section_title": "空章节",
        "text": "",
        "_doc_id": "TEST",
        "_source_title": "测试共识",
    }
    repository.chunks.append(empty_chunk)
    repository.chunk_by_id["TEST_CH02"] = empty_chunk

    summary = next(
        item
        for item in repository.chunk_summaries()
        if item["chunk_id"] == "TEST_CH02"
    )

    assert summary["entity_count"] == 0
    assert summary["relation_count"] == 0
