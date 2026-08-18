cd"""Export untouched machine-review entities for one review batch.

Usage:
    python export_pending_physician_review.py 1

The default output is written to:
    data/review/<batch>/state/exports/pending_physician_review_entities.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any


BATCH_ID_PATTERN = re.compile(r"^[1-9]\d*$")
DEFAULT_REVIEW_DATA_ROOT = Path(
    os.getenv(
        "REVIEW_DATA_ROOT",
        str(Path(__file__).resolve().parents[1] / "data" / "review"),
    )
).resolve()
DEFAULT_OUTPUT_NAME = "pending_physician_review_entities.json"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return value


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"JSONL 第 {line_number} 行格式错误：{path}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(
                    f"JSONL 第 {line_number} 行必须是对象：{path}"
                )
            yield value


def validate_batch_root(review_data_root: Path, batch_id: str) -> Path:
    if not BATCH_ID_PATTERN.fullmatch(batch_id):
        raise ValueError(f"批次号必须是正整数：{batch_id}")

    batch_root = review_data_root / batch_id
    required_paths = (
        batch_root / "current" / "entity_nodes",
        batch_root / "state" / "reviews",
    )
    missing = [str(path) for path in required_paths if not path.is_dir()]
    if missing:
        raise FileNotFoundError("批次目录不完整：" + "，".join(missing))
    return batch_root


def source_entity_paths(batch_root: Path) -> list[Path]:
    entity_root = batch_root / "current" / "entity_nodes"
    paths = sorted(entity_root.glob("*.entity_label_result.jsonl"))
    if not paths:
        paths = sorted(entity_root.glob("*.entity_nodes.base.jsonl"))
    if not paths:
        raise FileNotFoundError(f"未找到实体结果文件：{entity_root}")
    return paths


def review_record_was_touched(record: dict[str, Any]) -> bool:
    try:
        version = int(record.get("review_version", 0))
    except (TypeError, ValueError):
        version = 0
    operation = str(record.get("review_operation") or "source")
    decision = str(record.get("review_decision") or "pending")
    flag = str(record.get("review_flag") or "pending")
    return (
        version > 0
        or operation != "source"
        or decision != "pending"
        or flag not in {"", "pending"}
    )


def load_touched_entity_keys(batch_root: Path) -> set[tuple[str, str]]:
    """Return entities that have ever appeared in a human operation.

    Current delta records cover ordinary saves. Audit events are also checked so
    an entity modified and later restored is still treated as operated.
    """

    touched: set[tuple[str, str]] = set()
    delta_root = batch_root / "state" / "reviews"
    for path in sorted(delta_root.glob("*/*.review.json")):
        payload = read_json(path)
        pdf_id = str(payload.get("document_id") or path.parent.name)

        for record in payload.get("entities", []):
            if not isinstance(record, dict) or not review_record_was_touched(record):
                continue
            entity_id = str(record.get("entity_id") or "")
            if entity_id:
                touched.add((pdf_id, entity_id))

        for event in payload.get("audit_events", []):
            if not isinstance(event, dict) or str(event.get("kind")) != "entity":
                continue
            entity_id = str(event.get("record_id") or "")
            if entity_id:
                touched.add((pdf_id, entity_id))
    return touched


def normalize_chunk_id(pdf_id: str, chunk_id: str) -> str:
    prefix = f"{pdf_id}_"
    return chunk_id if chunk_id.startswith(prefix) else f"{prefix}{chunk_id}"


def effective_entity_type(entity: dict[str, Any]) -> str:
    return str(
        entity.get("entity_type")
        or entity.get("proposed_entity_type")
        or entity.get("fusion_entity_type")
        or entity.get("teacher_candidate_type")
        or ""
    )


def original_evidence(entity: dict[str, Any]) -> str:
    evidence = entity.get("evidence_text")
    if evidence:
        return str(evidence)

    for field in ("source_evidence_span", "evidence_span"):
        span = entity.get(field)
        if not isinstance(span, dict):
            continue
        for key in ("text", "raw_text", "normalized_text"):
            if span.get(key):
                return str(span[key])
    return ""


def collect_pending_entities(batch_root: Path) -> list[dict[str, Any]]:
    touched = load_touched_entity_keys(batch_root)
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    seen: set[tuple[str, str, str]] = set()

    for path in source_entity_paths(batch_root):
        for entity in read_jsonl(path):
            if str(entity.get("status") or "") != "review":
                continue

            pdf_id = str(entity.get("document_id") or "")
            raw_chunk_id = str(entity.get("chunk_id") or "")
            entity_id = str(entity.get("entity_id") or "")
            if not pdf_id or not raw_chunk_id or not entity_id:
                raise ValueError(
                    f"待复验实体缺少 document_id、chunk_id 或 entity_id：{path}"
                )
            if (pdf_id, entity_id) in touched:
                continue

            chunk_id = normalize_chunk_id(pdf_id, raw_chunk_id)
            identity = (pdf_id, chunk_id, entity_id)
            if identity in seen:
                continue
            seen.add(identity)

            item = {
                "item": entity_id,
                "object": {
                    "entity_name": str(
                        entity.get("name")
                        or entity.get("semantic_name")
                        or entity.get("raw_surface")
                        or ""
                    ),
                    "entity_type": effective_entity_type(entity),
                    "evidence": original_evidence(entity),
                },
            }
            grouped.setdefault(pdf_id, {}).setdefault(chunk_id, []).append(item)

    result: list[dict[str, Any]] = []
    for pdf_id, chunks in grouped.items():
        result.append(
            {
                "pdf_id": pdf_id,
                "chunks": [
                    {
                        "chunk_id": chunk_id,
                        "items": items,
                    }
                    for chunk_id, items in chunks.items()
                ],
            }
        )
    return result


def count_items(payload: list[dict[str, Any]]) -> int:
    return sum(
        len(chunk["items"])
        for document in payload
        for chunk in document["chunks"]
    )


def write_json_atomic(path: Path, payload: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计并导出一个复验批次中机器标为 review 且人工未操作的实体。"
    )
    parser.add_argument("batch", help="复验批次号，例如 1 或 2")
    parser.add_argument(
        "--review-data-root",
        type=Path,
        default=DEFAULT_REVIEW_DATA_ROOT,
        help="复验数据根目录，默认使用 pro/data/review",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "输出 JSON 路径。默认写入该批次的 "
            "state/exports/pending_physician_review_entities.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review_data_root = args.review_data_root.resolve()
    batch_root = validate_batch_root(review_data_root, args.batch)
    output = (
        args.output.resolve()
        if args.output
        else batch_root / "state" / "exports" / DEFAULT_OUTPUT_NAME
    )

    payload = collect_pending_entities(batch_root)
    write_json_atomic(output, payload)
    print(
        f"批次 {args.batch}：共 {count_items(payload)} 条待医师复验实体，"
        f"涉及 {len(payload)} 个 PDF。"
    )
    print(f"输出：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
