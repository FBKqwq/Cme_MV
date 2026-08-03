from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from build_physician_review_doc import (
    BORDER,
    CALLOUT,
    CAUTION,
    CAUTION_FILL,
    CONTENT_WIDTH_DXA,
    DARK_BLUE,
    INK,
    LIGHT_BLUE,
    LIGHT_GRAY,
    MUTED,
    add_one_cell_callout,
    add_text_paragraph,
    configure_page,
    configure_styles,
    format_cell_text,
    mark_repeat_header,
    set_cell_shading,
    set_paragraph,
    set_run_font,
    set_table_borders,
    set_table_geometry,
)


REVIEW_ROOT = Path(
    r"C:\Users\zhurunjie\Desktop\CmePlatform\pro\data\review"
)
OUTPUT_PATH = (
    REVIEW_ROOT
    / "state"
    / "exports"
    / "医师复验清单_机器待复验且人工未操作_排除Blau_2026-07-31.docx"
)
EXCLUDED_DOCUMENT_ID = "DOC_91bfb25e36f4"
EXPECTED_UNTOUCHED = 32

TYPE_LABELS = {
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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def sanitize_display(value: Any, *, limit: int | None = None) -> str:
    text = "" if value is None else str(value)
    pieces: list[str] = []
    for char in text:
        code = ord(char)
        if 0xE000 <= code <= 0xF8FF:
            pieces.append(f"[缺失字形U+{code:04X}]")
        elif code < 32 and char not in "\t\n\r":
            pieces.append(" ")
        else:
            pieces.append(char)
    text = "".join(pieces)
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + "…"
    return text


def entity_doc_id(entity: dict[str, Any]) -> str:
    return str(entity.get("document_id") or entity.get("_doc_id") or "")


def source_chunk_id(entity: dict[str, Any]) -> str:
    doc_id = entity_doc_id(entity)
    chunk_id = str(entity.get("chunk_id") or "")
    prefix = f"{doc_id}_"
    return chunk_id[len(prefix) :] if chunk_id.startswith(prefix) else chunk_id


def load_chunks() -> tuple[
    dict[str, dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    list[str],
]:
    documents: dict[str, dict[str, Any]] = {}
    chunks: dict[tuple[str, str], dict[str, Any]] = {}
    document_order: list[str] = []
    for path in sorted((REVIEW_ROOT / "current" / "chunks").glob("*chunk.json")):
        payload = read_json(path)
        doc_id = str(payload["doc_id"])
        documents[doc_id] = {
            "document_id": doc_id,
            "title": str(payload.get("source_title") or path.stem),
            "chunk_count": len(payload.get("chunks", [])),
        }
        document_order.append(doc_id)
        for index, chunk in enumerate(payload.get("chunks", []), start=1):
            item = dict(chunk)
            item["_index"] = index
            chunks[(doc_id, str(chunk["chunk_id"]))] = item
    return documents, chunks, document_order


def load_touched_entity_ids() -> set[str]:
    touched: set[str] = set()
    delta_root = REVIEW_ROOT / "state" / "reviews"
    for path in delta_root.glob("*/*.review.json"):
        payload = read_json(path)
        for entity in payload.get("entities", []):
            version = int(entity.get("review_version", 0))
            operation = str(entity.get("review_operation") or "source")
            decision = str(entity.get("review_decision") or "pending")
            if version > 0 or operation != "source" or decision != "pending":
                touched.add(str(entity.get("entity_id")))
    return touched


def load_source_entities() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    node_root = REVIEW_ROOT / "current" / "entity_nodes"
    paths = sorted(node_root.glob("*.entity_label_result.jsonl"))
    if not paths:
        paths = sorted(node_root.glob("*.entity_nodes.base.jsonl"))
    for path in paths:
        rows.extend(read_jsonl(path))
    return rows


def excerpt_around(entity: dict[str, Any], chunk: dict[str, Any] | None) -> str:
    if not chunk:
        return sanitize_display(entity.get("evidence_text"), limit=360)
    raw_text = str(chunk.get("text") or "")
    needles = [
        str(entity.get("raw_surface") or ""),
        str(entity.get("name") or ""),
        str(entity.get("semantic_name") or ""),
    ]
    index = -1
    needle = ""
    for candidate in needles:
        if not candidate:
            continue
        index = raw_text.find(candidate)
        if index >= 0:
            needle = candidate
            break
    if index < 0:
        evidence = str(entity.get("evidence_text") or "")
        candidate = evidence[: min(24, len(evidence))]
        if candidate:
            index = raw_text.find(candidate)
            needle = candidate
    if index < 0:
        return sanitize_display(entity.get("evidence_text") or raw_text, limit=360)

    start = max(0, index - 130)
    end = min(len(raw_text), index + max(len(needle), 1) + 230)
    before = raw_text[start:index]
    after = raw_text[index:end]
    punctuation = "。！？；\n"
    last_break = max((before.rfind(mark) for mark in punctuation), default=-1)
    if last_break >= 0:
        start += last_break + 1
    first_candidates = [after.find(mark, max(len(needle), 1)) for mark in punctuation]
    first_candidates = [value for value in first_candidates if value >= 0]
    if first_candidates:
        end = min(end, index + min(first_candidates) + 1)
    return sanitize_display(raw_text[start:end], limit=420)


def type_display(code: Any) -> str:
    value = sanitize_display(code)
    return f"{TYPE_LABELS.get(value, '未映射类型')}（{value or '空'}）"


def confidence_display(entity: dict[str, Any]) -> str:
    for key in (
        "decision_confidence",
        "calibrated_probability",
        "fusion_probability",
        "candidate_confidence",
    ):
        value = entity.get(key)
        if isinstance(value, (int, float)):
            return f"{key}={value:.3f}"
    return "源记录未提供可用置信度"


def build_review_rows() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    documents, chunks, document_order = load_chunks()
    touched = load_touched_entity_ids()
    source_entities = load_source_entities()

    stats = {
        doc_id: {
            "document_id": doc_id,
            "title": documents[doc_id]["title"],
            "machine_review": 0,
            "human_operated": 0,
            "untouched": 0,
        }
        for doc_id in document_order
        if doc_id != EXCLUDED_DOCUMENT_ID
    }
    untouched_rows: list[dict[str, Any]] = []

    for entity in source_entities:
        doc_id = entity_doc_id(entity)
        if doc_id == EXCLUDED_DOCUMENT_ID or doc_id not in stats:
            continue
        if str(entity.get("status")) != "review":
            continue
        stats[doc_id]["machine_review"] += 1
        entity_id = str(entity.get("entity_id") or "")
        if entity_id in touched:
            stats[doc_id]["human_operated"] += 1
            continue
        stats[doc_id]["untouched"] += 1

        raw_chunk_id = source_chunk_id(entity)
        chunk = chunks.get((doc_id, raw_chunk_id))
        page_start = chunk.get("page_start") if chunk else None
        page_end = chunk.get("page_end") if chunk else None
        if page_start is None:
            pages = "页码缺失"
        elif page_end is None or page_end == page_start:
            pages = str(page_start)
        else:
            pages = f"{page_start}-{page_end}"

        candidate_types: list[str] = []
        for key in (
            "candidate_entity_type",
            "teacher_candidate_type",
            "proposed_entity_type",
            "final_entity_type",
        ):
            value = str(entity.get(key) or "")
            if value and value not in candidate_types:
                candidate_types.append(value)

        effective_type = str(
            entity.get("entity_type")
            or entity.get("proposed_entity_type")
            or entity.get("fusion_entity_type")
            or entity.get("teacher_candidate_type")
            or ""
        )

        mention_start = 10**9
        mention = entity.get("raw_mention_span")
        if isinstance(mention, dict) and isinstance(mention.get("start"), int):
            mention_start = int(mention["start"])

        untouched_rows.append(
            {
                "document_id": doc_id,
                "document_title": documents[doc_id]["title"],
                "document_order": document_order.index(doc_id),
                "entity_id": entity_id,
                "name": sanitize_display(entity.get("name"), limit=160),
                "raw_surface": sanitize_display(entity.get("raw_surface"), limit=160),
                "entity_type": effective_type,
                "entity_type_display": type_display(effective_type),
                "candidate_type_trace": " → ".join(
                    type_display(value) for value in candidate_types
                )
                or "无",
                "chunk_id": f"{doc_id}_{raw_chunk_id}",
                "chunk_order": int(chunk.get("_index", 10**6)) if chunk else 10**6,
                "mention_start": mention_start,
                "pages": pages,
                "section": sanitize_display(
                    entity.get("section_title")
                    or " > ".join(entity.get("section_path") or []),
                    limit=100,
                )
                or "未标注章节",
                "evidence": sanitize_display(
                    entity.get("evidence_text")
                    or entity.get("source_evidence_span", {}).get("text"),
                    limit=420,
                )
                or "源记录未提供证据短句",
                "context": excerpt_around(entity, chunk),
                "confidence": confidence_display(entity),
            }
        )

    untouched_rows.sort(
        key=lambda row: (
            row["document_order"],
            row["chunk_order"],
            row["mention_start"],
            row["entity_id"],
        )
    )
    summary_rows = [
        stats[doc_id]
        for doc_id in document_order
        if doc_id != EXCLUDED_DOCUMENT_ID
    ]
    if len(untouched_rows) != EXPECTED_UNTOUCHED:
        raise RuntimeError(
            f"Expected {EXPECTED_UNTOUCHED} untouched review entities, "
            f"found {len(untouched_rows)}"
        )
    return untouched_rows, summary_rows, documents


def set_row_cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    node = tr_pr.find(qn("w:cantSplit"))
    if node is None:
        node = OxmlElement("w:cantSplit")
        tr_pr.append(node)


def add_valid_page_field(paragraph) -> None:
    prefix = paragraph.add_run("第 ")
    set_run_font(prefix, size=9, color=MUTED)

    begin_run = OxmlElement("w:r")
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin_run.append(begin)
    paragraph._p.append(begin_run)

    instruction_run = OxmlElement("w:r")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    instruction_run.append(instruction)
    paragraph._p.append(instruction_run)

    separate_run = OxmlElement("w:r")
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    separate_run.append(separate)
    paragraph._p.append(separate_run)

    value_run = paragraph.add_run("1")
    set_run_font(value_run, size=9, color=MUTED)

    end_run = OxmlElement("w:r")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    end_run.append(end)
    paragraph._p.append(end_run)

    suffix = paragraph.add_run(" 页")
    set_run_font(suffix, size=9, color=MUTED)


def add_title_block(doc: Document) -> None:
    add_text_paragraph(
        doc,
        "医师复验清单",
        size=24,
        bold=True,
        color=INK,
        after=4,
    )
    add_text_paragraph(
        doc,
        "机器判定需复验且人工未操作的实体（已排除Blau文档）",
        size=13.2,
        color=MUTED,
        after=15,
    )
    metadata = [
        ("筛选口径", "机器实体状态 status=review，且不存在任何人工实体复验增量或审计操作"),
        ("数据范围", "排除《Blau综合征诊疗专家共识（2024版）》后的其余10篇文献"),
        ("待复验数量", "32条"),
        ("生成日期", "2026-07-31"),
    ]
    for label, value in metadata:
        paragraph = doc.add_paragraph()
        set_paragraph(paragraph, before=0, after=3, line_spacing=1.18)
        label_run = paragraph.add_run(f"{label}：")
        set_run_font(label_run, size=10.3, bold=True, color=INK)
        value_run = paragraph.add_run(value)
        set_run_font(value_run, size=10.3, color="333333")


def add_summary_table(doc: Document, summary_rows: list[dict[str, Any]]) -> None:
    doc.add_paragraph("复验范围汇总", style="Heading 1")
    table = doc.add_table(rows=1, cols=5)
    widths = [650, 4110, 1500, 1500, 1600]
    set_table_geometry(table, widths)
    set_table_borders(table)
    headers = ["序号", "文献", "机器需复验", "已人工操作", "本次未操作"]
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        set_cell_shading(cell, LIGHT_BLUE)
        format_cell_text(cell, header, bold=True, color=INK, size=9.3)
        if index != 1:
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    mark_repeat_header(table.rows[0])

    for index, item in enumerate(summary_rows, start=1):
        cells = table.add_row().cells
        values = [
            str(index),
            sanitize_display(item["title"], limit=90),
            str(item["machine_review"]),
            str(item["human_operated"]),
            str(item["untouched"]),
        ]
        for cell_index, value in enumerate(values):
            format_cell_text(cells[cell_index], value, size=9.1)
            if cell_index != 1:
                cells[cell_index].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if item["untouched"] > 0:
            set_cell_shading(cells[4], CAUTION_FILL)
        set_row_cant_split(table.rows[-1])

    add_text_paragraph(doc, "", size=2, after=2)
    add_one_cell_callout(
        doc,
        "填写及边界说明",
        (
            "医师对每条实体勾选一个主结论。选择“修改”“合并”或“其他”时，"
            "请填写规范名称、目标类型或合并对象，并给出简要医学依据。"
            "本清单仅用于知识库实体质量复验，不用于患者诊断、处方或治疗决策；"
            "页码来自当前分块元数据。"
        ),
        fill=CALLOUT,
        label_color=DARK_BLUE,
    )
    set_row_cant_split(doc.tables[-1].rows[0])


def add_entity_metadata_table(doc: Document, row: dict[str, Any]) -> None:
    table = doc.add_table(rows=0, cols=4)
    widths = [1350, 3330, 1350, 3330]
    pairs = [
        ("文献页码", f'第{row["pages"]}页', "章节", row["section"]),
        ("机器名称", row["name"], "机器类型", row["entity_type_display"]),
        ("类型轨迹", row["candidate_type_trace"], "机器状态", "review（需人工复验）"),
        ("实体ID", row["entity_id"], "分块ID", row["chunk_id"]),
    ]
    for pair in pairs:
        cells = table.add_row().cells
        for offset in (0, 2):
            set_cell_shading(cells[offset], LIGHT_GRAY)
            format_cell_text(
                cells[offset],
                pair[offset],
                bold=True,
                color=INK,
                size=8.8,
            )
            format_cell_text(cells[offset + 1], pair[offset + 1], size=8.8)
        set_row_cant_split(table.rows[-1])
    set_table_geometry(table, widths)
    set_table_borders(table)


def add_decision_form(doc: Document) -> None:
    table = doc.add_table(rows=4, cols=2)
    widths = [4680, 4680]
    values = [
        ("□ 接受当前名称与类型", "□ 修改实体名称"),
        ("□ 修改实体类型", "□ 删除 / 不纳入知识库"),
        ("□ 合并至已有实体", "□ 其他处理"),
        ("规范名称：", "目标类型 / 合并对象："),
    ]
    for row_index, row_values in enumerate(values):
        for column_index, value in enumerate(row_values):
            format_cell_text(
                table.cell(row_index, column_index),
                value,
                bold=row_index < 3,
                color=INK if row_index < 3 else "333333",
                size=9.4,
            )
        set_row_cant_split(table.rows[row_index])
    set_table_geometry(table, widths)
    set_table_borders(table, color=BORDER, size="4")

    notes = doc.add_table(rows=1, cols=1)
    cell = notes.cell(0, 0)
    paragraph = cell.paragraphs[0]
    paragraph.clear()
    set_paragraph(paragraph, before=0, after=10, line_spacing=1.2)
    run = paragraph.add_run("医学依据 / 修订说明：")
    set_run_font(run, size=9.4, bold=True, color=INK)
    blank = cell.add_paragraph()
    set_paragraph(blank, before=0, after=10, line_spacing=1.2)
    set_table_geometry(notes, [CONTENT_WIDTH_DXA])
    set_table_borders(notes, color=BORDER, size="4")


def add_entity_card(doc: Document, row: dict[str, Any], number: int) -> None:
    heading = doc.add_paragraph(
        f'实体 {number:02d} · {row["name"]}',
        style="Heading 2",
    )
    heading.paragraph_format.keep_with_next = True
    heading.paragraph_format.space_before = Pt(13)
    add_entity_metadata_table(doc, row)

    evidence_table = doc.add_table(rows=2, cols=2)
    widths = [1350, 8010]
    evidence_rows = [
        ("证据短句", row["evidence"]),
        ("局部上下文", row["context"]),
    ]
    for index, (label, value) in enumerate(evidence_rows):
        label_cell = evidence_table.cell(index, 0)
        value_cell = evidence_table.cell(index, 1)
        set_cell_shading(label_cell, LIGHT_BLUE)
        set_cell_shading(value_cell, CALLOUT)
        format_cell_text(label_cell, label, bold=True, color=DARK_BLUE, size=8.9)
        format_cell_text(value_cell, value, size=9.0)
        set_row_cant_split(evidence_table.rows[index])
    set_table_geometry(evidence_table, widths)
    set_table_borders(evidence_table, color=BORDER, size="4")

    add_text_paragraph(
        doc,
        f'机器信息：{row["confidence"]}',
        size=8.5,
        color=MUTED,
        before=3,
        after=4,
        line_spacing=1.1,
    )
    add_decision_form(doc)


def add_section_signature(doc: Document, title: str, count: int) -> None:
    doc.add_paragraph("文献复验签署", style="Heading 3")
    table = doc.add_table(rows=2, cols=4)
    widths = [1400, 3280, 1400, 3280]
    values = [
        ("判定医师", "签名：", "科室 / 职称", ""),
        ("复验数量", f"{count}条", "判定日期", "____年__月__日"),
    ]
    for row_index, row_values in enumerate(values):
        for column_index, value in enumerate(row_values):
            cell = table.cell(row_index, column_index)
            if column_index % 2 == 0:
                set_cell_shading(cell, LIGHT_GRAY)
                format_cell_text(cell, value, bold=True, color=INK, size=9.0)
            else:
                format_cell_text(cell, value, size=9.0)
        set_row_cant_split(table.rows[row_index])
    set_table_geometry(table, widths)
    set_table_borders(table)


def configure_document_header(doc: Document) -> None:
    configure_page(doc)
    section = doc.sections[0]
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.clear()
    set_paragraph(
        paragraph,
        before=0,
        after=0,
        line_spacing=1.0,
        alignment=WD_ALIGN_PARAGRAPH.LEFT,
    )
    run = paragraph.add_run("CmePlatform  |  医师复验清单")
    set_run_font(run, size=9, bold=True, color=MUTED)

    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.clear()
    set_paragraph(
        paragraph,
        before=0,
        after=0,
        line_spacing=1.0,
        alignment=WD_ALIGN_PARAGRAPH.RIGHT,
    )
    add_valid_page_field(paragraph)


def build_document() -> Path:
    untouched_rows, summary_rows, _ = build_review_rows()
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in untouched_rows:
        by_document[row["document_id"]].append(row)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    configure_styles(doc)
    configure_document_header(doc)

    props = doc.core_properties
    props.title = "医师复验清单：机器待复验且人工未操作实体"
    props.subject = "排除Blau文档后的未操作复验实体"
    props.author = "CmePlatform"
    props.keywords = "知识复验, 医师判定, 未操作实体"

    add_title_block(doc)
    add_summary_table(doc, summary_rows)

    number = 1
    for summary in summary_rows:
        doc_id = summary["document_id"]
        rows = by_document.get(doc_id, [])
        if not rows:
            continue
        heading = doc.add_paragraph(
            f'{summary["title"]}（{len(rows)}条）',
            style="Heading 1",
        )
        heading.paragraph_format.page_break_before = True
        heading.paragraph_format.space_before = Pt(0)
        add_text_paragraph(
            doc,
            (
                f'机器判定需复验 {summary["machine_review"]} 条，'
                f'已人工操作 {summary["human_operated"]} 条，'
                f'本次导出未操作 {summary["untouched"]} 条。'
            ),
            size=9.5,
            color=MUTED,
            after=7,
        )
        for row in rows:
            add_entity_card(doc, row, number)
            number += 1
        add_section_signature(doc, summary["title"], len(rows))

    if number - 1 != EXPECTED_UNTOUCHED:
        raise RuntimeError(f"Rendered entity count mismatch: {number - 1}")

    doc.save(OUTPUT_PATH)
    return OUTPUT_PATH


if __name__ == "__main__":
    print(build_document())
