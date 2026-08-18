"""Publish physician-adjudicated entities as downstream Stage04 base nodes.

The source and review delta directories stay immutable.  A successful run
creates one ``*.entity_nodes.base.jsonl`` file per document under
``state/exports/node_entity_F1`` plus an input/output manifest and change log.

Usage:
    python export_final_node_entity_f1.py 1
    python export_final_node_entity_f1.py 1 --check-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


BATCH_ID_PATTERN = re.compile(r"^[1-9]\d*$")
LABEL_SUFFIX = ".entity_label_result.jsonl"
BASE_SUFFIX = ".entity_nodes.base.jsonl"
DEFAULT_OUTPUT_DIR_NAME = "node_entity_F1"
REVIEW_INTERNAL_FIELDS = {
    "corrected_values",
    "restore_metadata",
    "review_canonical_id",
    "review_decision",
    "review_flag",
    "review_operation",
    "review_scope",
    "review_updated_at",
    "review_version",
}
EDITABLE_FIELDS = {"name", "entity_type", "evidence_text"}
IGNORED_PATCH_FIELDS = {"review_canonical_id", "status"}
LAYOUT_IGNORED = {"\u200b", "\ufeff", "\u00ad"}


class ExportValidationError(ValueError):
    """Raised when review state cannot be published without data loss."""


@dataclass(frozen=True)
class DocumentSource:
    document_id: str
    title: str
    chunks_path: Path
    chunks: dict[str, dict[str, Any]]
    entity_path: Path
    base_path: Path | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ExportValidationError(f"JSON 顶层必须是对象：{path}")
    return value


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ExportValidationError(
                    f"JSONL 第 {line_number} 行格式错误：{path}"
                ) from exc
            if not isinstance(value, dict):
                raise ExportValidationError(
                    f"JSONL 第 {line_number} 行必须是对象：{path}"
                )
            yield value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_batch_root(review_data_root: Path, batch_id: str) -> Path:
    if not BATCH_ID_PATTERN.fullmatch(batch_id):
        raise ExportValidationError(f"批次号必须是正整数：{batch_id}")
    batch_root = (review_data_root / batch_id).resolve()
    required = (
        batch_root / "current" / "chunks",
        batch_root / "current" / "entity_nodes",
        batch_root / "state" / "reviews",
    )
    missing = [str(path) for path in required if not path.is_dir()]
    if missing:
        raise FileNotFoundError("批次目录不完整：" + "，".join(missing))
    return batch_root


def _clean_document_name(value: str) -> str:
    for character in "《》（）()_-. ":
        value = value.replace(character, "")
    return value.casefold()


def _entity_stem(path: Path) -> str:
    for suffix in (LABEL_SUFFIX, BASE_SUFFIX):
        if path.name.endswith(suffix):
            return path.name[: -len(suffix)]
    return path.stem


def _peek_document_id(path: Path) -> str:
    first = next(read_jsonl(path), None)
    return str((first or {}).get("document_id") or "")


def _load_chunk_documents(batch_root: Path) -> dict[str, dict[str, Any]]:
    chunks_root = batch_root / "current" / "chunks"
    paths = sorted(set(chunks_root.glob("*chunk.json")))
    if not paths:
        raise FileNotFoundError(f"未找到 Chunk 文件：{chunks_root}")
    documents: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = read_json(path)
        document_id = str(payload.get("doc_id") or payload.get("document_id") or "")
        if not document_id:
            raise ExportValidationError(f"Chunk 文件缺少 doc_id：{path}")
        if document_id in documents:
            raise ExportValidationError(f"重复文档 ID：{document_id}")
        title = str(payload.get("source_title") or document_id)
        chunks: dict[str, dict[str, Any]] = {}
        for chunk in payload.get("chunks", []):
            if not isinstance(chunk, dict):
                continue
            chunk_id = str(chunk.get("chunk_id") or "")
            if not chunk_id or chunk_id in chunks:
                raise ExportValidationError(
                    f"Chunk ID 缺失或重复：{document_id}/{chunk_id}"
                )
            chunks[chunk_id] = chunk
        chunks["__DOC__"] = {
            "chunk_id": "__DOC__",
            "text": title,
            "section_title": "文档标题",
            "section_path": ["文档", "标题"],
            "page_start": 1,
            "page_end": 1,
        }
        documents[document_id] = {
            "title": title,
            "chunks_path": path,
            "chunks": chunks,
        }
    return documents


def _match_document(
    path: Path, documents: dict[str, dict[str, Any]]
) -> str:
    document_id = _peek_document_id(path)
    if document_id in documents:
        return document_id
    clean_stem = _clean_document_name(_entity_stem(path))
    matches = [
        candidate
        for candidate, metadata in documents.items()
        if clean_stem in _clean_document_name(str(metadata["title"]))
        or _clean_document_name(str(metadata["title"])) in clean_stem
    ]
    if len(matches) != 1:
        raise ExportValidationError(f"实体文件无法唯一匹配文档：{path}")
    return matches[0]


def discover_document_sources(batch_root: Path) -> list[DocumentSource]:
    documents = _load_chunk_documents(batch_root)
    entity_root = batch_root / "current" / "entity_nodes"
    selected: dict[str, Path] = {}
    for path in sorted(entity_root.glob(f"*{BASE_SUFFIX}")):
        selected.setdefault(_match_document(path, documents), path)
    for path in sorted(entity_root.glob(f"*{LABEL_SUFFIX}")):
        selected[_match_document(path, documents)] = path
    if not selected:
        raise FileNotFoundError(f"未找到实体结果文件：{entity_root}")
    missing = sorted(set(documents) - set(selected))
    if missing:
        raise ExportValidationError(
            "以下文档没有实体结果文件：" + "，".join(missing)
        )

    sources: list[DocumentSource] = []
    for document_id in sorted(selected):
        entity_path = selected[document_id]
        base_path: Path | None = None
        if entity_path.name.endswith(LABEL_SUFFIX):
            candidate = entity_path.with_name(
                _entity_stem(entity_path) + BASE_SUFFIX
            )
            if candidate.is_file():
                base_path = candidate
        elif entity_path.name.endswith(BASE_SUFFIX):
            base_path = entity_path
        metadata = documents[document_id]
        sources.append(
            DocumentSource(
                document_id=document_id,
                title=str(metadata["title"]),
                chunks_path=Path(metadata["chunks_path"]),
                chunks=dict(metadata["chunks"]),
                entity_path=entity_path,
                base_path=base_path,
            )
        )
    return sources


def load_entity_types(batch_root: Path) -> set[str]:
    schemas = sorted((batch_root / "current").glob("graph_property_schema*.json"))
    if len(schemas) != 1:
        raise ExportValidationError(
            f"图谱 Schema 必须且只能有一个，当前找到 {len(schemas)} 个"
        )
    entities = read_json(schemas[0]).get("entities", {})
    if not isinstance(entities, dict):
        raise ExportValidationError("图谱 Schema 的 entities 必须是对象")
    return {
        str(key)
        for key, definition in entities.items()
        if isinstance(definition, dict)
        and definition.get("enabled", True)
        and key != "methods"
    }


def load_latest_entity_deltas(
    batch_root: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[Path]]:
    review_paths = sorted(
        (batch_root / "state" / "reviews").glob("*/*.review.json")
    )
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for path in review_paths:
        payload = read_json(path)
        document_id = str(payload.get("document_id") or path.parent.name)
        for record in payload.get("entities", []):
            if not isinstance(record, dict):
                raise ExportValidationError(f"复验 entities 中存在非对象：{path}")
            entity_id = str(record.get("entity_id") or "")
            if not document_id or not entity_id:
                raise ExportValidationError(f"复验记录缺少文档或实体 ID：{path}")
            key = (document_id, entity_id)
            try:
                version = int(record.get("review_version", 0))
            except (TypeError, ValueError) as exc:
                raise ExportValidationError(
                    f"复验版本不是整数：{document_id}/{entity_id}"
                ) from exc
            previous = latest.get(key)
            previous_version = int((previous or {}).get("review_version", -1))
            if version > previous_version:
                latest[key] = deepcopy(record)
            elif version == previous_version and previous != record:
                raise ExportValidationError(
                    f"同版本复验记录冲突：{document_id}/{entity_id}/v{version}"
                )
    return latest, review_paths


def _validated_patch(record: dict[str, Any]) -> dict[str, Any]:
    corrected = record.get("corrected_values") or {}
    if not isinstance(corrected, dict):
        raise ExportValidationError(
            f"corrected_values 必须是对象：{record.get('entity_id')}"
        )
    unknown = set(corrected) - EDITABLE_FIELDS - IGNORED_PATCH_FIELDS
    if unknown:
        raise ExportValidationError(
            f"复验修改包含未授权字段 {sorted(unknown)}：{record.get('entity_id')}"
        )
    return {key: deepcopy(value) for key, value in corrected.items() if key in EDITABLE_FIELDS}


def _normalize_chunk_id(document_id: str, chunk_id: str) -> str:
    prefix = f"{document_id}_"
    return chunk_id[len(prefix) :] if chunk_id.startswith(prefix) else chunk_id


def _compact_layout(value: str) -> tuple[str, list[int]]:
    compact: list[str] = []
    offsets: list[int] = []
    for index, character in enumerate(value):
        if character.isspace() or character in LAYOUT_IGNORED:
            continue
        compact.append(character)
        offsets.append(index)
    return "".join(compact), offsets


def locate_review_evidence(
    *,
    document_id: str,
    chunk: dict[str, Any],
    evidence_text: str,
) -> dict[str, Any]:
    source = str(chunk.get("text") or "")
    target = evidence_text.strip()
    if not source or not target:
        raise ExportValidationError(
            f"人工证据为空：{document_id}/{chunk.get('chunk_id')}"
        )
    start = source.find(target)
    if start >= 0:
        end = start + len(target)
        match_method = "exact"
        ambiguity_count = source.count(target)
    else:
        compact_source, offsets = _compact_layout(source)
        compact_target, _ = _compact_layout(target)
        compact_start = compact_source.find(compact_target)
        if compact_start < 0 or not compact_target:
            raise ExportValidationError(
                f"人工证据无法回链到 Chunk 原文：{document_id}/"
                f"{chunk.get('chunk_id')}，证据={target!r}"
            )
        compact_end = compact_start + len(compact_target)
        start = offsets[compact_start]
        end = offsets[compact_end - 1] + 1
        match_method = "layout_whitespace"
        ambiguity_count = compact_source.count(compact_target)
    raw_text = source[start:end]
    evidence_id = "REVIEW_EVD_" + hashlib.sha256(
        f"{document_id}|{chunk.get('chunk_id')}|{start}|{end}|{raw_text}".encode(
            "utf-8"
        )
    ).hexdigest()[:20].upper()
    return {
        "evidence_id": evidence_id,
        "document_id": document_id,
        "chunk_id": str(chunk.get("chunk_id") or ""),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "start": start,
        "end": end,
        "raw_text": raw_text,
        "normalized_text": target,
        "source": "physician_review",
        "match_method": match_method,
        "match_confidence": 1.0,
        "match_strength": "strong",
        "anchor_coverage": 1.0,
        "evidence_token_overlap": 1.0,
        "ambiguity_count": ambiguity_count,
    }


def _effective_type(row: dict[str, Any], patch: dict[str, Any]) -> str:
    return str(
        patch.get("entity_type")
        or row.get("entity_type")
        or row.get("final_entity_type")
        or row.get("proposed_entity_type")
        or row.get("fusion_entity_type")
        or row.get("teacher_candidate_type")
        or ""
    ).strip()


def _effective_name(row: dict[str, Any], patch: dict[str, Any]) -> str:
    return str(
        patch.get("name")
        or row.get("semantic_name")
        or row.get("name")
        or row.get("content")
        or row.get("raw_surface")
        or ""
    ).strip()


def _machine_status(row: dict[str, Any]) -> str:
    return str(row.get("status") or row.get("entity_status") or "").lower()


def _review_action(record: dict[str, Any] | None, machine_status: str) -> str:
    if record is None:
        return {
            "accepted": "retain",
            "review": "unresolved",
            "rejected": "exclude_machine",
        }.get(machine_status, "invalid")
    operation = str(record.get("review_operation") or "source").lower()
    decision = str(record.get("review_decision") or "pending").lower()
    if operation == "delete" or decision == "rejected":
        return "exclude_physician"
    if decision == "accepted":
        return "retain_physician"
    if operation in {"update", "create"}:
        return "unresolved"
    return {
        "accepted": "retain",
        "review": "unresolved",
        "rejected": "exclude_machine",
    }.get(machine_status, "invalid")


def _base_rows(path: Path | None) -> tuple[dict[str, dict[str, Any]], set[str]]:
    if path is None:
        return {}, set()
    rows: dict[str, dict[str, Any]] = {}
    fields: set[str] = set()
    for row in read_jsonl(path):
        entity_id = str(row.get("entity_id") or "")
        if not entity_id or entity_id in rows:
            raise ExportValidationError(f"Base 实体 ID 缺失或重复：{path}/{entity_id}")
        rows[entity_id] = row
        fields.update(row)
    return rows, fields


def _strip_review_fields(row: dict[str, Any]) -> None:
    row.pop("_review", None)
    for field in REVIEW_INTERNAL_FIELDS:
        row.pop(field, None)


def _materialize_node(
    *,
    source: dict[str, Any],
    base: dict[str, Any] | None,
    base_fields: set[str],
    review: dict[str, Any] | None,
    document: DocumentSource,
    valid_types: set[str],
    physician_created: bool = False,
    contract_version: str = "semantic_role_contract_v6",
) -> dict[str, Any]:
    patch = _validated_patch(review or {})
    if base is not None:
        node = deepcopy(base)
    elif base_fields:
        node = {
            key: deepcopy(source[key])
            for key in base_fields
            if key in source
        }
    else:
        node = deepcopy(source)

    entity_id = str(source.get("entity_id") or "")
    chunk_id = _normalize_chunk_id(
        document.document_id, str(source.get("chunk_id") or "")
    )
    if not entity_id or chunk_id not in document.chunks:
        raise ExportValidationError(
            f"最终实体缺少 ID 或引用未知 Chunk：{document.document_id}/"
            f"{entity_id}/{chunk_id}"
        )
    entity_type = _effective_type({**source, **node}, patch)
    if entity_type not in valid_types:
        raise ExportValidationError(
            f"最终实体类型不在 V3.6 契约中：{entity_id}/{entity_type}"
        )
    name = _effective_name({**source, **node}, patch)
    if not name:
        raise ExportValidationError(f"最终实体名称为空：{entity_id}")

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
            "status": "accepted",
            "entity_status": "accepted",
            "type_status": "accepted",
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
                "semantic_role_contract_version": contract_version,
                "review_reasons": ["physician_created_entity_requires_relation_schematic"],
            }
        )
    if str(node.get("semantic_role_contract_version") or "") != (
        "semantic_role_contract_v6"
    ):
        raise ExportValidationError(
            f"最终实体不满足关系构建的 Stage04 V6 契约：{entity_id}"
        )

    evidence_text = str(
        patch.get("evidence_text")
        or source.get("evidence_text")
        or node.get("evidence_text")
        or ""
    ).strip()
    if not evidence_text:
        raise ExportValidationError(f"最终实体证据为空：{entity_id}")
    node["evidence_text"] = evidence_text
    if "evidence_text" in patch or physician_created:
        span = locate_review_evidence(
            document_id=document.document_id,
            chunk=document.chunks[chunk_id],
            evidence_text=evidence_text,
        )
        node["evidence_span"] = span
        node["evidence_spans"] = [span]
        node["evidence_ids"] = [span["evidence_id"]]
        node["evidence_status"] = "located"
    _strip_review_fields(node)
    return node


def _change_entry(
    *,
    document_id: str,
    source: dict[str, Any] | None,
    output: dict[str, Any] | None,
    review: dict[str, Any],
    action: str,
) -> dict[str, Any]:
    def summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "name": row.get("semantic_name") or row.get("name"),
            "entity_type": (
                row.get("entity_type")
                or row.get("final_entity_type")
                or row.get("proposed_entity_type")
            ),
            "evidence_text": row.get("evidence_text"),
            "status": row.get("status") or row.get("entity_status"),
        }

    return {
        "document_id": document_id,
        "entity_id": str(review.get("entity_id") or ""),
        "action": action,
        "review_version": int(review.get("review_version", 0)),
        "review_updated_at": review.get("review_updated_at"),
        "before": summary(source),
        "after": summary(output),
    }


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _relative_input(path: Path, batch_root: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(batch_root).as_posix(),
        "sha256": sha256_file(path),
    }


def _publish_directory(staged: Path, target: Path) -> None:
    if not target.name or target.parent == target:
        raise ExportValidationError(f"拒绝发布到危险路径：{target}")
    backup = target.with_name(f".{target.name}.{uuid.uuid4().hex}.bak")
    moved_old = False
    try:
        if target.exists():
            os.replace(target, backup)
            moved_old = True
        os.replace(staged, target)
    except Exception:
        if moved_old and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def build_final_export(
    *,
    batch_root: Path,
    output_dir: Path,
    check_only: bool = False,
) -> dict[str, Any]:
    batch_root = batch_root.resolve()
    output_dir = output_dir.resolve()
    protected_roots = (
        batch_root / "current",
        batch_root / "state" / "reviews",
        batch_root / "state" / "results",
    )
    if any(
        output_dir == root or output_dir.is_relative_to(root)
        for root in protected_roots
    ):
        raise ExportValidationError(f"输出目录不得覆盖源数据或复验状态：{output_dir}")
    sources = discover_document_sources(batch_root)
    valid_types = load_entity_types(batch_root)
    deltas, review_paths = load_latest_entity_deltas(batch_root)
    deltas_by_document: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for (document_id, entity_id), record in deltas.items():
        deltas_by_document[document_id][entity_id] = record

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staged = output_dir.with_name(f".{output_dir.name}.{uuid.uuid4().hex}.tmp")
    staged.mkdir()
    global_counts: Counter[str] = Counter()
    changes: list[dict[str, Any]] = []
    unresolved: list[dict[str, str]] = []
    used_delta_keys: set[tuple[str, str]] = set()
    document_summaries: list[dict[str, Any]] = []
    source_paths: set[Path] = set(review_paths)
    source_paths.update(
        (batch_root / "current").glob("graph_property_schema*.json")
    )
    try:
        for document in sources:
            source_paths.update({document.entity_path, document.chunks_path})
            base_rows, base_fields = _base_rows(document.base_path)
            if document.base_path is not None:
                source_paths.add(document.base_path)
            output_name = _entity_stem(document.entity_path) + BASE_SUFFIX
            output_path = staged / output_name
            label_output_name = _entity_stem(document.entity_path) + LABEL_SUFFIX
            label_output_path = staged / label_output_name
            document_counts: Counter[str] = Counter()
            output_occurrences: set[str] = set()
            seen_source_ids: set[str] = set()
            contract_versions: Counter[str] = Counter()

            with (
                output_path.open("w", encoding="utf-8", newline="\n") as handle,
                label_output_path.open(
                    "w", encoding="utf-8", newline="\n"
                ) as label_handle,
            ):
                for source_row in read_jsonl(document.entity_path):
                    entity_id = str(source_row.get("entity_id") or "")
                    source_document_id = str(
                        source_row.get("document_id") or document.document_id
                    )
                    if (
                        not entity_id
                        or source_document_id != document.document_id
                        or entity_id in seen_source_ids
                    ):
                        raise ExportValidationError(
                            f"源实体 ID 缺失/重复或跨文档：{document.entity_path}/"
                            f"{entity_id}"
                        )
                    seen_source_ids.add(entity_id)
                    machine_status = _machine_status(source_row)
                    if machine_status not in {"accepted", "review", "rejected"}:
                        raise ExportValidationError(
                            f"未知机器状态：{document.document_id}/{entity_id}/"
                            f"{machine_status}"
                        )
                    global_counts[f"machine_{machine_status}"] += 1
                    document_counts[f"machine_{machine_status}"] += 1
                    version = str(
                        source_row.get("semantic_role_contract_version") or ""
                    )
                    if version:
                        contract_versions[version] += 1
                    review = deltas_by_document[document.document_id].get(entity_id)
                    if review is not None:
                        used_delta_keys.add((document.document_id, entity_id))
                    action = _review_action(review, machine_status)
                    if action == "unresolved":
                        unresolved.append(
                            {
                                "document_id": document.document_id,
                                "entity_id": entity_id,
                                "machine_status": machine_status,
                            }
                        )
                        continue
                    if action.startswith("exclude"):
                        document_counts[action] += 1
                        global_counts[action] += 1
                        if review is not None:
                            changes.append(
                                _change_entry(
                                    document_id=document.document_id,
                                    source=source_row,
                                    output=None,
                                    review=review,
                                    action="delete",
                                )
                            )
                        continue
                    if action == "invalid":
                        raise ExportValidationError(
                            f"无法解释实体发布状态：{document.document_id}/{entity_id}"
                        )

                    base = base_rows.get(entity_id)
                    if machine_status == "accepted" and base is None and document.base_path:
                        raise ExportValidationError(
                            f"机器 accepted 实体缺少 Base Node："
                            f"{document.document_id}/{entity_id}"
                        )
                    node = _materialize_node(
                        source=source_row,
                        base=base,
                        base_fields=base_fields,
                        review=review,
                        document=document,
                        valid_types=valid_types,
                    )
                    label_node = _materialize_node(
                        source=source_row,
                        base=None,
                        base_fields=set(),
                        review=review,
                        document=document,
                        valid_types=valid_types,
                    )
                    occurrence_id = str(node["occurrence_id"])
                    if occurrence_id in output_occurrences:
                        raise ExportValidationError(
                            f"最终 occurrence_id 重复：{document.document_id}/"
                            f"{occurrence_id}"
                        )
                    output_occurrences.add(occurrence_id)
                    handle.write(
                        json.dumps(node, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                    label_handle.write(
                        json.dumps(
                            label_node,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    document_counts["retained"] += 1
                    global_counts["retained"] += 1
                    if review is not None:
                        patch = _validated_patch(review)
                        change_action = "update" if patch else "accept"
                        document_counts[f"physician_{change_action}"] += 1
                        global_counts[f"physician_{change_action}"] += 1
                        changes.append(
                            _change_entry(
                                document_id=document.document_id,
                                source=source_row,
                                output=node,
                                review=review,
                                action=change_action,
                            )
                        )

                default_contract = (
                    contract_versions.most_common(1)[0][0]
                    if contract_versions
                    else "semantic_role_contract_v6"
                )
                for entity_id, review in sorted(
                    deltas_by_document[document.document_id].items()
                ):
                    key = (document.document_id, entity_id)
                    if key in used_delta_keys:
                        continue
                    operation = str(review.get("review_operation") or "source").lower()
                    decision = str(review.get("review_decision") or "pending").lower()
                    used_delta_keys.add(key)
                    if operation == "delete" or decision == "rejected":
                        document_counts["excluded_physician"] += 1
                        global_counts["excluded_physician"] += 1
                        continue
                    if operation != "create":
                        raise ExportValidationError(
                            f"复验修改无法匹配源实体：{document.document_id}/{entity_id}"
                        )
                    if decision != "accepted":
                        unresolved.append(
                            {
                                "document_id": document.document_id,
                                "entity_id": entity_id,
                                "machine_status": "physician_created",
                            }
                        )
                        continue
                    node = _materialize_node(
                        source=review,
                        base=None,
                        base_fields=base_fields,
                        review=review,
                        document=document,
                        valid_types=valid_types,
                        physician_created=True,
                        contract_version=default_contract,
                    )
                    occurrence_id = str(node["occurrence_id"])
                    if occurrence_id in output_occurrences:
                        raise ExportValidationError(
                            f"新增实体 occurrence_id 重复：{document.document_id}/"
                            f"{occurrence_id}"
                        )
                    output_occurrences.add(occurrence_id)
                    handle.write(
                        json.dumps(node, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                    label_handle.write(
                        json.dumps(node, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                    document_counts["retained"] += 1
                    document_counts["physician_create"] += 1
                    global_counts["retained"] += 1
                    global_counts["physician_create"] += 1
                    changes.append(
                        _change_entry(
                            document_id=document.document_id,
                            source=None,
                            output=node,
                            review=review,
                            action="create",
                        )
                    )
                handle.flush()
                os.fsync(handle.fileno())
                label_handle.flush()
                os.fsync(label_handle.fileno())
            document_summaries.append(
                {
                    "document_id": document.document_id,
                    "title": document.title,
                    "output_file": output_name,
                    "label_output_file": label_output_name,
                    "counts": dict(sorted(document_counts.items())),
                }
            )

        unmatched = sorted(set(deltas) - used_delta_keys)
        if unmatched:
            preview = "，".join(f"{doc}/{entity}" for doc, entity in unmatched[:10])
            raise ExportValidationError(f"复验记录引用未知文档：{preview}")
        if unresolved:
            preview = "，".join(
                f"{item['document_id']}/{item['entity_id']}"
                for item in unresolved[:20]
            )
            raise ExportValidationError(
                f"仍有 {len(unresolved)} 个实体未完成复验，拒绝生成最终 F1：{preview}"
            )

        _write_jsonl(staged / "node_entity_F1.change_log.jsonl", changes)
        output_files = sorted(
            [
                *staged.glob(f"*{BASE_SUFFIX}"),
                *staged.glob(f"*{LABEL_SUFFIX}"),
            ]
        )
        manifest = {
            "artifact": "node_entity_F1",
            "contract_version": "node_entity_F1_v1",
            "batch_id": batch_root.name,
            "generated_at": utc_now(),
            "publish_status": "final",
            "invariants": {
                "accepted_only": True,
                "unresolved_count": 0,
                "source_state_mutated": False,
            },
            "counts": dict(sorted(global_counts.items())),
            "documents": document_summaries,
            "inputs": [
                _relative_input(path, batch_root)
                for path in sorted(source_paths, key=lambda item: str(item))
            ],
            "outputs": [
                {"path": path.name, "sha256": sha256_file(path)}
                for path in output_files
            ],
        }
        _write_json(staged / "node_entity_F1.manifest.json", manifest)
        if check_only:
            shutil.rmtree(staged)
        else:
            _publish_directory(staged, output_dir)
        return manifest
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        raise


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "将机器实体结果与医师复验增量合并，发布最终 node_entity_F1。"
        )
    )
    parser.add_argument("batch", help="复验批次号，例如 1、2、3")
    parser.add_argument(
        "--review-data-root",
        type=Path,
        default=Path(
            os.getenv("REVIEW_DATA_ROOT", str(project_root / "data" / "review"))
        ),
        help="复验数据根目录，默认使用 pro/data/review",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "发布目录；默认写入该批次的 "
            "state/exports/node_entity_F1"
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="执行完整合并与校验，但不发布文件",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        batch_root = validate_batch_root(
            args.review_data_root.resolve(), str(args.batch)
        )
        output_dir = (
            args.output_dir.resolve()
            if args.output_dir
            else batch_root / "state" / "exports" / DEFAULT_OUTPUT_DIR_NAME
        )
        manifest = build_final_export(
            batch_root=batch_root,
            output_dir=output_dir,
            check_only=bool(args.check_only),
        )
    except (ExportValidationError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    counts = manifest["counts"]
    verb = "校验通过" if args.check_only else "发布完成"
    print(
        f"批次 {args.batch} {verb}：最终实体 {counts.get('retained', 0)} 条，"
        f"人工修改 {counts.get('physician_update', 0)} 条，"
        f"人工新增 {counts.get('physician_create', 0)} 条。"
    )
    if not args.check_only:
        print(f"输出：{output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
