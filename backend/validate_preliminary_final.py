#!/usr/bin/env python3
"""Independently validate a preliminary entity artifact.

The artifact path is always supplied by the caller. Dataset-specific document
counts are optional acceptance gates instead of hidden local defaults.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterator, Sequence


ALLOWED_CONTRACTS = {
    "semantic_role_contract_v6",
    "semantic_role_contract_v6_1",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not an object")
            yield line_number, value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("必须是非负整数")
    return parsed


def require_expected_count(
    actual: int,
    expected: int | None,
    label: str,
) -> None:
    if expected is not None:
        require(actual == expected, f"expected {expected} {label}, got {actual}")


def validate(
    root: Path,
    *,
    expected_documents: int | None = None,
    expected_excluded_documents: int | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    require(root.is_dir(), f"artifact directory does not exist: {root}")
    manifest_path = root / "manifests" / "preliminary_final.manifest.json"
    manifest = load_json(manifest_path)
    inventory = load_json(root / "manifests" / "document_inventory.json")
    excluded_documents = load_json(
        root / "manifests" / "excluded_documents.json"
    )
    schema = load_json(root / "graph_property_schema_v3_6.json")
    entity_types = set(schema["entities"]) - {"methods"}

    require(manifest["status"] == "preliminary_not_formal_f1", "bad status")
    require(len(inventory) == manifest["counts"]["documents"], "document count")
    require(
        len(excluded_documents) == manifest["counts"]["excluded_documents"],
        "excluded document count",
    )
    require_expected_count(
        len(inventory),
        expected_documents,
        "included documents",
    )
    require_expected_count(
        len(excluded_documents),
        expected_excluded_documents,
        "excluded documents",
    )

    actual_files = {
        str(path.relative_to(root)).replace("\\", "/"): path
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    recorded_files = {row["path"]: row for row in manifest["output_files"]}
    require(set(actual_files) == set(recorded_files), "output file inventory mismatch")
    verified_records: list[dict[str, Any]] = []
    for relative_path in sorted(actual_files, key=str.casefold):
        path = actual_files[relative_path]
        row = recorded_files[relative_path]
        size = path.stat().st_size
        digest = sha256(path)
        require(size == row["bytes"], f"size mismatch: {relative_path}")
        require(digest == row["sha256"], f"hash mismatch: {relative_path}")
        verified_records.append(
            {"path": relative_path, "bytes": size, "sha256": digest}
        )
    aggregate = hashlib.sha256(
        json.dumps(
            verified_records, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
    ).hexdigest()
    require(
        aggregate == manifest["output_aggregate_sha256"],
        "output aggregate hash mismatch",
    )

    require(len(list((root / "raw_pdf").glob("*.pdf"))) == len(inventory), "PDF count")
    require(len(list((root / "chunks").glob("*.json"))) == len(inventory), "chunk file count")
    require(
        len(list((root / "entity_nodes").glob("*entity_label_result.jsonl")))
        == len(inventory),
        "label file count",
    )
    require(
        len(list((root / "entity_nodes").glob("*entity_nodes.base.jsonl")))
        == len(inventory),
        "base file count",
    )

    global_entity_ids: set[str] = set()
    global_occurrence_ids: set[str] = set()
    counts: Counter[str] = Counter()
    seen_documents: set[str] = set()
    for document in inventory:
        document_id = document["document_id"]
        require(document_id not in seen_documents, f"duplicate document: {document_id}")
        seen_documents.add(document_id)

        chunk_path = root / "chunks" / document["chunk_file"]
        pdf_path = root / "raw_pdf" / document["pdf_file"]
        label_path = root / "entity_nodes" / document["label_file"]
        base_path = root / "entity_nodes" / document["base_file"]
        for path in (chunk_path, pdf_path, label_path, base_path):
            require(path.is_file(), f"missing document artifact: {path}")

        chunk_doc = load_json(chunk_path)
        require(chunk_doc["doc_id"] == document_id, f"chunk doc id: {chunk_path}")
        chunk_ids = {"__DOC__"}
        for chunk in chunk_doc["chunks"]:
            chunk_id = chunk.get("chunk_id")
            require(chunk_id, f"missing chunk id: {chunk_path}")
            require(chunk_id not in chunk_ids, f"duplicate chunk id: {chunk_id}")
            chunk_ids.add(chunk_id)
        counts["chunks"] += len(chunk_doc["chunks"])

        label_ids: set[str] = set()
        base_ids: set[str] = set()
        for _, row in iter_jsonl(label_path):
            entity_id = row.get("entity_id")
            occurrence_id = row.get("occurrence_id")
            require(entity_id, f"missing entity id: {label_path}")
            require(occurrence_id, f"missing occurrence id: {label_path}")
            require(entity_id not in global_entity_ids, f"duplicate entity id: {entity_id}")
            require(
                occurrence_id not in global_occurrence_ids,
                f"duplicate occurrence id: {occurrence_id}",
            )
            require(row.get("document_id") == document_id, f"wrong document: {entity_id}")
            require(row.get("chunk_id") in chunk_ids, f"bad chunk ref: {entity_id}")
            require(row.get("entity_type") in entity_types, f"bad type: {entity_id}")
            require(str(row.get("name") or "").strip(), f"missing name: {entity_id}")
            require(
                str(row.get("evidence_text") or "").strip(),
                f"missing evidence: {entity_id}",
            )
            require(row.get("status") == "accepted", f"bad status: {entity_id}")
            require(row.get("entity_status") == "accepted", f"bad entity status: {entity_id}")
            require(
                row.get("semantic_role_contract_version") in ALLOWED_CONTRACTS,
                f"bad contract: {entity_id}",
            )
            label_ids.add(entity_id)
            global_entity_ids.add(entity_id)
            global_occurrence_ids.add(occurrence_id)

        for _, row in iter_jsonl(base_path):
            entity_id = row.get("entity_id")
            require(entity_id, f"missing base entity id: {base_path}")
            require(entity_id not in base_ids, f"duplicate base entity: {entity_id}")
            require(row.get("document_id") == document_id, f"bad base document: {entity_id}")
            require(row.get("chunk_id") in chunk_ids, f"bad base chunk: {entity_id}")
            require(row.get("entity_type") in entity_types, f"bad base type: {entity_id}")
            require(row.get("status") == "accepted", f"bad base status: {entity_id}")
            require(row.get("entity_status") == "accepted", f"bad base entity status: {entity_id}")
            base_ids.add(entity_id)

        require(label_ids == base_ids, f"label/base mismatch: {document['title']}")
        require(
            len(label_ids) == document["main_entity_count"],
            f"document entity count mismatch: {document['title']}",
        )
        counts["main_entities"] += len(label_ids)

    pending = sum(
        1
        for path in (root / "pending_review").glob("*.jsonl")
        for _ in iter_jsonl(path)
    )
    excluded = sum(
        1
        for path in (root / "excluded_entities").glob("*.jsonl")
        for _ in iter_jsonl(path)
    )
    orphan = sum(
        1
        for _ in iter_jsonl(root / "manifests" / "orphan_review_deltas.jsonl")
    )
    require(counts["chunks"] == manifest["counts"]["chunks"], "chunk total")
    require(
        counts["main_entities"] == manifest["counts"]["main_entities"],
        "main entity total",
    )
    require(pending == manifest["counts"]["pending_records"], "pending total")
    require(excluded == manifest["counts"]["excluded_entities"], "excluded total")
    require(orphan == manifest["counts"]["orphan_review_deltas"], "orphan total")

    for row in excluded_documents:
        require(
            not (root / "raw_pdf" / row["excluded_pdf"]).exists(),
            f"excluded PDF leaked: {row['excluded_pdf']}",
        )
        require(
            not (root / "chunks" / row["excluded_chunk_file"]).exists(),
            f"excluded chunk leaked: {row['excluded_chunk_file']}",
        )

    return {
        "status": "pass",
        "documents": len(inventory),
        "excluded_documents": len(excluded_documents),
        "chunks": counts["chunks"],
        "main_entities": counts["main_entities"],
        "pending_records": pending,
        "excluded_entities": excluded,
        "orphan_review_deltas": orphan,
        "verified_output_files": len(verified_records),
        "output_aggregate_sha256": aggregate,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifact",
        type=Path,
        help="待校验的 preliminary artifact 目录",
    )
    parser.add_argument(
        "--expected-documents",
        type=non_negative_int,
        help="可选门禁：预期纳入的文献数量",
    )
    parser.add_argument(
        "--expected-excluded-documents",
        type=non_negative_int,
        help="可选门禁：预期排除的文献数量",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        result = validate(
            arguments.artifact,
            expected_documents=arguments.expected_documents,
            expected_excluded_documents=(
                arguments.expected_excluded_documents
            ),
        )
    except (AssertionError, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
