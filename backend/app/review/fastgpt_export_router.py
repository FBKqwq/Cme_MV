from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException


# 加载 backend/.env
load_dotenv()

router = APIRouter(
    prefix="/api/review",
    tags=["knowledge-review"],
)


def get_required_env(name: str) -> str:
    """
    读取必需的环境变量。
    如果缺少配置，返回清晰错误，而不是让程序莫名失败。
    """
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(f"缺少环境变量：{name}")

    return value


def parse_fastgpt_content(content: Any) -> dict[str, Any]:
    """
    解析 FastGPT 最终回复。

    优先按 JSON 解析；
    如果回复节点仍是普通文本，则尝试从文本中提取下载地址。
    """
    if isinstance(content, dict):
        return content

    text = str(content or "").strip()

    if not text:
        raise ValueError("FastGPT 返回内容为空")

    # 最理想情况：指定回复节点返回 JSON 字符串
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 兼容 Markdown 代码块
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

    # 兼容原来的普通文本回复
    url_match = re.search(r"https?://[^\s<>\"]+", text)

    if not url_match:
        raise ValueError(
            "无法从 FastGPT 回复中找到 PDF 下载地址，"
            "请检查指定回复节点是否输出 download_url"
        )

    download_url = url_match.group(0).rstrip("。.,，；;")

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
    调用 FastGPT 工作流，让工作流生成医师复验 PDF。
    """
    api_base = get_required_env("FASTGPT_API_BASE").rstrip("/")
    api_key = get_required_env("FASTGPT_API_KEY")
    app_id = get_required_env("FASTGPT_APP_ID")

    url = f"{api_base}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
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
        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                url,
                headers=headers,
                json=body,
            )

            response.raise_for_status()

    except httpx.TimeoutException as exc:
        raise RuntimeError(
            "调用 FastGPT 超时，请检查 FastAPI、cpolar 和 "
            "FastGPT 工作流是否都在运行"
        ) from exc

    except httpx.HTTPStatusError as exc:
        error_text = exc.response.text[:1000]

        raise RuntimeError(
            f"FastGPT 返回错误状态 "
            f"{exc.response.status_code}：{error_text}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"无法连接 FastGPT：{exc}"
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "FastGPT 返回的不是有效 JSON"
        ) from exc

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"FastGPT 返回格式不符合预期：{result}"
        ) from exc

    parsed = parse_fastgpt_content(content)

    download_url = str(
        parsed.get("download_url") or ""
    ).strip()

    if not download_url:
        raise RuntimeError(
            "FastGPT 工作流没有返回 download_url"
        )

    return {
        "success": bool(parsed.get("success", True)),
        "message": "医师复验 PDF 生成成功",
        "file_name": str(
            parsed.get("file_name")
            or "医师复验清单.pdf"
        ),
        "download_url": download_url,
    }


@router.post(
    "/export-pdf-via-fastgpt",
    summary="通过 FastGPT 生成医师复验 PDF",
)
def export_pdf_via_fastgpt() -> dict[str, Any]:
    """
    提供给 Cme_MV 前端调用的接口。

    前端不需要知道 FastGPT Key，也不需要直接访问 FastGPT。
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
            detail=f"生成医师复验 PDF 失败：{exc}",
        ) from exc