import json
from pathlib import Path

import pytest

from export_final_node_entity_f1 import (
    BASE_SUFFIX,
    ExportValidationError,
    build_final_export,
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


def make_batch(tmp_path: Path, *, include_review_decision: bool = True) -> Path:
    batch_root = tmp_path / "review" / "1"
    current = batch_root / "current"
    state = batch_root / "state"
    state.joinpath("reviews", "DOC_A").mkdir(parents=True)

    write_json(
        current / "chunks" / "测试文献.chunk.json",
        {
            "doc_id": "DOC_A",
            "source_title": "测试文献",
            "chunks": [
                {
                    "chunk_id": "CH0001",
                    "section_title": "临床表现",
                    "section_path": ["正文", "临床表现"],
                    "page_start": 2,
                    "page_end": 2,
                    "text": "旧证据与新证据。另有纵隔气肿。",
                }
            ],
        },
    )
    write_json(
        current / "graph_property_schema_v3_6.json",
        {
            "schema_version": "3.6",
            "entities": {
                "diseases": {"enabled": True},
                "symptoms": {"enabled": True},
                "tests": {"enabled": True},
                "methods": {"enabled": False},
            },
            "relationships": {},
        },
    )

    label_rows = [
        {
            "entity_id": "OCC_ACCEPTED",
            "occurrence_id": "OCC_ACCEPTED",
            "document_id": "DOC_A",
            "chunk_id": "CH0001",
            "raw_surface": "机器接受实体",
            "semantic_name": "机器接受实体",
            "name": "机器接受实体",
            "content": "机器接受实体",
            "final_entity_type": "diseases",
            "status": "accepted",
            "role_status": "resolved",
            "semantic_role_contract_version": "semantic_role_contract_v6",
            "evidence_text": "旧证据",
        },
        {
            "entity_id": "OCC_REVIEW",
            "occurrence_id": "OCC_REVIEW",
            "document_id": "DOC_A",
            "chunk_id": "CH0001",
            "raw_surface": "旧名称",
            "semantic_name": "旧名称",
            "name": "旧名称",
            "content": "旧名称",
            "final_entity_type": "tests",
            "status": "review",
            "role_status": "unresolved",
            "semantic_role_contract_version": "semantic_role_contract_v6",
            "evidence_text": "旧证据",
        },
        {
            "entity_id": "OCC_DELETE",
            "occurrence_id": "OCC_DELETE",
            "document_id": "DOC_A",
            "chunk_id": "CH0001",
            "semantic_name": "人工删除实体",
            "name": "人工删除实体",
            "final_entity_type": "symptoms",
            "status": "review",
            "role_status": "unresolved",
            "semantic_role_contract_version": "semantic_role_contract_v6",
            "evidence_text": "旧证据",
        },
        {
            "entity_id": "OCC_MACHINE_REJECTED",
            "occurrence_id": "OCC_MACHINE_REJECTED",
            "document_id": "DOC_A",
            "chunk_id": "CH0001",
            "semantic_name": "机器拒绝实体",
            "name": "机器拒绝实体",
            "final_entity_type": "tests",
            "status": "rejected",
            "role_status": "unresolved",
            "semantic_role_contract_version": "semantic_role_contract_v6",
            "evidence_text": "旧证据",
        },
    ]
    write_jsonl(
        current / "entity_nodes" / "测试文献.entity_label_result.jsonl",
        label_rows,
    )
    write_jsonl(
        current / "entity_nodes" / "测试文献.entity_nodes.base.jsonl",
        [
            {
                "entity_id": "OCC_ACCEPTED",
                "occurrence_id": "OCC_ACCEPTED",
                "document_id": "DOC_A",
                "chunk_id": "CH0001",
                "raw_surface": "机器接受实体",
                "semantic_name": "机器接受实体",
                "name": "机器接受实体",
                "content": "机器接受实体",
                "entity_type": "diseases",
                "status": "accepted",
                "entity_status": "accepted",
                "role_status": "resolved",
                "semantic_role_contract_version": "semantic_role_contract_v6",
                "evidence_text": "旧证据",
            }
        ],
    )

    review_entities = [
        {
            "entity_id": "OCC_DELETE",
            "review_operation": "delete",
            "review_decision": "rejected",
            "review_flag": "deleted",
            "review_version": 3,
            "corrected_values": {},
        },
        {
            "entity_id": "REVIEW_ENTITY_NEW",
            "document_id": "multi_doc",
            "chunk_id": "DOC_A_CH0001",
            "name": "纵隔气肿",
            "entity_type": "symptoms",
            "evidence_text": "纵隔气 肿",
            "status": "pending",
            "entity_status": "review_added",
            "review_operation": "create",
            "review_decision": "accepted",
            "review_flag": "added",
            "review_version": 4,
            "corrected_values": {},
        },
    ]
    if include_review_decision:
        review_entities.insert(
            0,
            {
                "entity_id": "OCC_REVIEW",
                "review_operation": "update",
                "review_decision": "accepted",
                "review_flag": "modified",
                "review_version": 2,
                "corrected_values": {
                    "name": "新名称",
                    "entity_type": "symptoms",
                    "evidence_text": "新证据",
                    "review_canonical_id": "REVIEW_CANON_INTERNAL",
                },
            },
        )
    write_json(
        state / "reviews" / "DOC_A" / "DOC_A_CH0001.review.json",
        {
            "document_id": "DOC_A",
            "entities": review_entities,
            "audit_events": [],
        },
    )
    return batch_root


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_publishes_accepted_nodes_with_field_family_sync_and_audit(
    tmp_path: Path,
) -> None:
    batch_root = make_batch(tmp_path)
    output_dir = batch_root / "state" / "exports" / "node_entity_F1"

    manifest = build_final_export(
        batch_root=batch_root,
        output_dir=output_dir,
    )

    output = read_jsonl(output_dir / f"测试文献{BASE_SUFFIX}")
    label_output = read_jsonl(
        output_dir / "测试文献.entity_label_result.jsonl"
    )
    by_id = {row["entity_id"]: row for row in output}
    label_by_id = {row["entity_id"]: row for row in label_output}
    assert set(by_id) == {"OCC_ACCEPTED", "OCC_REVIEW", "REVIEW_ENTITY_NEW"}
    assert set(label_by_id) == set(by_id)
    assert all(row["status"] == row["entity_status"] == "accepted" for row in output)

    corrected = by_id["OCC_REVIEW"]
    assert corrected["raw_surface"] == "新名称"
    assert corrected["semantic_name"] == corrected["name"] == corrected["content"] == "新名称"
    assert corrected["entity_type"] == corrected["final_entity_type"] == "symptoms"
    assert corrected["evidence_text"] == "新证据"
    assert corrected["evidence_span"]["raw_text"] == "新证据"
    assert corrected["evidence_span"]["source"] == "physician_review"
    assert "review_canonical_id" not in corrected
    assert "corrected_values" not in corrected
    assert label_by_id["OCC_REVIEW"]["final_entity_type"] == "symptoms"
    assert label_by_id["OCC_REVIEW"]["semantic_name"] == "新名称"

    created = by_id["REVIEW_ENTITY_NEW"]
    assert created["document_id"] == "DOC_A"
    assert created["chunk_id"] == "CH0001"
    assert created["occurrence_id"] == "REVIEW_ENTITY_NEW"
    assert created["role_status"] == "unresolved"
    assert created["evidence_span"]["raw_text"] == "纵隔气肿"
    assert created["evidence_span"]["match_method"] == "layout_whitespace"

    assert manifest["publish_status"] == "final"
    assert manifest["invariants"]["accepted_only"] is True
    assert manifest["counts"]["retained"] == 3
    assert manifest["counts"]["physician_update"] == 1
    assert manifest["counts"]["physician_create"] == 1
    assert manifest["counts"]["exclude_machine"] == 1
    assert manifest["counts"]["exclude_physician"] == 1
    change_log = read_jsonl(output_dir / "node_entity_F1.change_log.jsonl")
    assert {row["action"] for row in change_log} == {"update", "delete", "create"}


def test_unresolved_review_blocks_publish_and_preserves_previous_output(
    tmp_path: Path,
) -> None:
    batch_root = make_batch(tmp_path, include_review_decision=False)
    output_dir = batch_root / "state" / "exports" / "node_entity_F1"
    output_dir.mkdir(parents=True)
    sentinel = output_dir / "previous.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(ExportValidationError, match="未完成复验"):
        build_final_export(batch_root=batch_root, output_dir=output_dir)

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert list(output_dir.iterdir()) == [sentinel]


def test_check_only_validates_without_publishing(tmp_path: Path) -> None:
    batch_root = make_batch(tmp_path)
    output_dir = batch_root / "state" / "exports" / "node_entity_F1"

    manifest = build_final_export(
        batch_root=batch_root,
        output_dir=output_dir,
        check_only=True,
    )

    assert manifest["counts"]["retained"] == 3
    assert not output_dir.exists()


def test_rejects_output_path_inside_immutable_source_tree(tmp_path: Path) -> None:
    batch_root = make_batch(tmp_path)

    with pytest.raises(ExportValidationError, match="不得覆盖源数据"):
        build_final_export(
            batch_root=batch_root,
            output_dir=batch_root / "current" / "entity_nodes",
        )
