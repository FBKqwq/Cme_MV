from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException


# 当前文件位置：
# backend/app/review/fastgpt_export_router.py
#
# parents[0] = review
# parents[1] = app
# parents[2] = backend
BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_ROOT / ".env"

# 明确读取 backend/.env，避免因启动目录不同而找不到环境变量
load_dotenv(
    dotenv_path=ENV_PATH,
    override=False,
)


router = APIRouter(
    prefix="/api/review",
    tags=["knowledge-review"],
)


def get_required_env(name: str) -> str:
    """
    读取必需的环境变量。

    环境变量应配置在：
    backend/.env
    """
    value = os.getenv(name, "").strip()

    if value:
        return value

    if not ENV_PATH.exists():
        raise RuntimeError(
            f"缺少环境变量：{name}；"
            f"同时未找到配置文件：{ENV_PATH}"
        )

    raise RuntimeError(
        f"缺少环境变量：{name}；"
        f"请检查配置文件：{ENV_PATH}"
    )


def parse_fastgpt_content(
    content: Any,
) -> dict[str, Any]:
    """
    解析 FastGPT 最终回复。

    支持三种格式：
    1. FastGPT 直接返回对象；
    2. FastGPT 返回 JSON 字符串；
    3. FastGPT 返回包含文件名和下载地址的普通文本。
    """
    if isinstance(content, dict):
        return content

    text = str(content or "").strip()

    if not text:
        raise ValueError("FastGPT 返回内容为空")

    # 尝试直接按 JSON 字符串解析
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 兼容 Markdown JSON 代码块
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    try:
        parsed = json.loads(cleaned)

        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 兼容普通文本回复，从文本中寻找下载地址
    url_match = re.search(
        r"https?://[^\s<>\"]+",
        text,
    )

    if not url_match:
        raise ValueError(
            "无法从 FastGPT 回复中找到 PDF 下载地址。"
            "请检查 FastGPT 的指定回复节点是否输出 "
            "download_url。"
        )

    download_url = url_match.group(0).rstrip(
        "。.,，；;)]}"
    )

    # 尝试从普通文本中提取 PDF 文件名
    file_match = re.search(
        r"([^\r\n<>:\"/\\|?*]+\.pdf)",
        text,
        flags=re.IGNORECASE,
    )

    file_name = (
        file_match.group(1).strip()
        if file_match
        else "医师复验清单.pdf"
    )

    return {
        "success": True,
        "file_name": file_name,
        "download_url": download_url,
    }


def call_fastgpt_export_workflow() -> dict[str, Any]:
    """
    调用 FastGPT 工作流，生成医师复验 PDF。
    """
    api_base = get_required_env(
        "FASTGPT_API_BASE"
    ).rstrip("/")

    api_key = get_required_env(
        "FASTGPT_API_KEY"
    )

    app_id = get_required_env(
        "FASTGPT_APP_ID"
    )

    url = f"{api_base}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    body = {
        "appId": app_id,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": "导出医师复验 PDF",
            }
        ],
    }

    try:
        with httpx.Client(
            timeout=httpx.Timeout(
                connect=30.0,
                read=180.0,
                write=30.0,
                pool=30.0,
            ),
            follow_redirects=True,
        ) as client:
            response = client.post(
                url,
                headers=headers,
                json=body,
            )

            response.raise_for_status()

    except httpx.TimeoutException as exc:
        raise RuntimeError(
            "调用 FastGPT 超时。请检查："
            "FastGPT 工作流、cpolar 和 PDF 生成后端"
            "是否都在运行。"
        ) from exc

    except httpx.HTTPStatusError as exc:
        error_text = exc.response.text[:1000]

        raise RuntimeError(
            "FastGPT 返回错误状态 "
            f"{exc.response.status_code}："
            f"{error_text}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"无法连接 FastGPT：{exc}"
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "FastGPT 返回的内容不是有效 JSON"
        ) from exc

    try:
        content = (
            result["choices"][0]
            ["message"]
            ["content"]
        )
    except (
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise RuntimeError(
            "FastGPT 返回格式不符合预期："
            f"{result}"
        ) from exc

    try:
        parsed = parse_fastgpt_content(
            content
        )
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    download_url = str(
        parsed.get("download_url") or ""
    ).strip()

    if not download_url:
        raise RuntimeError(
            "FastGPT 工作流没有返回 "
            "download_url"
        )

    file_name = str(
        parsed.get("file_name")
        or "医师复验清单.pdf"
    ).strip()

    return {
        "success": bool(
            parsed.get("success", True)
        ),
        "message": str(
            parsed.get("message")
            or "医师复验 PDF 生成成功"
        ),
        "file_name": file_name,
        "download_url": download_url,
    }


@router.post(
    "/export-pdf-via-fastgpt",
    summary="通过 FastGPT 生成医师复验 PDF",
)
def export_pdf_via_fastgpt() -> dict[str, Any]:
    """
    提供给 Cme_MV 前端调用。

    前端只调用本接口，不接触 FastGPT API Key。
    """
    try:
        return call_fastgpt_export_workflow()

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "生成医师复验 PDF 失败："
                f"{exc}"
            ),
        ) from exc