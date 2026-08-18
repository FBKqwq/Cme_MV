"""Build a traceable preliminary entity set from all physician-review batches.

This intentionally does not publish a formal F1 artifact. Machine ``review``
rows without a final physician decision and unconfirmed physician-created rows
are quarantined under ``pending_review``. Documents without any entity result
file are omitted together with their PDF and Chunk file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import export_final_node_entity_f1 as exp


ALLOWED_CONTRACTS = {
    "semantic_role_contract_v6",
    "semantic_role_contract_v6_1",
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )


def write_line(handle, payload: dict[str, Any]) -> None:
    handle.write(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_permissive(
    batch_root: Path,
) -> tuple[
    dict[str, dict[str, Any]],
    list[exp.DocumentSource],
    list[str],
]:
    """Discover all usable documents without rejecting incomplete siblings."""
    documents = exp._load_chunk_documents(batch_root)
    entity_root = batch_root / "current" / "entity_nodes"
    selected: dict[str, Path] = {}
    for path in sorted(entity_root.glob(f"*{exp.BASE_SUFFIX}")):
        selected.setdefault(exp._match_document(path, documents), path)
    for path in sorted(entity_root.glob(f"*{exp.LABEL_SUFFIX}")):
        selected[exp._match_document(path, documents)] = path

    missing = sorted(set(documents) - set(selected))
    sources: list[exp.DocumentSource] = []
    for document_id in sorted(selected):
        entity_path = selected[document_id]
        base_path: Path | None = None
        if entity_path.name.endswith(exp.LABEL_SUFFIX):
            candidate = entity_path.with_name(
                exp._entity_stem(entity_path) + exp.BASE_SUFFIX
            )
            if candidate.is_file():
                base_path = candidate
        elif entity_path.name.endswith(exp.BASE_SUFFIX):
            base_path = entity_path
        metadata = documents[document_id]
        sources.append(
            exp.DocumentSource(
                document_id=document_id,
                title=str(metadata["title"]),
                chunks_path=Path(metadata["chunks_path"]),
                chunks=dict(metadata["chunks"]),
                entity_path=entity_path,
                base_path=base_path,
            )
        )
    return documents, sources, missing


def match_pdf(batch_root: Path, title: str) -> Path:
    pdfs = sorted((batch_root / "current" / "raw_pdf").glob("*.pdf"))
    matches = [path for path in pdfs if path.stem == title]
    if len(matches) != 1:
        clean_title = exp._clean_document_name(title)
        matches = [
            path
            for path in pdfs
            if exp._clean_document_name(path.stem) == clean_title
        ]
    if len(matches) != 1:
        raise exp.ExportValidationError(
            f"PDF 无法唯一匹配：{batch_root.name}/{title}/"
            f"{[path.name for path in matches]}"
        )
    return matches[0]


def materialize(
    *,
    source: dict[str, Any],
    review: dict[str, Any] | None,
    document: exp.DocumentSource,
    valid_types: set[str],
    default_contract: str | None,
    physician_created: bool = False,
) -> dict[str, Any]:
    """Apply a review delta while retaining the source Stage04 payload."""
    patch = exp._validated_patch(review or {})
    node = deepcopy(source)
    entity_id = str(source.get("entity_id") or "")
    chunk_id = exp._normalize_chunk_id(
        document.document_id, str(source.get("chunk_id") or "")
    )
    if not entity_id or chunk_id not in document.chunks:
        raise exp.ExportValidationError(
            f"实体缺少 ID 或引用未知 Chunk："
            f"{document.document_id}/{entity_id}/{chunk_id}"
        )

    entity_type = exp._effective_type({**source, **node}, patch)
    if entity_type not in valid_types:
        raise exp.ExportValidationError(
            f"实体类型不在 V3.6 契约中：{entity_id}/{entity_type}"
        )
    name = exp._effective_name({**source, **node}, patch)
    if not name:
        raise exp.ExportValidationError(f"实体名称为空：{entity_id}")
    evidence_text = str(
        patch.get("evidence_text")
        or source.get("evidence_text")
        or node.get("evidence_text")
        or ""
    ).strip()
    if not evidence_text:
        raise exp.ExportValidationError(f"实体证据为空：{entity_id}")

    contract = str(
        source.get("semantic_role_contract_version")
        or node.get("semantic_role_contract_version")
        or default_contract
        or ""
    )
    if contract not in ALLOWED_CONTRACTS:
        raise exp.ExportValidationError(
            f"实体语义角色契约不可用于初步整合："
            f"{entity_id}/{contract or '(missing)'}"
        )

    node.update(
        {
            "entity_id": entity_id,
            "occurrence_id": str(
                source.get("occurrence_id")
                or node.get("occurrence_id")
                or entity_id
            ),
            "document_id": document.document_id,
            "chunk_id": chunk_id,
            "entity_type": entity_type,
            "final_entity_type": entity_type,
            "semantic_name": name,
            "name": name,
            "content": name,
            "evidence_text": evidence_text,
            "status": "accepted",
            "entity_status": "accepted",
            "type_status": "accepted",
            "semantic_role_contract_version": contract,
        }
    )
    if "name" in patch or physician_created:
        node["raw_surface"] = name
    if review is not None:
        node["decision_source"] = "physician_review"
        node["acceptance_basis"] = "physician_review"
    if physician_created:
        chunk = document.chunks[chunk_id]
        node.update(
            {
                "source_title": document.title,
                "section_title": chunk.get("section_title"),
                "section_path": list(chunk.get("section_path") or []),
                "role_status": "unresolved",
                "source": "physician_review",
                "review_reasons": [
                    "physician_created_entity_requires_relation_schematic"
                ],
            }
        )
    if "evidence_text" in patch or physician_created:
        span = exp.locate_review_evidence(
            document_id=document.document_id,
            chunk=document.chunks[chunk_id],
            evidence_text=evidence_text,
        )
        node["evidence_span"] = span
        node["evidence_spans"] = [span]
        node["evidence_ids"] = [span["evidence_id"]]
        node["evidence_status"] = "located"

    exp._strip_review_fields(node)
    return node


def add_pending(
    pending: list[dict[str, Any]],
    source: dict[str, Any],
    *,
    batch_id: int,
    reason: str,
    review: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    record = deepcopy(source)
    metadata: dict[str, Any] = {
        "batch_id": str(batch_id),
        "reason": reason,
    }
    if review is not None:
        metadata["review_delta"] = deepcopy(review)
    if error:
        metadata["error"] = error
    record["_preliminary_pending"] = metadata
    pending.append(record)


def build(review_root: Path, staging: Path) -> dict[str, Any]:
    review_root = review_root.resolve()
    staging = staging.resolve()
    if staging.exists():
        raise FileExistsError(f"暂存目录已存在，拒绝覆盖：{staging}")
    if staging.parent != review_root.parent:
        raise ValueError(f"暂存目录必须位于 data 目录：{staging}")

    staging.mkdir(parents=True)
    for name in (
        "raw_pdf",
        "chunks",
        "entity_nodes",
        "pending_review",
        "excluded_entities",
        "manifests",
    ):
        (staging / name).mkdir()

    input_paths: set[Path] = set()
    missing_documents: list[dict[str, Any]] = []
    document_inventory: list[dict[str, Any]] = []
    change_log: list[dict[str, Any]] = []
    orphan_deltas: list[dict[str, Any]] = []
    global_counts: Counter[str] = Counter()
    batch_summaries: list[dict[str, Any]] = []
    global_entity_ids: dict[str, tuple[int, str]] = {}
    global_occurrence_ids: dict[str, tuple[int, str]] = {}
    output_name_keys: set[tuple[str, str]] = set()
    schema_source: Path | None = None
    schema_hash: str | None = None
    batch_contexts = []
    selection_signature: list[tuple[int, str, str]] = []

    for batch_id in range(1, 7):
        batch = review_root / str(batch_id)
        schemas = sorted((batch / "current").glob("graph_property_schema*.json"))
        if len(schemas) != 1:
            raise exp.ExportValidationError(
                f"第 {batch_id} 批 Schema 数量异常：{len(schemas)}"
            )
        current_schema_hash = file_sha256(schemas[0])
        if schema_hash is None:
            schema_hash = current_schema_hash
            schema_source = schemas[0]
        elif current_schema_hash != schema_hash:
            raise exp.ExportValidationError(
                f"第 {batch_id} 批 Schema 与其他批次不一致"
            )
        input_paths.add(schemas[0])

        documents, sources, missing = discover_permissive(batch)
        deltas, review_paths = exp.load_latest_entity_deltas(batch)
        input_paths.update(review_paths)
        by_doc: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for (document_id, entity_id), record in deltas.items():
            by_doc[document_id][entity_id] = record

        pdf_by_doc: dict[str, Path] = {}
        for source in sources:
            pdf_path = match_pdf(batch, source.title)
            pdf_by_doc[source.document_id] = pdf_path
            input_paths.update(
                {source.chunks_path, source.entity_path, pdf_path}
            )
            if source.base_path is not None:
                input_paths.add(source.base_path)
            selection_signature.append(
                (batch_id, source.document_id, source.entity_path.name)
            )

        for document_id in missing:
            metadata = documents[document_id]
            pdf_path = match_pdf(batch, str(metadata["title"]))
            input_paths.update({Path(metadata["chunks_path"]), pdf_path})
            missing_documents.append(
                {
                    "batch_id": str(batch_id),
                    "document_id": document_id,
                    "title": str(metadata["title"]),
                    "reason": "missing_entity_result",
                    "excluded_pdf": pdf_path.name,
                    "excluded_chunk_file": Path(metadata["chunks_path"]).name,
                    "chunk_count": max(0, len(metadata["chunks"]) - 1),
                }
            )

        batch_contexts.append(
            (batch_id, batch, sources, pdf_by_doc, by_doc, deltas)
        )

    input_snapshot = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in input_paths
    }
    shutil.copy2(schema_source, staging / "graph_property_schema_v3_6.json")

    for batch_id, batch, sources, pdf_by_doc, by_doc, deltas in batch_contexts:
        valid_types = exp.load_entity_types(batch)
        batch_counts: Counter[str] = Counter()
        used_delta_keys: set[tuple[str, str]] = set()

        for document in sources:
            pdf_path = pdf_by_doc[document.document_id]
            entity_stem = exp._entity_stem(document.entity_path)
            destinations = {
                "chunk": staging / "chunks" / document.chunks_path.name,
                "pdf": staging / "raw_pdf" / pdf_path.name,
                "label": staging
                / "entity_nodes"
                / f"{entity_stem}{exp.LABEL_SUFFIX}",
                "base": staging
                / "entity_nodes"
                / f"{entity_stem}{exp.BASE_SUFFIX}",
                "pending": staging
                / "pending_review"
                / f"{entity_stem}.pending_review.jsonl",
                "excluded": staging
                / "excluded_entities"
                / f"{entity_stem}.excluded_entities.jsonl",
            }
            for kind in ("chunk", "pdf", "label", "base"):
                key = (kind, destinations[kind].name)
                if key in output_name_keys:
                    raise exp.ExportValidationError(
                        f"整合输出文件名冲突：{kind}/{key[1]}"
                    )
                output_name_keys.add(key)

            shutil.copy2(document.chunks_path, destinations["chunk"])
            shutil.copy2(pdf_path, destinations["pdf"])

            review_by_id = by_doc.get(document.document_id, {})
            source_ids: set[str] = set()
            accepted_main_ids: set[str] = set()
            base_output_ids: set[str] = set()
            main_label_ids: set[str] = set()
            pending_records: list[dict[str, Any]] = []
            excluded_records: list[dict[str, Any]] = []
            contract_versions: Counter[str] = Counter()
            doc_counts: Counter[str] = Counter()

            with (
                destinations["label"].open(
                    "w", encoding="utf-8", newline="\n"
                ) as label_out,
                destinations["base"].open(
                    "w", encoding="utf-8", newline="\n"
                ) as base_out,
            ):
                for source_row in exp.read_jsonl(document.entity_path):
                    entity_id = str(source_row.get("entity_id") or "")
                    source_document_id = str(
                        source_row.get("document_id") or document.document_id
                    )
                    if (
                        not entity_id
                        or source_document_id != document.document_id
                        or entity_id in source_ids
                    ):
                        raise exp.ExportValidationError(
                            "源实体 ID 缺失、重复或跨文档："
                            f"{document.entity_path}/{entity_id}"
                        )
                    source_ids.add(entity_id)
                    machine_status = exp._machine_status(source_row)
                    if machine_status not in {"accepted", "review", "rejected"}:
                        raise exp.ExportValidationError(
                            f"未知机器状态：{document.document_id}/"
                            f"{entity_id}/{machine_status}"
                        )
                    contract = str(
                        source_row.get("semantic_role_contract_version") or ""
                    )
                    if contract:
                        contract_versions[contract] += 1

                    review = review_by_id.get(entity_id)
                    if review is not None:
                        used_delta_keys.add((document.document_id, entity_id))
                    action = exp._review_action(review, machine_status)
                    doc_counts[f"machine_{machine_status}"] += 1
                    doc_counts[f"action_{action}"] += 1
                    batch_counts[f"machine_{machine_status}"] += 1
                    batch_counts[f"action_{action}"] += 1
                    global_counts[f"machine_{machine_status}"] += 1
                    global_counts[f"action_{action}"] += 1

                    if action == "unresolved":
                        add_pending(
                            pending_records,
                            source_row,
                            batch_id=batch_id,
                            reason="machine_review_unresolved",
                            review=review,
                        )
                        continue
                    if action.startswith("exclude"):
                        excluded_records.append(
                            {
                                "batch_id": str(batch_id),
                                "document_id": document.document_id,
                                "source_title": document.title,
                                "entity_id": entity_id,
                                "name": exp._effective_name(source_row, {}),
                                "entity_type": exp._effective_type(source_row, {}),
                                "machine_status": machine_status,
                                "reason": (
                                    "physician_deleted"
                                    if action == "exclude_physician"
                                    else "machine_rejected"
                                ),
                                "review_version": (
                                    review.get("review_version") if review else None
                                ),
                            }
                        )
                        continue
                    if action == "invalid":
                        raise exp.ExportValidationError(
                            f"无法解释实体状态：{document.document_id}/{entity_id}"
                        )

                    try:
                        label_node = materialize(
                            source=source_row,
                            review=review,
                            document=document,
                            valid_types=valid_types,
                            default_contract=contract or None,
                        )
                    except exp.ExportValidationError as exc:
                        add_pending(
                            pending_records,
                            source_row,
                            batch_id=batch_id,
                            reason="retained_entity_failed_validation",
                            review=review,
                            error=str(exc),
                        )
                        doc_counts["validation_quarantine"] += 1
                        global_counts["validation_quarantine"] += 1
                        continue

                    if entity_id in global_entity_ids:
                        raise exp.ExportValidationError(
                            f"跨批次 entity_id 冲突：{entity_id}/"
                            f"{global_entity_ids[entity_id]}/"
                            f"{(batch_id, document.document_id)}"
                        )
                    occurrence_id = str(label_node.get("occurrence_id") or entity_id)
                    if occurrence_id in global_occurrence_ids:
                        raise exp.ExportValidationError(
                            f"跨批次 occurrence_id 冲突：{occurrence_id}/"
                            f"{global_occurrence_ids[occurrence_id]}/"
                            f"{(batch_id, document.document_id)}"
                        )
                    global_entity_ids[entity_id] = (
                        batch_id,
                        document.document_id,
                    )
                    global_occurrence_ids[occurrence_id] = (
                        batch_id,
                        document.document_id,
                    )
                    main_label_ids.add(entity_id)
                    write_line(label_out, label_node)
                    doc_counts["main_entities"] += 1
                    global_counts["main_source_entities"] += 1

                    if machine_status == "accepted" and document.base_path:
                        accepted_main_ids.add(entity_id)
                    else:
                        base_node = materialize(
                            source=source_row,
                            review=review,
                            document=document,
                            valid_types=valid_types,
                            default_contract=contract or None,
                        )
                        write_line(base_out, base_node)
                        base_output_ids.add(entity_id)

                    if review is not None:
                        patch = exp._validated_patch(review)
                        change_log.append(
                            {
                                "batch_id": str(batch_id),
                                "document_id": document.document_id,
                                "source_title": document.title,
                                "entity_id": entity_id,
                                "action": "update" if patch else "accept",
                                "machine_status": machine_status,
                                "review_version": review.get("review_version"),
                                "corrected_values": patch,
                            }
                        )

                if document.base_path is not None:
                    seen_base_ids: set[str] = set()
                    default_contract = (
                        contract_versions.most_common(1)[0][0]
                        if contract_versions
                        else None
                    )
                    for base_row in exp.read_jsonl(document.base_path):
                        entity_id = str(base_row.get("entity_id") or "")
                        if not entity_id or entity_id in seen_base_ids:
                            raise exp.ExportValidationError(
                                "Base 实体 ID 缺失或重复："
                                f"{document.base_path}/{entity_id}"
                            )
                        seen_base_ids.add(entity_id)
                        if entity_id not in accepted_main_ids:
                            continue
                        base_node = materialize(
                            source=base_row,
                            review=review_by_id.get(entity_id),
                            document=document,
                            valid_types=valid_types,
                            default_contract=default_contract,
                        )
                        write_line(base_out, base_node)
                        base_output_ids.add(entity_id)
                    missing_base = sorted(accepted_main_ids - seen_base_ids)
                    if missing_base:
                        raise exp.ExportValidationError(
                            "机器 accepted 实体缺少 Base Node："
                            f"{document.document_id}/{missing_base[:20]}"
                        )

                default_contract = (
                    contract_versions.most_common(1)[0][0]
                    if contract_versions
                    else "semantic_role_contract_v6"
                )
                for entity_id, review in sorted(review_by_id.items()):
                    key = (document.document_id, entity_id)
                    if key in used_delta_keys:
                        continue
                    used_delta_keys.add(key)
                    operation = str(
                        review.get("review_operation") or "source"
                    ).lower()
                    decision = str(
                        review.get("review_decision") or "pending"
                    ).lower()
                    if operation == "create":
                        if decision == "accepted":
                            try:
                                node = materialize(
                                    source=review,
                                    review=review,
                                    document=document,
                                    valid_types=valid_types,
                                    default_contract=default_contract,
                                    physician_created=True,
                                )
                            except exp.ExportValidationError as exc:
                                add_pending(
                                    pending_records,
                                    review,
                                    batch_id=batch_id,
                                    reason=(
                                        "accepted_physician_create_failed_validation"
                                    ),
                                    error=str(exc),
                                )
                                doc_counts["validation_quarantine"] += 1
                                global_counts["validation_quarantine"] += 1
                                continue
                            if entity_id in global_entity_ids:
                                raise exp.ExportValidationError(
                                    f"人工新增 entity_id 冲突：{entity_id}"
                                )
                            occurrence_id = str(
                                node.get("occurrence_id") or entity_id
                            )
                            if occurrence_id in global_occurrence_ids:
                                raise exp.ExportValidationError(
                                    "人工新增 occurrence_id 冲突："
                                    f"{occurrence_id}"
                                )
                            global_entity_ids[entity_id] = (
                                batch_id,
                                document.document_id,
                            )
                            global_occurrence_ids[occurrence_id] = (
                                batch_id,
                                document.document_id,
                            )
                            write_line(label_out, node)
                            write_line(base_out, node)
                            main_label_ids.add(entity_id)
                            base_output_ids.add(entity_id)
                            doc_counts["main_entities"] += 1
                            doc_counts["physician_created"] += 1
                            global_counts["main_physician_created"] += 1
                            change_log.append(
                                {
                                    "batch_id": str(batch_id),
                                    "document_id": document.document_id,
                                    "source_title": document.title,
                                    "entity_id": entity_id,
                                    "action": "create",
                                    "machine_status": "physician_created",
                                    "review_version": review.get("review_version"),
                                    "corrected_values": {},
                                }
                            )
                        elif decision == "rejected":
                            excluded_records.append(
                                {
                                    "batch_id": str(batch_id),
                                    "document_id": document.document_id,
                                    "source_title": document.title,
                                    "entity_id": entity_id,
                                    "name": review.get("name")
                                    or review.get("content"),
                                    "entity_type": review.get("entity_type"),
                                    "machine_status": "physician_created",
                                    "reason": "physician_created_rejected",
                                    "review_version": review.get("review_version"),
                                }
                            )
                        else:
                            add_pending(
                                pending_records,
                                review,
                                batch_id=batch_id,
                                reason="physician_created_unconfirmed",
                            )
                            doc_counts["pending_physician_created"] += 1
                            global_counts["pending_physician_created"] += 1
                    else:
                        orphan_deltas.append(
                            {
                                "batch_id": str(batch_id),
                                "document_id": document.document_id,
                                "source_title": document.title,
                                "entity_id": entity_id,
                                "reason": (
                                    "review_delta_does_not_match_source_entity"
                                ),
                                "review_delta": deepcopy(review),
                            }
                        )
                        doc_counts["orphan_review_delta"] += 1
                        global_counts["orphan_review_delta"] += 1

                if main_label_ids != base_output_ids:
                    raise exp.ExportValidationError(
                        "主结果 Label/Base 实体集合不一致："
                        f"{document.document_id}/"
                        f"label_only={sorted(main_label_ids-base_output_ids)[:10]}/"
                        f"base_only={sorted(base_output_ids-main_label_ids)[:10]}"
                    )

            if pending_records:
                write_jsonl(destinations["pending"], pending_records)
            if excluded_records:
                write_jsonl(destinations["excluded"], excluded_records)

            chunk_count = max(0, len(document.chunks) - 1)
            global_counts["documents"] += 1
            global_counts["chunks"] += chunk_count
            global_counts["pending_records"] += len(pending_records)
            global_counts["excluded_entities"] += len(excluded_records)
            batch_counts["documents"] += 1
            batch_counts["chunks"] += chunk_count
            batch_counts["main_entities"] += doc_counts["main_entities"]
            batch_counts["pending_records"] += len(pending_records)
            batch_counts["excluded_entities"] += len(excluded_records)

            document_inventory.append(
                {
                    "batch_id": str(batch_id),
                    "document_id": document.document_id,
                    "title": document.title,
                    "chunk_file": destinations["chunk"].name,
                    "pdf_file": destinations["pdf"].name,
                    "label_file": destinations["label"].name,
                    "base_file": destinations["base"].name,
                    "source_entity_file": document.entity_path.name,
                    "source_mode": (
                        "label_result"
                        if document.entity_path.name.endswith(exp.LABEL_SUFFIX)
                        else "base_fallback"
                    ),
                    "main_entity_count": len(main_label_ids),
                    "pending_count": len(pending_records),
                    "excluded_entity_count": len(excluded_records),
                    "counts": dict(sorted(doc_counts.items())),
                    "contract_versions": dict(sorted(contract_versions.items())),
                }
            )

        unmatched = sorted(set(deltas) - used_delta_keys)
        for document_id, entity_id in unmatched:
            review = deltas[(document_id, entity_id)]
            orphan_deltas.append(
                {
                    "batch_id": str(batch_id),
                    "document_id": document_id,
                    "source_title": None,
                    "entity_id": entity_id,
                    "reason": "review_delta_document_not_in_integrated_sources",
                    "review_delta": deepcopy(review),
                }
            )
            batch_counts["orphan_review_delta"] += 1
            global_counts["orphan_review_delta"] += 1

        batch_summaries.append(
            {
                "batch_id": str(batch_id),
                "counts": dict(sorted(batch_counts.items())),
            }
        )

    # Detect concurrent edits and newly appearing entity files before hashing.
    end_signature: list[tuple[int, str, str]] = []
    for batch_id in range(1, 7):
        batch = review_root / str(batch_id)
        _, sources, _ = discover_permissive(batch)
        end_signature.extend(
            (batch_id, source.document_id, source.entity_path.name)
            for source in sources
        )
    if sorted(selection_signature) != sorted(end_signature):
        raise RuntimeError("整合期间可用文献集合发生变化，拒绝发布暂存结果")
    for path, before in input_snapshot.items():
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != before:
            raise RuntimeError(f"整合期间输入文件发生变化：{path}")

    write_json(staging / "manifests" / "excluded_documents.json", missing_documents)
    write_json(staging / "manifests" / "document_inventory.json", document_inventory)
    write_json(staging / "manifests" / "batch_summary.json", batch_summaries)
    write_jsonl(staging / "manifests" / "change_log.jsonl", change_log)
    write_jsonl(
        staging / "manifests" / "orphan_review_deltas.jsonl", orphan_deltas
    )

    main_entity_count = (
        global_counts["main_source_entities"]
        + global_counts["main_physician_created"]
    )
    readme = f"""# 六批实体复验初步整合结果

生成时间：{datetime.now(timezone.utc).astimezone().isoformat()}

本目录是六个复验批次的初步整合产物，不是正式 F1 金标准。

## 纳入规则

- 保留机器 accepted 实体。
- 保留人工接收、人工修改和人工恢复的实体。
- 保留已确认的人工新增实体。
- 人工删除和未恢复的机器 rejected 实体不进入主结果。
- 未决实体放入 pending_review，不进入主结果。
- 完全缺少实体结果的文献，其 PDF 和 Chunk 不进入本目录。

## 目录

- raw_pdf：纳入文献 PDF。
- chunks：纳入文献 Chunk。
- entity_nodes：初步主结果，每篇文献同时提供 label_result 和 base。
- pending_review：尚未完成复验或未通过结构校验的隔离实体。
- excluded_entities：按人工删除或机器 rejected 排除的实体清单。
- manifests：文档清单、批次统计、变更日志、剔除清单和哈希清单。

## 关键数量

- 纳入文献：{global_counts['documents']}
- 纳入 Chunk：{global_counts['chunks']}
- 主结果实体：{main_entity_count}
- 其中人工新增实体：{global_counts['main_physician_created']}
- 隔离待复验实体：{global_counts['pending_records']}
- 排除实体：{global_counts['excluded_entities']}
- 剔除文献：{len(missing_documents)}
- 孤立复验增量：{len(orphan_deltas)}
"""
    (staging / "README.md").write_text(
        readme, encoding="utf-8", newline="\n"
    )

    input_records = []
    for path in sorted(input_paths, key=lambda value: str(value).casefold()):
        stat = path.stat()
        input_records.append(
            {
                "path": str(path.relative_to(review_root)),
                "bytes": stat.st_size,
                "sha256": file_sha256(path),
            }
        )
        if (stat.st_size, stat.st_mtime_ns) != input_snapshot[path]:
            raise RuntimeError(f"哈希期间输入文件发生变化：{path}")

    manifest_path = staging / "manifests" / "preliminary_final.manifest.json"
    output_records = []
    for path in sorted(
        (
            path
            for path in staging.rglob("*")
            if path.is_file() and path != manifest_path
        ),
        key=lambda value: str(value).casefold(),
    ):
        stat = path.stat()
        output_records.append(
            {
                "path": str(path.relative_to(staging)).replace("\\", "/"),
                "bytes": stat.st_size,
                "sha256": file_sha256(path),
            }
        )

    input_digest = hashlib.sha256(
        json.dumps(
            input_records, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
    ).hexdigest()
    output_digest = hashlib.sha256(
        json.dumps(
            output_records, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
    ).hexdigest()

    manifest = {
        "artifact": "six_batch_preliminary_entity_integration",
        "artifact_version": "preliminary_final_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_batches": ["1", "2", "3", "4", "5", "6"],
        "status": "preliminary_not_formal_f1",
        "policy": {
            "machine_accepted": "included",
            "machine_review_human_accepted_or_modified": "included",
            "machine_review_unresolved": "pending_review",
            "machine_rejected": "excluded_unless_physician_accepted",
            "physician_deleted": "excluded",
            "physician_created_accepted": "included",
            "physician_created_unconfirmed": "pending_review",
            "missing_entity_document": "pdf_chunk_and_document_excluded",
            "allowed_semantic_role_contracts": sorted(ALLOWED_CONTRACTS),
        },
        "counts": {
            **dict(sorted(global_counts.items())),
            "main_entities": main_entity_count,
            "excluded_documents": len(missing_documents),
            "orphan_review_deltas": len(orphan_deltas),
        },
        "batch_summaries": batch_summaries,
        "input_aggregate_sha256": input_digest,
        "output_aggregate_sha256": output_digest,
        "input_files": input_records,
        "output_files": output_records,
    }
    write_json(manifest_path, manifest)
    return {
        "staging": str(staging),
        "documents": global_counts["documents"],
        "chunks": global_counts["chunks"],
        "main_entities": main_entity_count,
        "main_source_entities": global_counts["main_source_entities"],
        "main_physician_created": global_counts["main_physician_created"],
        "pending_records": global_counts["pending_records"],
        "validation_quarantine": global_counts["validation_quarantine"],
        "excluded_entities": global_counts["excluded_entities"],
        "excluded_documents": len(missing_documents),
        "orphan_review_deltas": len(orphan_deltas),
        "input_files": len(input_records),
        "output_files": len(output_records),
        "input_aggregate_sha256": input_digest,
        "output_aggregate_sha256": output_digest,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "review",
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data"
        / "final.staging_019fe955",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args.review_root, args.staging)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
