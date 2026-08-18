import json
from pathlib import Path

from export_pending_physician_review import (
    collect_pending_entities,
    count_items,
    validate_batch_root,
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False),
        encoding="utf-8",
    )


def write_jsonl(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(value, ensure_ascii=False) for value in values)
        + "\n",
        encoding="utf-8",
    )


def make_batch(tmp_path: Path) -> Path:
    batch_root = tmp_path / "review" / "1"
    entity_root = batch_root / "current" / "entity_nodes"
    review_root = batch_root / "state" / "reviews" / "DOC_A"

    write_jsonl(
        entity_root / "test.entity_label_result.jsonl",
        [
            {
                "document_id": "DOC_A",
                "chunk_id": "CH0001",
                "entity_id": "OCC_UNTOUCHED",
                "name": "未操作实体",
                "entity_type": None,
                "teacher_candidate_type": "diseases",
                "evidence_text": "这是未操作实体的原文证据。",
                "status": "review",
            },
            {
                "document_id": "DOC_A",
                "chunk_id": "CH0001",
                "entity_id": "OCC_SAVED",
                "name": "已保存实体",
                "entity_type": "symptoms",
                "evidence_text": "已保存实体证据。",
                "status": "review",
            },
            {
                "document_id": "DOC_A",
                "chunk_id": "CH0002",
                "entity_id": "OCC_RESTORED",
                "name": "恢复过的实体",
                "entity_type": "tests",
                "evidence_text": "恢复过的实体证据。",
                "status": "review",
            },
            {
                "document_id": "DOC_A",
                "chunk_id": "CH0002",
                "entity_id": "OCC_ACCEPTED_BY_MACHINE",
                "name": "机器已接受实体",
                "entity_type": "diseases",
                "evidence_text": "不应进入医师复验。",
                "status": "accepted",
            },
        ],
    )
    write_json(
        review_root / "DOC_A_CH0001.review.json",
        {
            "document_id": "DOC_A",
            "entities": [
                {
                    "entity_id": "OCC_SAVED",
                    "review_version": 2,
                    "review_operation": "update",
                    "review_decision": "accepted",
                }
            ],
            "audit_events": [],
        },
    )
    write_json(
        review_root / "DOC_A_CH0002.review.json",
        {
            "document_id": "DOC_A",
            "entities": [],
            "audit_events": [
                {
                    "kind": "entity",
                    "record_id": "OCC_RESTORED",
                    "action": "restore",
                }
            ],
        },
    )
    return batch_root


def test_collects_only_machine_review_entities_without_human_operations(
    tmp_path: Path,
) -> None:
    batch_root = make_batch(tmp_path)

    payload = collect_pending_entities(batch_root)

    assert payload == [
        {
            "pdf_id": "DOC_A",
            "chunks": [
                {
                    "chunk_id": "DOC_A_CH0001",
                    "items": [
                        {
                            "item": "OCC_UNTOUCHED",
                            "object": {
                                "entity_name": "未操作实体",
                                "entity_type": "diseases",
                                "evidence": "这是未操作实体的原文证据。",
                            },
                        }
                    ],
                }
            ],
        }
    ]
    assert count_items(payload) == 1


def test_validate_batch_root_rejects_invalid_batch_id(tmp_path: Path) -> None:
    try:
        validate_batch_root(tmp_path, "../1")
    except ValueError as exc:
        assert "正整数" in str(exc)
    else:
        raise AssertionError("无效批次号应被拒绝")
