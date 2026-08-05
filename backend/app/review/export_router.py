from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from threading import Lock
from urllib.parse import quote

import pythoncom
from docx2pdf import convert
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse


# 当前文件：
# Cme_MV/backend/app/review/export_router.py
#
# parents[3] 指向项目根目录 Cme_MV
PROJECT_ROOT = Path(__file__).resolve().parents[3]

REVIEW_DATA_ROOT = (
    PROJECT_ROOT
    / "data"
    / "review"
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# 不直接导入 build_document，
# 而是导入整个模块，方便每次切换 REVIEW_ROOT。
import build_untouched_physician_review_doc as review_builder


router = APIRouter(
    prefix="/api",
    tags=["医师复验导出"],
)


# 文档生成器使用模块级 REVIEW_ROOT，
# 所以多个批次不能同时修改该变量。
# 使用锁确保一次只生成一个批次。
PDF_BUILD_LOCK = Lock()


def normalize_batch_id(batch: str) -> str:
    batch_id = str(batch or "").strip()

    if not batch_id:
        raise ValueError("没有收到复验批次编号")

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        batch_id,
    ):
        raise ValueError(
            f"非法的复验批次编号：{batch_id}"
        )

    return batch_id


def batch_paths(
    batch: str,
) -> tuple[Path, Path, Path]:
    """
    根据批次得到：

    data/review/4
    Word 输出路径
    PDF 输出路径
    """
    batch_id = normalize_batch_id(batch)

    batch_root = (
        REVIEW_DATA_ROOT
        / batch_id
    ).resolve()

    # 防止批次参数跳出 data/review 目录
    review_root_resolved = REVIEW_DATA_ROOT.resolve()

    if review_root_resolved not in batch_root.parents:
        raise ValueError("批次目录不合法")

    entity_root = (
        batch_root
        / "current"
        / "entity_nodes"
    )

    chunk_root = (
        batch_root
        / "current"
        / "chunks"
    )

    if not batch_root.exists():
        raise FileNotFoundError(
            f"第 {batch_id} 批目录不存在："
            f"{batch_root}"
        )

    if not entity_root.exists():
        raise FileNotFoundError(
            f"第 {batch_id} 批实体目录不存在："
            f"{entity_root}"
        )

    if not chunk_root.exists():
        raise FileNotFoundError(
            f"第 {batch_id} 批 Chunk 目录不存在："
            f"{chunk_root}"
        )

    export_root = (
        batch_root
        / "state"
        / "exports"
    )

    export_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    day = date.today().isoformat()

    file_stem = (
        f"医师复验清单_第{batch_id}批_"
        f"机器待复验且人工未操作_{day}"
    )

    docx_path = (
        export_root
        / f"{file_stem}.docx"
    )

    pdf_path = (
        export_root
        / f"{file_stem}.pdf"
    )

    return (
        batch_root,
        docx_path,
        pdf_path,
    )


def build_review_docx(
    batch: str,
) -> Path:
    batch_id = normalize_batch_id(batch)

    (
        batch_root,
        docx_path,
        _,
    ) = batch_paths(batch_id)

    # 关键修改：
    # 把生成程序的数据根目录切换到当前批次。
    #
    # 第4批：
    # data/review/4
    review_builder.REVIEW_ROOT = batch_root

    # 同时设置当前批次的输出文件。
    review_builder.OUTPUT_PATH = docx_path

    # 实体数量随批次变化，不能固定为某个数量。
    if hasattr(
        review_builder,
        "EXPECTED_UNTOUCHED",
    ):
        review_builder.EXPECTED_UNTOUCHED = None

    generated_path = Path(
        review_builder.build_document()
    ).resolve()

    if not generated_path.exists():
        raise FileNotFoundError(
            "Word 文档生成完成后不存在："
            f"{generated_path}"
        )

    return generated_path


def build_review_pdf(
    batch: str,
) -> Path:
    batch_id = normalize_batch_id(batch)

    with PDF_BUILD_LOCK:
        docx_path = build_review_docx(
            batch_id
        )

        pdf_path = docx_path.with_suffix(
            ".pdf"
        )

        if pdf_path.exists():
            pdf_path.unlink()

        pythoncom.CoInitialize()

        try:
            convert(
                str(docx_path),
                str(pdf_path),
            )
        finally:
            pythoncom.CoUninitialize()

        if not pdf_path.exists():
            raise RuntimeError(
                "PDF 转换完成后未找到文件："
                f"{pdf_path}"
            )

        return pdf_path


@router.get(
    "/export-review-pdf",
    name="export_review_pdf",
    summary="生成当前批次医师复验 PDF",
)
def export_review_pdf(
    request: Request,
    batch: str = Query(
        ...,
        description="复验批次编号，例如 4",
    ),
):
    try:
        batch_id = normalize_batch_id(batch)

        pdf_path = build_review_pdf(
            batch_id
        )

        base_download_url = str(
            request.url_for(
                "download_review_pdf"
            )
        )

        download_url = (
            f"{base_download_url}"
            f"?batch={quote(batch_id)}"
        )

        return {
            "success": True,
            "message": (
                f"第 {batch_id} 批医师复验 PDF "
                "生成成功"
            ),
            "batch": batch_id,
            "file_name": pdf_path.name,
            "download_url": download_url,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"生成第 {batch} 批医师复验 "
                f"PDF 失败：{exc}"
            ),
        ) from exc


@router.get(
    "/download-review-pdf",
    name="download_review_pdf",
    summary="下载当前批次医师复验 PDF",
)
def download_review_pdf(
    batch: str = Query(
        ...,
        description="复验批次编号，例如 4",
    ),
):
    try:
        batch_id = normalize_batch_id(batch)

        (
            _,
            _,
            expected_pdf_path,
        ) = batch_paths(batch_id)

        # 如果前面的导出接口已经生成，就直接下载。
        # 如果用户直接访问下载接口，则自动生成。
        if expected_pdf_path.exists():
            pdf_path = expected_pdf_path
        else:
            pdf_path = build_review_pdf(
                batch_id
            )

        return FileResponse(
            path=str(pdf_path),
            filename=pdf_path.name,
            media_type="application/pdf",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"下载第 {batch} 批医师复验 "
                f"PDF 失败：{exc}"
            ),
        ) from exc


@router.get(
    "/export-review-doc",
    name="export_review_doc",
    summary="生成当前批次医师复验 Word",
)
def export_review_doc(
    request: Request,
    batch: str = Query(
        ...,
        description="复验批次编号，例如 4",
    ),
):
    try:
        batch_id = normalize_batch_id(batch)

        with PDF_BUILD_LOCK:
            docx_path = build_review_docx(
                batch_id
            )

        base_download_url = str(
            request.url_for(
                "download_review_doc"
            )
        )

        download_url = (
            f"{base_download_url}"
            f"?batch={quote(batch_id)}"
        )

        return {
            "success": True,
            "message": (
                f"第 {batch_id} 批医师复验 Word "
                "生成成功"
            ),
            "batch": batch_id,
            "file_name": docx_path.name,
            "download_url": download_url,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"生成第 {batch} 批医师复验 "
                f"Word 失败：{exc}"
            ),
        ) from exc


@router.get(
    "/download-review-doc",
    name="download_review_doc",
    summary="下载当前批次医师复验 Word",
)
def download_review_doc(
    batch: str = Query(
        ...,
        description="复验批次编号，例如 4",
    ),
):
    try:
        batch_id = normalize_batch_id(batch)

        (
            _,
            expected_docx_path,
            _,
        ) = batch_paths(batch_id)

        if expected_docx_path.exists():
            docx_path = expected_docx_path
        else:
            with PDF_BUILD_LOCK:
                docx_path = build_review_docx(
                    batch_id
                )

        return FileResponse(
            path=str(docx_path),
            filename=docx_path.name,
            media_type=(
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml.document"
            ),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"下载第 {batch} 批医师复验 "
                f"Word 失败：{exc}"
            ),
        ) from exc