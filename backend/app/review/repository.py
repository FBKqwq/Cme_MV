from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
import zipfile
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException

from .config import (
    EXPORT_ROOT,
    INBOX_ROOT,
    PROJECT_ROOT,
    RESULT_ROOT,
    SCHEMA_PATH,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            value = line.strip()
            if not value:
                continue
            try:
                records.append(json.loads(value))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name} 第 {line_number} 行不是合法 JSON") from exc
    return records


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ReviewRepository:
    """Immutable source data plus one human-readable review JSON per PDF."""

    ENTITY_LABELS_ZH = {
        "diseases": "疾病",
        "sub_diseases": "疾病亚型",
        "symptoms": "症状与体征",
        "tests": "检查",
        "treatments": "治疗原则",
        "plans": "治疗方案",
        "methods": "实施方法",
        "etiologies": "病因",
        "pathogeneses": "发病机制",
    }
    RELATION_LABELS_ZH = {
        "has_sub_disease": "包含亚型",
        "manifests_as": "表现为",
        "requires_test": "需要检查",
        "follows_treatment": "接受治疗",
        "implements_by": "实施方案",
        "causes": "导致",
        "explained_by": "机制解释",
    }

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        inbox_root: Path | None = None,
        result_root: Path | None = None,
        export_root: Path | None = None,
        schema_path: Path | None = None,
    ) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self.inbox_root = inbox_root or INBOX_ROOT
        self.result_root = result_root or RESULT_ROOT
        self.export_root = export_root or EXPORT_ROOT
        self.schema_path = schema_path or SCHEMA_PATH
        self.result_root.mkdir(parents=True, exist_ok=True)
        self.export_root.mkdir(parents=True, exist_ok=True)
        self._load_source()
        self._validate_source()
        self._sync_input_hash()
        self._load_or_initialize_results()

    def _manifest_path(self) -> Path:
        return self.inbox_root / "chunks"

    def _resolve_manifest_file(self, key: str, *, required: bool = True) -> Path | None:
        return None
    def _load_source(self) -> None:
        chunks_dir = self.inbox_root / "chunks"
        nodes_dir = self.inbox_root / "entity_nodes"

        if not chunks_dir.exists():
            raise ValueError(f"未找到chunks目录：{chunks_dir}")

        chunk_files = sorted(chunks_dir.glob("*_chunk.json"))
        if not chunk_files:
            chunk_files = sorted(chunks_dir.glob("*chunk.json"))
        if not chunk_files:
            raise ValueError(f"未找到chunk文件：{chunks_dir}")

        self.manifest = {"document_id": "multi_doc", "title": "多文档复验", "schema_version": "3.6"}
        self.source_paths: dict[str, Path] = {}
        self.chunk_sources: dict[str, dict] = {}
        self.pdf_by_document_id: dict[str, Path] = {}

        doc_count = 0
        self.chunks = []
        for cf in chunk_files:
            payload = read_json(cf)
            chunks = payload.get("chunks", [])
            if not isinstance(chunks, list):
                continue
            source_title = payload.get("source_title", cf.stem)
            doc_id = payload.get("doc_id", f"DOC_{doc_count:03d}")
            for ch in chunks:
                orig = str(ch.get("chunk_id", f"CH{len(self.chunks)+1:04d}"))
                ch["chunk_id"] = f"{doc_id}_{orig}"
                ch["_source_title"] = source_title
                ch["_doc_id"] = doc_id
                ch["_original_chunk_id"] = orig
                self.chunks.append(ch)
            self.chunk_sources[doc_id] = {"title": source_title, "count": len(chunks)}
            doc_count += 1

        self._index_source_pdfs()

        self.chunk_by_id = {str(c["chunk_id"]): c for c in self.chunks}
        if not self.chunks:
            raise ValueError("没有加载到任何chunk数据")

        self.entities = []
        if nodes_dir.exists():
            # Map cleaned document stems to chunk doc_ids
            def _clean_stem(s):
                for ch in ("\u300a", "\u300b", "\uff08", "\uff09", "(", ")", "_", "-", ".", " "):
                    s = s.replace(ch, "")
                return s

            stem_to_doc = {}
            for cf in chunk_files:
                payload = read_json(cf)
                raw_stem = cf.stem.replace("_chunk.json", "").replace("__chunk.json", "").replace("_chunk", "").replace("__chunk", "")
                clean = _clean_stem(raw_stem)
                doc_id = payload.get("doc_id", "")
                if doc_id and clean:
                    stem_to_doc[clean] = doc_id

            for ef in sorted(nodes_dir.glob("*.entity_nodes.base.jsonl")):
                raw_stem = ef.stem.replace(".entity_nodes.base", "")
                clean_ef = _clean_stem(raw_stem)
                matched_doc = None
                for clean, did in stem_to_doc.items():
                    if clean in clean_ef or clean_ef in clean:
                        matched_doc = did
                        break
                if not matched_doc:
                    matched_doc = list(self.chunk_sources.keys())[0]

                for rec in read_jsonl(ef):
                    rec["_doc_id"] = matched_doc
                    cid = str(rec.get("chunk_id", ""))
                    if cid:
                        prefixed = f"{matched_doc}_{cid}"
                        if prefixed in self.chunk_by_id:
                            rec["chunk_id"] = prefixed
                    self.entities.append(rec)

        base_dir = self.inbox_root / "entity_base"
        if not self.entities and base_dir.exists():
            for ef in sorted(base_dir.glob("*.entity_base.jsonl")):
                for rec in read_jsonl(ef):
                    document_id = str(rec.get("document_id", ""))
                    rec["_doc_id"] = (
                        document_id
                        if document_id in self.chunk_sources
                        else next(iter(self.chunk_sources))
                    )
                    self.entities.append(rec)

        self.entity_by_id = {str(e["entity_id"]): e for e in self.entities}

        self.relationships = []
        self.relationship_by_id = {}

        self.canonical_entities = []
        for e in self.entities:
            eid = str(e.get("entity_id", ""))
            if eid:
                self.canonical_entities.append({
                    "entity_id": eid,
                    "entity_type": e.get("entity_type", ""),
                    "name": e.get("name", ""),
                    "raw_entity_ids": [eid],
                    "source_chunk_ids": [str(e.get("chunk_id", ""))],
                    "status": e.get("status", "accepted"),
                })
        self.canonical_by_id = {str(c["entity_id"]): c for c in self.canonical_entities}
        self.raw_to_canonical = {}
        for can in self.canonical_entities:
            cid = str(can["entity_id"])
            for rid in can.get("raw_entity_ids", []):
                if rid:
                    self.raw_to_canonical[str(rid)] = cid

        if not self.schema_path.exists():
            raise ValueError(f"未找到图谱 schema：{self.schema_path}")
        self.schema = read_json(self.schema_path)

        entity_definitions = self.schema.get("entities", {})
        self.entity_types = [
            {
                "value": key,
                "label": definition.get("label_zh")
                or self.ENTITY_LABELS_ZH.get(key)
                or definition.get("label")
                or key,
                "contract_label": definition.get("label") or key,
            }
            for key, definition in entity_definitions.items()
            if definition.get("enabled", True) and key != "methods"
        ]
        self.entity_contract_labels = {i["value"]: i["contract_label"] for i in self.entity_types}
        self.relation_definitions = {
            k: v for k, v in self.schema.get("relationships", {}).items()
            if v.get("enabled", True)
        }
        self.relation_types = [
            {
                "value": k,
                "label": v.get("label_zh") or self.RELATION_LABELS_ZH.get(k) or v.get("label") or k,
                "source_type": v.get("source_entity_type"),
                "target_type": v.get("target_entity_type"),
            }
            for k, v in self.relation_definitions.items()
        ]

        # Derive synthetic relationships from entity co-occurrence per chunk.
        self._derive_relationships()

    @staticmethod
    def _normalized_document_name(value: str) -> str:
        ignored = "《》（）()_-. "
        normalized = value.casefold()
        for character in ignored:
            normalized = normalized.replace(character, "")
        return normalized

    def _index_source_pdfs(self) -> None:
        raw_pdf_dir = self.inbox_root / "raw_pdf"
        if not raw_pdf_dir.exists():
            return

        pdf_files = sorted(raw_pdf_dir.glob("*.pdf"))
        for document_id, source in self.chunk_sources.items():
            title = str(source.get("title", ""))
            exact = [path for path in pdf_files if path.stem == title]
            candidates = exact or [
                path
                for path in pdf_files
                if self._normalized_document_name(path.stem)
                == self._normalized_document_name(title)
            ]
            if len(candidates) == 1:
                self.pdf_by_document_id[document_id] = candidates[0]
                source["pdf_available"] = True
            elif len(candidates) > 1:
                raise ValueError(
                    f"文档 {document_id} 匹配到多个 PDF，请统一文件名：{title}"
                )
            else:
                source["pdf_available"] = False

    def _derive_relationships(self) -> None:
        """Derive synthetic relationships from entity type pairs per chunk."""
        if self.relationships:
            return  # already have explicit relationships
        if not self.entities:
            return

        # Map schema contract labels to actual entity_type values
        schema_to_type = {v.lower(): k for k, v in self.entity_contract_labels.items()}
        # Build reverse map: entity_type -> schema contract_label
        type_to_schema = self.entity_contract_labels  # already maps type_value -> contract_label

        # Collect entities by chunk
        by_chunk: dict[tuple[str, str], list[dict]] = {}
        for e in self.entities:
            cid = str(e.get("chunk_id", ""))
            group_key = (str(e.get("_doc_id", "")), cid)
            if group_key not in by_chunk:
                by_chunk[group_key] = []
            by_chunk[group_key].append(e)

        relationships: list[dict] = []
        seen_pairs: set[tuple[str, str, str]] = set()  # (rel_type, src_id, tgt_id)

        for (document_id, cid), chunk_ents in by_chunk.items():
            if not chunk_ents:
                continue
            # Group by entity_type
            by_type: dict[str, list[dict]] = {}
            for e in chunk_ents:
                et = e.get("entity_type", "")
                if et not in by_type:
                    by_type[et] = []
                by_type[et].append(e)

            # Extended type pairs for cases without sub_diseases intermediary
            extended_pairs = {
                ("diseases", "sub_diseases"): "has_sub_disease",
                ("diseases", "symptoms"): "manifests_as",
                ("diseases", "tests"): "requires_test",
                ("diseases", "treatments"): "follows_treatment",
                ("diseases", "pathogeneses"): "explained_by",
                ("sub_diseases", "symptoms"): "manifests_as",
                ("sub_diseases", "tests"): "requires_test",
                ("sub_diseases", "treatments"): "follows_treatment",
                ("sub_diseases", "pathogeneses"): "explained_by",
                ("treatments", "plans"): "implements_by",
                ("sub_diseases", "methods"): "implements_by",
                ("etiologies", "sub_diseases"): "causes",
                ("etiologies", "pathogeneses"): "causes",
                ("etiologies", "symptoms"): "causes",
                ("pathogeneses", "symptoms"): "explained_by",
            }

            # Use extended pairs (direct type pairs + schema pairs)
            all_pairs = list(extended_pairs.items())

            for (src_type_val, tgt_type_val), rel_type in all_pairs:
                if src_type_val not in by_type or tgt_type_val not in by_type:
                    continue

                # Pair source entities with target entities
                src_ents = by_type[src_type_val]
                tgt_ents = by_type[tgt_type_val]

                for src in src_ents:
                    for tgt in tgt_ents:
                        if src["entity_id"] == tgt["entity_id"]:
                            continue
                        key = (rel_type, str(src["entity_id"]), str(tgt["entity_id"]))
                        if key in seen_pairs:
                            continue
                        seen_pairs.add(key)

                        rel_id = f"SYNTH_REL_{uuid.uuid4().hex[:12].upper()}"
                        relationships.append({
                            "relation_id": rel_id,
                            "_doc_id": document_id,
                            "chunk_id": cid,
                            "source_chunk_id": cid,
                            "target_chunk_id": cid,
                            "start_entity_id": str(src["entity_id"]),
                            "relation_type": rel_type,
                            "end_entity_id": str(tgt["entity_id"]),
                            "evidence_text": tgt.get("evidence_text", src.get("evidence_text", "")),
                            "status": "pending",
                            "source": "synthetic_derived",
                            "conflicts": [],
                            "_review": {
                                "operation": "source",
                                "deleted": False,
                                "added": False,
                                "modified": False,
                            },
                        })

        self.relationships = relationships
        self.relationship_by_id = {str(r["relation_id"]): r for r in relationships}

    @staticmethod
    def _safe_result_name(value: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
        return cleaned or "untitled"

    def _result_path(self, document_id: str) -> Path:
        source = self.chunk_sources[document_id]
        pdf = self.pdf_by_document_id.get(document_id)
        stem = pdf.stem if pdf else str(source.get("title") or document_id)
        return self.result_root / f"{self._safe_result_name(stem)}.review.json"

    def _document_id_for_chunk(self, chunk_id: str) -> str:
        chunk = self.chunk_by_id.get(chunk_id)
        if not chunk:
            raise HTTPException(status_code=404, detail="未找到该 chunk")
        return str(chunk["_doc_id"])

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    @staticmethod
    def _source_result_entity(entity: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(entity)
        result.update(
            {
                "review_flag": "pending",
                "review_operation": "source",
                "review_scope": "current",
                "corrected_values": {},
                "review_version": 0,
                "review_updated_at": None,
            }
        )
        return result

    def _new_document_result(self, document_id: str) -> dict[str, Any]:
        entity_records = [
            self._source_result_entity(entity)
            for entity in self.entities
            if str(entity.get("_doc_id", "")) == document_id
        ]
        relationship_records = [
            self._source_result_entity(relation)
            for relation in self.relationships
            if str(relation.get("_doc_id", "")) == document_id
        ]
        source = self.chunk_sources[document_id]
        pdf = self.pdf_by_document_id.get(document_id)
        return {
            "document_id": document_id,
            "source_title": source.get("title"),
            "source_pdf": pdf.name if pdf else None,
            "schema_version": self.schema.get("schema_version"),
            "input_hash": self.input_hash,
            "version": 0,
            "updated_at": None,
            "entities": entity_records,
            "canonical_entities": [],
            "relationships": relationship_records,
            "chunk_reviews": {},
            "audit_events": [],
        }

    def _load_or_initialize_results(self) -> None:
        self.results: dict[str, dict[str, Any]] = {}
        for document_id in self.chunk_sources:
            path = self._result_path(document_id)
            if path.exists():
                result = read_json(path)
                if result.get("input_hash") != self.input_hash:
                    changed = (
                        any(
                            entity.get("review_operation") != "source"
                            for entity in result.get("entities", [])
                        )
                        or any(
                            relation.get("review_operation") != "source"
                            for relation in result.get("relationships", [])
                        )
                        or bool(result.get("chunk_reviews"))
                    )
                    if changed:
                        raise ValueError(
                            f"源文件已变化，但 {path.name} 中仍有旧修订。"
                            "请先备份或迁移结果集。"
                        )
                    result = self._new_document_result(document_id)
            else:
                result = self._new_document_result(document_id)
            self.results[document_id] = result
            self._atomic_write_json(path, result)

    def _save_result(self, document_id: str) -> None:
        self._atomic_write_json(self._result_path(document_id), self.results[document_id])

    def _validate_source(self) -> None:
        issues: list[str] = []
        fatal_issues: list[str] = []
        if len(self.chunk_by_id) != len(self.chunks):
            issues.append("chunk_id 存在缺失或重复")
        if len(self.entity_by_id) != len(self.entities):
            issues.append("entity_id 存在缺失或重复")
        if self.relationships and len(self.relationship_by_id) != len(self.relationships):
            issues.append("relation_id 存在缺失或重复")
        allowed_entity_types = set(self.entity_contract_labels)
        for entity in self.entities:
            cid = str(entity.get("chunk_id", ""))
            if cid and cid not in self.chunk_by_id and cid != "__DOC__":
                fatal_issues.append(
                    f"实体 {entity.get('entity_id')} 引用了未知 chunk {cid}"
                )
            if entity.get("entity_type") not in allowed_entity_types:
                issues.append(f"实体 {entity.get('entity_id')} 类型不在 V3.6 契约中")
        if fatal_issues:
            raise ValueError("；".join(fatal_issues[:20]))
        if issues:
            preview = "；".join(issues[:20])
            suffix = f"（另有 {len(issues) - 20} 项）" if len(issues) > 20 else ""
            import logging
            logging.warning(f"输入数据校验预警：{preview}{suffix}")

    def _sync_input_hash(self) -> None:
        chunks_dir = self.inbox_root / "chunks"
        checksums: dict[str, str] = {}
        if chunks_dir.exists():
            chunk_files = sorted(chunks_dir.glob("*_chunk.json"))
            if not chunk_files:
                chunk_files = sorted(chunks_dir.glob("*chunk.json"))
            for cf in chunk_files:
                checksums[f"chunks/{cf.name}"] = file_sha256(cf)
            nodes_dir = self.inbox_root / "entity_nodes"
            if nodes_dir.exists():
                for ef in sorted(nodes_dir.glob("*.entity_nodes.base.jsonl")):
                    checksums[f"entity_nodes/{ef.name}"] = file_sha256(ef)
        checksums[self.schema_path.name] = file_sha256(self.schema_path)
        current_hash = hashlib.sha256(
            json.dumps(checksums, sort_keys=True).encode("utf-8")
        ).hexdigest()
        self.input_hash = current_hash
        self.checksums = checksums

    def version(self) -> int:
        return max(
            (int(result.get("version", 0)) for result in self.results.values()),
            default=0,
        )

    def _assert_version(self, base_version: int) -> None:
        current = self.version()
        if base_version != current:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "VERSION_CONFLICT",
                    "message": "数据已在另一标签页更新，请刷新后重试。",
                    "current_version": current,
                },
            )

    def _overrides(self, kind: str) -> dict[str, dict[str, Any]]:
        collection = {
            "entity": "entities",
            "canonical": "canonical_entities",
            "relationship": "relationships",
        }[kind]
        rows: dict[str, dict[str, Any]] = {}
        id_key = "relation_id" if kind == "relationship" else "entity_id"
        for result in self.results.values():
            for record in result.get(collection, []):
                operation = record.get("review_operation", "source")
                if operation == "source":
                    continue
                corrected = deepcopy(record.get("corrected_values", {}))
                if operation == "create":
                    payload = {
                        key: value
                        for key, value in record.items()
                        if key not in {
                            "review_flag", "review_operation", "review_scope", "corrected_values",
                            "review_version", "review_updated_at",
                        }
                    }
                    payload.update(corrected)
                else:
                    payload = corrected
                record_id = str(record[id_key])
                rows[record_id] = {
                    "kind": kind,
                    "record_id": record_id,
                    "chunk_id": str(record.get("chunk_id", "")),
                    "operation": operation,
                    "scope": record.get("review_scope", "current"),
                    "payload_json": json.dumps(payload, ensure_ascii=False),
                    "before_json": json.dumps(record, ensure_ascii=False),
                    "version": int(record.get("review_version", 0)),
                    "updated_at": record.get("review_updated_at"),
                }
        return rows

    @staticmethod
    def _apply_override(record: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
        projected = deepcopy(record)
        payload = {
            key: value
            for key, value in json.loads(row["payload_json"]).items()
            if not key.startswith("__restore_")
        }
        projected.update(payload)
        projected["_review"] = {
            "operation": row["operation"],
            "scope": row["scope"],
            "version": row["version"],
            "updated_at": row["updated_at"],
            "deleted": row["operation"] == "delete",
            "added": row["operation"] == "create",
            "modified": row["operation"] in {"update", "delete"},
        }
        return projected

    def projected_entities(self) -> list[dict[str, Any]]:
        overrides = self._overrides("entity")
        projected: list[dict[str, Any]] = []
        for record in self.entities:
            record_id = str(record["entity_id"])
            row = overrides.get(record_id)
            if row:
                projected.append(self._apply_override(record, row))
            else:
                item = deepcopy(record)
                item["_review"] = {
                    "operation": "source",
                    "deleted": False,
                    "added": False,
                    "modified": False,
                }
                projected.append(item)
        for record_id, row in overrides.items():
            if record_id not in self.entity_by_id and row["operation"] == "create":
                projected.append(self._apply_override({}, row))
        return projected

    def projected_canonical_entities(self) -> list[dict[str, Any]]:
        overrides = self._overrides("canonical")
        projected: list[dict[str, Any]] = []
        for record in self.canonical_entities:
            record_id = str(record["entity_id"])
            row = overrides.get(record_id)
            item = self._apply_override(record, row) if row else deepcopy(record)
            item.setdefault(
                "_review",
                {
                    "operation": "source",
                    "deleted": False,
                    "added": False,
                    "modified": False,
                },
            )
            projected.append(item)
        for record_id, row in overrides.items():
            if record_id not in self.canonical_by_id and row["operation"] == "create":
                projected.append(self._apply_override({}, row))
        return projected

    def projected_relationships(self) -> list[dict[str, Any]]:
        overrides = self._overrides("relationship")
        projected: list[dict[str, Any]] = []
        for record in self.relationships:
            record_id = str(record["relation_id"])
            row = overrides.get(record_id)
            if row:
                projected.append(self._apply_override(record, row))
            else:
                item = deepcopy(record)
                item["_review"] = {
                    "operation": "source",
                    "deleted": False,
                    "added": False,
                    "modified": False,
                }
                projected.append(item)
        for record_id, row in overrides.items():
            if record_id not in self.relationship_by_id and row["operation"] == "create":
                projected.append(self._apply_override({}, row))
        return projected

    @staticmethod
    def _relation_chunk_ids(relation: dict[str, Any]) -> set[str]:
        chunk_ids: set[str] = set()
        for key in ("chunk_id", "source_chunk_id", "target_chunk_id"):
            value = relation.get(key)
            if value:
                chunk_ids.add(str(value))
        for value in relation.get("source_chunk_ids", []) or []:
            if value:
                chunk_ids.add(str(value))
        for collection_key in ("evidence_mentions", "evidence_spans"):
            for evidence in relation.get(collection_key, []) or []:
                for key in ("chunk_id", "source_chunk_id", "target_chunk_id"):
                    value = evidence.get(key)
                    if value:
                        chunk_ids.add(str(value))
        return chunk_ids

    def _changed_canonical_ids(self) -> set[str]:
        changed: set[str] = set()
        for record_id, row in self._overrides("entity").items():
            payload = json.loads(row["payload_json"])
            if row["operation"] == "delete" or {"name", "entity_type"} & payload.keys():
                canonical_id = self.raw_to_canonical.get(record_id)
                if canonical_id:
                    changed.add(canonical_id)
        return changed

    def _deleted_canonical_ids(self) -> set[str]:
        deleted: set[str] = set()
        for record_id, row in self._overrides("entity").items():
            if row["operation"] != "delete":
                continue
            canonical_id = self.raw_to_canonical.get(record_id)
            if canonical_id:
                deleted.add(canonical_id)
        return deleted

    def _entity_options(self) -> list[dict[str, str]]:
        options: list[dict[str, str]] = []
        seen: set[str] = set()
        for canonical in self.projected_canonical_entities():
            entity_id = str(canonical.get("entity_id", ""))
            if not entity_id or canonical["_review"].get("deleted") or entity_id in seen:
                continue
            seen.add(entity_id)
            options.append(
                {
                    "id": entity_id,
                    "name": str(canonical.get("name") or entity_id),
                    "entity_type": str(canonical.get("entity_type") or ""),
                    "canonical": "true",
                }
            )
        for entity in self.projected_entities():
            review_id = entity.get("review_canonical_id")
            if not review_id or review_id in seen or entity["_review"].get("deleted"):
                continue
            seen.add(review_id)
            options.append(
                {
                    "id": str(review_id),
                    "name": str(entity.get("name") or review_id),
                    "entity_type": str(entity.get("entity_type") or ""),
                    "canonical": "true",
                }
            )
        return options

    def _relation_conflicts(
        self, relations: Iterable[dict[str, Any]]
    ) -> dict[str, list[dict[str, str]]]:
        options = {item["id"]: item for item in self._entity_options()}
        changed_canonical_ids = self._changed_canonical_ids()
        deleted_canonical_ids = self._deleted_canonical_ids()
        result: dict[str, list[dict[str, str]]] = {}
        for relation in relations:
            if relation["_review"].get("deleted"):
                result[str(relation["relation_id"])] = []
                continue
            relation_id = str(relation["relation_id"])
            conflicts: list[dict[str, str]] = []
            start_id = str(relation.get("start_entity_id", ""))
            end_id = str(relation.get("end_entity_id", ""))
            if (
                start_id not in options
                or end_id not in options
                or start_id in deleted_canonical_ids
                or end_id in deleted_canonical_ids
            ):
                conflicts.append(
                    {
                        "code": "missing_endpoint",
                        "message": "实体已删除或端点不存在，请重新绑定关系。",
                    }
                )
            definition = self.relation_definitions.get(str(relation.get("relation_type")))
            if not definition:
                conflicts.append(
                    {
                        "code": "invalid_relation_type",
                        "message": "关系类型不在 V3.6 契约中。",
                    }
                )
            elif start_id in options and end_id in options:
                source_label = self.entity_contract_labels.get(
                    options[start_id]["entity_type"], options[start_id]["entity_type"]
                )
                target_label = self.entity_contract_labels.get(
                    options[end_id]["entity_type"], options[end_id]["entity_type"]
                )
                if (
                    source_label != definition.get("source_entity_type")
                    or target_label != definition.get("target_entity_type")
                ):
                    conflicts.append(
                        {
                            "code": "invalid_relation_frame",
                            "message": "当前实体类型与该关系的源/目标约束不匹配。",
                        }
                    )
            if (
                (start_id in changed_canonical_ids or end_id in changed_canonical_ids)
                and start_id not in deleted_canonical_ids
                and end_id not in deleted_canonical_ids
                and relation["_review"].get("operation") == "source"
            ):
                conflicts.append(
                    {
                        "code": "needs_rebind",
                        "message": "端点实体已被修改，请确认并重新绑定该关系。",
                    }
                )
            result[relation_id] = conflicts
        return result

    def _chunk_review_rows(self) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for result in self.results.values():
            rows.update(result.get("chunk_reviews", {}))
        return rows

    def chunk_summaries(self, pending_only: bool = False) -> list[dict[str, Any]]:
        entities_by_chunk: dict[str, int] = defaultdict(int)
        for entity in self.projected_entities():
            if not entity["_review"].get("deleted"):
                entities_by_chunk[str(entity.get("chunk_id", ""))] += 1
        relations = self.projected_relationships()
        conflicts = self._relation_conflicts(relations)
        relation_counts: dict[str, int] = defaultdict(int)
        issue_counts: dict[str, int] = defaultdict(int)
        for relation in relations:
            if relation["_review"].get("deleted"):
                continue
            relation_id = str(relation["relation_id"])
            for chunk_id in self._relation_chunk_ids(relation):
                relation_counts[chunk_id] += 1
                issue_counts[chunk_id] += len(conflicts.get(relation_id, []))
        reviews = self._chunk_review_rows()
        result: list[dict[str, Any]] = []
        for index, chunk in enumerate(self.chunks):
            chunk_id = str(chunk["chunk_id"])
            review = reviews.get(chunk_id)
            has_override = bool(
                review and review["has_changes"]
            ) or self._chunk_has_override(chunk_id)
            status = review["status"] if review else "pending"
            if status == "approved" and has_override:
                display_status = "modified"
            else:
                display_status = status
            summary = {
                "chunk_id": chunk_id,
                "index": index + 1,
                "section_title": chunk.get("section_title")
                or "未命名章节",
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "text_preview": str(chunk.get("text", ""))[:90],
                "entity_count": entities_by_chunk[chunk_id],
                "relation_count": relation_counts[chunk_id],
                "issue_count": issue_counts[chunk_id],
                "status": display_status,
                "approved": status == "approved",
                "has_changes": has_override,
                "_source_title": chunk.get("_source_title", ""),
                "_doc_id": chunk.get("_doc_id", ""),
            }
            if not pending_only or status != "approved" or issue_counts[chunk_id] > 0:
                result.append(summary)
        return result

    def _chunk_has_override(self, chunk_id: str) -> bool:
        return any(
            row["chunk_id"] == chunk_id
            for kind in ("entity", "relationship")
            for row in self._overrides(kind).values()
        )

    def task(self) -> dict[str, Any]:
        summaries = self.chunk_summaries()
        approved = sum(1 for item in summaries if item["approved"])
        issues = sum(item["issue_count"] for item in summaries)
        documents = [
            {
                "document_id": document_id,
                "title": source.get("title", ""),
                "chunk_count": source.get("count", 0),
                "pdf_available": document_id in self.pdf_by_document_id,
            }
            for document_id, source in self.chunk_sources.items()
        ]
        return {
            "document": {
                "title": "多文档复验",
                "schema_version": self.manifest.get("schema_version")
                or self.schema.get("schema_version"),
                "total_chunks": len(self.chunks),
                "total_pages": None,
                "pdf_available": bool(self.pdf_by_document_id),
            },
            "documents": documents,
            "progress": {
                "approved": approved,
                "total": len(summaries),
                "percent": round(approved / len(summaries) * 100) if summaries else 0,
                "issues": issues,
                "modified": sum(1 for item in summaries if item["has_changes"]),
            },
            "input_hash": self.input_hash,
            "checksums": self.checksums,
            "version": self.version(),
        }

    def source_pdf(self, document_id: str) -> Path:
        if document_id not in self.chunk_sources:
            raise HTTPException(status_code=404, detail="未找到该文档")
        path = self.pdf_by_document_id.get(document_id)
        if path is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "PDF_UNAVAILABLE",
                    "message": "该文档未配置同名 PDF 文件。",
                },
            )
        return path

    def chunk_detail(self, chunk_id: str) -> dict[str, Any]:
        chunk = self.chunk_by_id.get(chunk_id)
        if not chunk:
            raise HTTPException(status_code=404, detail="未找到该 chunk")
        entities = [
            item
            for item in self.projected_entities()
            if str(item.get("chunk_id")) == chunk_id
        ]
        for entity in entities:
            entity["canonical_entity_id"] = entity.get(
                "review_canonical_id"
            ) or self.raw_to_canonical.get(str(entity.get("entity_id")))
        relations = [
            item
            for item in self.projected_relationships()
            if chunk_id in self._relation_chunk_ids(item)
        ]
        conflicts = self._relation_conflicts(relations)
        for relation in relations:
            relation["conflicts"] = conflicts.get(str(relation["relation_id"]), [])
        review = self._chunk_review_rows().get(chunk_id)
        options = self._entity_options()
        option_ids = {
            str(relation.get("start_entity_id"))
            for relation in relations
        } | {
            str(relation.get("end_entity_id"))
            for relation in relations
        }
        option_ids |= {
            str(entity.get("canonical_entity_id"))
            for entity in entities
            if entity.get("canonical_entity_id")
        }
        return {
            "chunk": deepcopy(chunk),
            "entities": entities,
            "relationships": relations,
            "entity_options": [
                option for option in options if option["id"] in option_ids
            ],
            "entity_types": self.entity_types,
            "relation_types": self.relation_types,
            "review": {
                "status": review["status"] if review else "pending",
                "has_changes": bool(review["has_changes"]) if review else False,
                "issue_count": sum(len(value) for value in conflicts.values()),
            },
            "version": self.version(),
        }

    def _write_override(
        self,
        *,
        kind: str,
        record_id: str,
        chunk_id: str,
        operation: str,
        scope: str,
        payload: dict[str, Any],
        before: dict[str, Any] | None,
        base_version: int,
        action: str,
    ) -> int:
        self._assert_version(base_version)
        timestamp = utc_now()
        version = self.version() + 1
        document_id = self._document_id_for_chunk(chunk_id)
        result = self.results[document_id]
        collection = {
            "entity": "entities",
            "canonical": "canonical_entities",
            "relationship": "relationships",
        }[kind]
        id_key = "relation_id" if kind == "relationship" else "entity_id"
        record = next(
            (
                item
                for item in result[collection]
                if str(item.get(id_key)) == record_id
            ),
            None,
        )
        previous_operation = record.get("review_operation") if record else None
        if record is None:
            record = deepcopy(payload)
            record["corrected_values"] = {}
            result[collection].append(record)
        elif operation == "create":
            record.update(deepcopy(payload))
        else:
            public_payload = {
                key: value for key, value in payload.items()
                if not key.startswith("__restore_")
            }
            record.setdefault("corrected_values", {}).update(public_payload)
            restore_metadata = {
                key.removeprefix("__restore_"): value
                for key, value in payload.items()
                if key.startswith("__restore_")
            }
            if restore_metadata:
                record["restore_metadata"] = restore_metadata

        # An entity/relationship created during review remains an addition even
        # when it is edited later, otherwise it would disappear after reload.
        stored_operation = (
            "create"
            if previous_operation == "create" and operation == "update"
            else operation
        )

        if stored_operation == "delete":
            flag = "deleted"
        elif stored_operation == "create":
            flag = "added"
        elif payload.get("status") == "accepted" and len(payload) == 1:
            flag = "approved"
        else:
            flag = "modified"
        record.update(
            {
                "review_flag": flag,
                "review_operation": stored_operation,
                "review_scope": scope,
                "review_version": version,
                "review_updated_at": timestamp,
            }
        )
        result["chunk_reviews"][chunk_id] = {
            "chunk_id": chunk_id,
            "status": "pending",
            "has_changes": True,
            "version": version,
            "updated_at": timestamp,
        }
        result["audit_events"].append(
            {
                "sequence": sum(
                    len(item.get("audit_events", []))
                    for item in self.results.values()
                )
                + 1,
                "kind": kind,
                "record_id": record_id,
                "chunk_id": chunk_id,
                "action": action,
                "before": deepcopy(before),
                "after": deepcopy(payload),
                "version": version,
                "created_at": timestamp,
            }
        )
        result["version"] = version
        result["updated_at"] = timestamp
        self._save_result(document_id)
        return version

    def create_entity(self, payload: dict[str, Any]) -> dict[str, Any]:
        chunk_id = payload["chunk_id"]
        if chunk_id not in self.chunk_by_id:
            raise HTTPException(status_code=404, detail="未找到该 chunk")
        if payload["entity_type"] not in self.entity_contract_labels:
            raise HTTPException(status_code=422, detail="实体类型不在 V3.6 契约中")
        entity_id = f"REVIEW_ENTITY_{uuid.uuid4().hex[:12].upper()}"
        canonical_id = f"REVIEW_CANON_{uuid.uuid4().hex[:12].upper()}"
        record = {
            "entity_id": entity_id,
            "document_id": self.manifest.get("document_id", "review_document"),
            "chunk_id": chunk_id,
            "section_title": self.chunk_by_id[chunk_id].get("section_title"),
            "source_title": self.manifest.get("title"),
            "entity_type": payload["entity_type"],
            "name": payload["name"].strip(),
            "evidence_text": payload["evidence_text"].strip(),
            "status": "pending",
            "entity_status": "review_added",
            "review_canonical_id": canonical_id,
        }
        version = self._write_override(
            kind="entity",
            record_id=entity_id,
            chunk_id=chunk_id,
            operation="create",
            scope="current",
            payload=record,
            before=None,
            base_version=payload["base_version"],
            action="create",
        )
        self._write_canonical_in_same_version(
            canonical_id, record, chunk_id, version
        )
        return {"entity_id": entity_id, "version": version}

    def _write_canonical_in_same_version(
        self, canonical_id: str, entity: dict[str, Any], chunk_id: str, version: int
    ) -> None:
        timestamp = utc_now()
        canonical = {
            "entity_id": canonical_id,
            "entity_type": entity["entity_type"],
            "name": entity["name"],
            "raw_entity_ids": [entity["entity_id"]],
            "source_chunk_ids": [chunk_id],
            "status": "review_added",
        }
        document_id = self._document_id_for_chunk(chunk_id)
        canonical.update(
            {
                "chunk_id": chunk_id,
                "review_flag": "added",
                "review_operation": "create",
                "review_scope": "current",
                "corrected_values": {},
                "review_version": version,
                "review_updated_at": timestamp,
            }
        )
        result = self.results[document_id]
        result["canonical_entities"] = [
            item
            for item in result["canonical_entities"]
            if str(item.get("entity_id")) != canonical_id
        ]
        result["canonical_entities"].append(canonical)
        self._save_result(document_id)

    def update_entity(self, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        source = self.entity_by_id.get(entity_id)
        existing = next(
            (
                item
                for item in self.projected_entities()
                if str(item.get("entity_id")) == entity_id
            ),
            None,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="未找到该实体")
        chunk_id = payload["chunk_id"]
        patch = {
            key: value
            for key, value in payload.items()
            if key in {"name", "entity_type", "evidence_text", "status"}
            and value is not None
        }
        if "entity_type" in patch and patch["entity_type"] not in self.entity_contract_labels:
            raise HTTPException(status_code=422, detail="实体类型不在 V3.6 契约中")
        scope = payload.get("scope", "current")
        target_ids = [entity_id]
        canonical_id = self.raw_to_canonical.get(entity_id)
        if scope == "all" and canonical_id:
            canonical = self.canonical_by_id.get(canonical_id, {})
            target_ids = [
                str(value)
                for value in canonical.get("raw_entity_ids", [])
                if value in self.entity_by_id
            ] or [entity_id]
        if scope == "current" and {"name", "entity_type"} & patch.keys():
            patch["review_canonical_id"] = existing.get(
                "review_canonical_id"
            ) or f"REVIEW_CANON_{uuid.uuid4().hex[:12].upper()}"

        base_version = payload["base_version"]
        version = base_version
        for target_id in target_ids:
            target_before = self.entity_by_id.get(target_id) or existing
            target_chunk = str(target_before.get("chunk_id") or chunk_id)
            version = self._write_override(
                kind="entity",
                record_id=target_id,
                chunk_id=target_chunk,
                operation="update",
                scope=scope,
                payload=patch,
                before=source or target_before,
                base_version=version,
                action="update",
            )
        if scope == "current" and patch.get("review_canonical_id"):
            projected = deepcopy(existing)
            projected.update(patch)
            self._write_canonical_in_same_version(
                patch["review_canonical_id"], projected, chunk_id, version
            )
        return {"entity_id": entity_id, "updated_mentions": len(target_ids), "version": version}

    def delete_entity(
        self, entity_id: str, *, chunk_id: str, base_version: int
    ) -> dict[str, Any]:
        existing = next(
            (
                item
                for item in self.projected_entities()
                if str(item.get("entity_id")) == entity_id
            ),
            None,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="未找到该实体")
        prior = self._overrides("entity").get(entity_id)
        delete_payload: dict[str, Any] = {}
        if prior:
            delete_payload = json.loads(prior["payload_json"])
            delete_payload["__restore_operation"] = prior["operation"]
            delete_payload["__restore_scope"] = prior["scope"]
        version = self._write_override(
            kind="entity",
            record_id=entity_id,
            chunk_id=chunk_id,
            operation="delete",
            scope="current",
            payload=delete_payload,
            before=self.entity_by_id.get(entity_id) or existing,
            base_version=base_version,
            action="delete",
        )
        return {"entity_id": entity_id, "version": version}

    def restore_entity(
        self, entity_id: str, *, chunk_id: str, base_version: int
    ) -> dict[str, Any]:
        version = self._restore_record(
            kind="entity",
            record_id=entity_id,
            chunk_id=chunk_id,
            base_version=base_version,
        )
        return {"entity_id": entity_id, "version": version}

    def _restore_record(
        self,
        *,
        kind: str,
        record_id: str,
        chunk_id: str,
        base_version: int,
    ) -> int:
        self._assert_version(base_version)
        document_id = self._document_id_for_chunk(chunk_id)
        result = self.results[document_id]
        collection = "entities" if kind == "entity" else "relationships"
        id_key = "entity_id" if kind == "entity" else "relation_id"
        record = next(
            (
                item for item in result[collection]
                if str(item.get(id_key)) == record_id
            ),
            None,
        )
        if not record or record.get("review_operation") != "delete":
            label = "实体" if kind == "entity" else "关系"
            raise HTTPException(status_code=404, detail=f"该{label}没有可恢复的删除记录")

        timestamp = utc_now()
        version = self.version() + 1
        metadata = record.pop("restore_metadata", {})
        previous_operation = metadata.get("operation")
        if previous_operation:
            record["review_operation"] = previous_operation
            record["review_scope"] = metadata.get("scope", "current")
            record["review_flag"] = (
                "added" if previous_operation == "create" else "modified"
            )
        else:
            record["review_operation"] = "source"
            record["review_scope"] = "current"
            record["review_flag"] = "pending"
            record["corrected_values"] = {}
        record["review_version"] = version
        record["review_updated_at"] = timestamp
        result["chunk_reviews"][chunk_id] = {
            "chunk_id": chunk_id,
            "status": "pending",
            "has_changes": self._chunk_has_override(chunk_id),
            "version": version,
            "updated_at": timestamp,
        }
        result["audit_events"].append(
            {
                "sequence": sum(
                    len(item.get("audit_events", []))
                    for item in self.results.values()
                )
                + 1,
                "kind": kind,
                "record_id": record_id,
                "chunk_id": chunk_id,
                "action": "restore",
                "before": {"review_flag": "deleted"},
                "after": None,
                "version": version,
                "created_at": timestamp,
            }
        )
        result["version"] = version
        result["updated_at"] = timestamp
        self._save_result(document_id)
        return version

    def create_relationship(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload["relation_type"] not in self.relation_definitions:
            raise HTTPException(status_code=422, detail="关系类型不在 V3.6 契约中")
        relation_id = f"REVIEW_REL_{uuid.uuid4().hex[:12].upper()}"
        record = {
            "relation_id": relation_id,
            "chunk_id": payload["chunk_id"],
            "source_chunk_id": payload["chunk_id"],
            "target_chunk_id": payload["chunk_id"],
            "start_entity_id": payload["start_entity_id"],
            "relation_type": payload["relation_type"],
            "end_entity_id": payload["end_entity_id"],
            "evidence_text": payload["evidence_text"].strip(),
            "status": "pending",
        }
        version = self._write_override(
            kind="relationship",
            record_id=relation_id,
            chunk_id=payload["chunk_id"],
            operation="create",
            scope="current",
            payload=record,
            before=None,
            base_version=payload["base_version"],
            action="create",
        )
        return {"relation_id": relation_id, "version": version}

    def update_relationship(
        self, relation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        existing = next(
            (
                item
                for item in self.projected_relationships()
                if str(item.get("relation_id")) == relation_id
            ),
            None,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="未找到该关系")
        patch = {
            key: value
            for key, value in payload.items()
            if key
            in {
                "start_entity_id",
                "relation_type",
                "end_entity_id",
                "evidence_text",
                "status",
            }
            and value is not None
        }
        if "relation_type" in patch and patch["relation_type"] not in self.relation_definitions:
            raise HTTPException(status_code=422, detail="关系类型不在 V3.6 契约中")
        version = self._write_override(
            kind="relationship",
            record_id=relation_id,
            chunk_id=payload["chunk_id"],
            operation="update",
            scope="current",
            payload=patch,
            before=self.relationship_by_id.get(relation_id) or existing,
            base_version=payload["base_version"],
            action="update",
        )
        return {"relation_id": relation_id, "version": version}

    def delete_relationship(
        self, relation_id: str, *, chunk_id: str, base_version: int
    ) -> dict[str, Any]:
        existing = next(
            (
                item
                for item in self.projected_relationships()
                if str(item.get("relation_id")) == relation_id
            ),
            None,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="未找到该关系")
        prior = self._overrides("relationship").get(relation_id)
        delete_payload: dict[str, Any] = {}
        if prior:
            delete_payload = json.loads(prior["payload_json"])
            delete_payload["__restore_operation"] = prior["operation"]
            delete_payload["__restore_scope"] = prior["scope"]
        version = self._write_override(
            kind="relationship",
            record_id=relation_id,
            chunk_id=chunk_id,
            operation="delete",
            scope="current",
            payload=delete_payload,
            before=self.relationship_by_id.get(relation_id) or existing,
            base_version=base_version,
            action="delete",
        )
        return {"relation_id": relation_id, "version": version}

    def restore_relationship(
        self, relation_id: str, *, chunk_id: str, base_version: int
    ) -> dict[str, Any]:
        version = self._restore_record(
            kind="relationship",
            record_id=relation_id,
            chunk_id=chunk_id,
            base_version=base_version,
        )
        return {"relation_id": relation_id, "version": version}

    def approve_chunk(self, chunk_id: str, base_version: int) -> dict[str, Any]:
        self._assert_version(base_version)
        detail = self.chunk_detail(chunk_id)
        blocking = [
            conflict
            for relation in detail["relationships"]
            if not relation["_review"].get("deleted")
            for conflict in relation.get("conflicts", [])
        ]
        if blocking:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "BLOCKING_CONFLICTS",
                    "message": "当前 Chunk 仍有关系冲突，请先处理。",
                    "conflicts": blocking,
                },
            )
        timestamp = utc_now()
        version = self.version() + 1
        document_id = self._document_id_for_chunk(chunk_id)
        result = self.results[document_id]
        result["chunk_reviews"][chunk_id] = {
            "chunk_id": chunk_id,
            "status": "approved",
            "has_changes": self._chunk_has_override(chunk_id),
            "version": version,
            "updated_at": timestamp,
        }
        result["audit_events"].append(
            {
                "sequence": sum(
                    len(item.get("audit_events", []))
                    for item in self.results.values()
                )
                + 1,
                "kind": "chunk",
                "record_id": chunk_id,
                "chunk_id": chunk_id,
                "action": "approve",
                "before": None,
                "after": {"status": "approved"},
                "version": version,
                "created_at": timestamp,
            }
        )
        result["version"] = version
        result["updated_at"] = timestamp
        self._save_result(document_id)
        return {"chunk_id": chunk_id, "status": "approved", "version": version}

    def _audit_log(self) -> list[dict[str, Any]]:
        rows = [
            deepcopy(event)
            for result in self.results.values()
            for event in result.get("audit_events", [])
        ]
        return sorted(rows, key=lambda item: int(item.get("sequence", 0)))

    def import_review(self, zip_path: Path) -> dict[str, Any]:
        """Import per-PDF review JSON files from a review export."""
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail=f"未找到导入文件：{zip_path}")

        with zipfile.ZipFile(zip_path, "r") as bundle:
            names = bundle.namelist()
            if "review_manifest.json" not in names:
                raise HTTPException(status_code=422, detail="无效的复验导出包：缺少 review_manifest.json")
            result_names = [
                name for name in names
                if name.startswith("results/") and name.endswith(".review.json")
            ]
            if not result_names:
                raise HTTPException(
                    status_code=422,
                    detail="导出包中缺少 results/*.review.json，无法导入。",
                )

            manifest = json.loads(bundle.read("review_manifest.json").decode("utf-8"))
            imported: dict[str, dict[str, Any]] = {}
            for name in result_names:
                payload = json.loads(bundle.read(name).decode("utf-8"))
                document_id = str(payload.get("document_id", ""))
                if document_id not in self.chunk_sources:
                    raise HTTPException(
                        status_code=422,
                        detail=f"结果集引用了未知文档：{document_id}",
                    )
                if payload.get("input_hash") != self.input_hash:
                    raise HTTPException(
                        status_code=422,
                        detail=f"结果集与当前源数据不匹配：{document_id}",
                    )
                imported[document_id] = payload
            if set(imported) != set(self.chunk_sources):
                raise HTTPException(
                    status_code=422,
                    detail="导入包没有覆盖当前任务的全部 PDF。",
                )
            self.results = imported
            for document_id in imported:
                self._save_result(document_id)

        return {
            "version": manifest.get("review_version", 0),
            "final": manifest.get("final", False),
            "exported_at": manifest.get("exported_at", ""),
            "counts": manifest.get("counts", {}),
        }

    def build_export(self, *, final: bool) -> Path:
        task = self.task()
        if final:
            unapproved = task["progress"]["total"] - task["progress"]["approved"]
            if task["progress"]["issues"] or unapproved:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "REVIEW_INCOMPLETE",
                        "message": f"尚有 {unapproved} 个 Chunk 未通过、{task['progress']['issues']} 个冲突。",
                    },
                )
        suffix = "final" if final else "draft"
        export_path = self.export_root / f"reviewed_{suffix}.zip"
        entities = self.projected_entities()
        canonicals = self.projected_canonical_entities()
        relationships = self.projected_relationships()
        manifest = {
            "source_manifest": self.manifest,
            "schema_version": self.schema.get("schema_version"),
            "input_hash": self.input_hash,
            "review_version": self.version(),
            "final": final,
            "exported_at": utc_now(),
            "counts": {
                "entities": len(entities),
                "canonical_entities": len(canonicals),
                "relationships": len(relationships),
            },
        }

        def jsonl_bytes(records: Iterable[dict[str, Any]]) -> bytes:
            return (
                "\n".join(
                    json.dumps(record, ensure_ascii=False) for record in records
                )
                + "\n"
            ).encode("utf-8")

        with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for document_id in self.chunk_sources:
                path = self._result_path(document_id)
                bundle.writestr(f"results/{path.name}", path.read_bytes())
            bundle.writestr("reviewed_entities.jsonl", jsonl_bytes(entities))
            bundle.writestr(
                "reviewed_canonical_entities.jsonl", jsonl_bytes(canonicals)
            )
            bundle.writestr(
                "reviewed_relationships.jsonl", jsonl_bytes(relationships)
            )
            bundle.writestr(
                "review_manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            )
            bundle.writestr(
                "change_log.json",
                json.dumps(self._audit_log(), ensure_ascii=False, indent=2).encode("utf-8"),
            )
            bundle.writestr(
                "review_checklist.json",
                json.dumps(
                    self.chunk_summaries(), ensure_ascii=False, indent=2
                ).encode("utf-8"),
            )
        return export_path
