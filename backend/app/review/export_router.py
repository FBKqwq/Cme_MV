from __future__ import annotations

import sys
from pathlib import Path
from threading import Lock

import pythoncom
from docx2pdf import convert
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse


# 当前文件：
# Cme_MV/backend/app/review/export_router.py
#
# parents[3] 指向项目根目录 Cme_MV
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 让 Python 可以导入项目根目录里的文档生成脚本
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from build_untouched_physician_review_doc import build_document


router = APIRouter(
    prefix="/api",
    tags=["医师复验导出"],
)

# 避免多个请求同时调用 Word 转换 PDF
PDF_BUILD_LOCK = Lock()


def build_review_pdf() -> Path:
    """
    先生成 DOCX，再通过 Microsoft Word 转换为 PDF。
    """

    with PDF_BUILD_LOCK:
        # 调用已有程序生成 Word 文档
        docx_path = Path(build_document()).resolve()

        if not docx_path.exists():
            raise FileNotFoundError(
                f"生成的 Word 文件不存在：{docx_path}"
            )

        # PDF 与 Word 文件同名，只改变扩展名
        pdf_path = docx_path.with_suffix(".pdf")

        # 删除旧 PDF，确保每次都是最新内容
        if pdf_path.exists():
            pdf_path.unlink()

        # FastAPI 的同步接口运行在线程中，
        # Windows 调用 Word 前需要初始化 COM。
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
                f"PDF 转换完成后未找到文件：{pdf_path}"
            )

        return pdf_path


@router.get(
    "/export-review-pdf",
    name="export_review_pdf",
    summary="生成医师复验 PDF",
)
def export_review_pdf(request: Request):
    """
    生成医师复验 PDF，并返回下载地址。
    """

    try:
        pdf_path = build_review_pdf()

        download_url = str(
            request.url_for("download_review_pdf")
        )

        return {
            "success": True,
            "message": "医师复验 PDF 生成成功",
            "file_name": pdf_path.name,
            "download_url": download_url,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"生成医师复验 PDF 失败：{exc}",
        ) from exc


@router.get(
    "/download-review-pdf",
    name="download_review_pdf",
    summary="下载医师复验 PDF",
)
def download_review_pdf():
    """
    生成并下载最新的医师复验 PDF。
    """

    try:
        pdf_path = build_review_pdf()

        return FileResponse(
            path=str(pdf_path),
            filename=pdf_path.name,
            media_type="application/pdf",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"下载医师复验 PDF 失败：{exc}",
        ) from exc


# 保留原有 Word 接口，方便需要时下载 DOCX
@router.get(
    "/export-review-doc",
    name="export_review_doc",
    summary="生成医师复验 Word",
)
def export_review_doc(request: Request):
    try:
        docx_path = Path(build_document()).resolve()

        if not docx_path.exists():
            raise FileNotFoundError(
                f"生成的 Word 文件不存在：{docx_path}"
            )

        download_url = str(
            request.url_for("download_review_doc")
        )

        return {
            "success": True,
            "message": "医师复验 Word 生成成功",
            "file_name": docx_path.name,
            "download_url": download_url,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"生成医师复验 Word 失败：{exc}",
        ) from exc


@router.get(
    "/download-review-doc",
    name="download_review_doc",
    summary="下载医师复验 Word",
)
def download_review_doc():
    try:
        docx_path = Path(build_document()).resolve()

        if not docx_path.exists():
            raise FileNotFoundError(
                f"生成的 Word 文件不存在：{docx_path}"
            )

        return FileResponse(
            path=str(docx_path),
            filename=docx_path.name,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"下载医师复验 Word 失败：{exc}",
        ) from exc