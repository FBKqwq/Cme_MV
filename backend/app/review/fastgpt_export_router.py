from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query


# 当前文件：
# backend/app/review/fastgpt_export_router.py
#
# parents[2] 指向 backend
BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_ROOT / ".env"

load_dotenv(
    dotenv_path=ENV_PATH,
    override=True,
)


router = APIRouter(
    prefix="/api/review",
    tags=["knowledge-review"],
)


def get_required_env(name: str) -> str:
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


def normalize_batch_id(batch: str) -> str:
    """
    校验批次编号。

    当前批次通常是：
    1、2、3、4……
    同时允许字母、下划线和短横线，方便以后扩展。
    """
    batch_id = str(batch or "").strip()

    if not batch_id:
        raise RuntimeError("没有收到复验批次编号")

    if not re.fullmatch(r"[A-Za-z0-9_-]+", batch_id):
        raise RuntimeError(
            f"非法的复验批次编号：{batch_id}"
        )

    return batch_id


def parse_fastgpt_content(
    content: Any,
) -> dict[str, Any]:
    if isinstance(content, dict):
        return content

    text = str(content or "").strip()

    if not text:
        raise ValueError("FastGPT 返回内容为空")

    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

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


def call_fastgpt_export_workflow(
    batch: str,
) -> dict[str, Any]:
    """
    调用 FastGPT。

    这里把批次编号作为“用户问题”传给 FastGPT。
    例如当前是第4批，发送给 FastGPT 的内容就是：
    4
    """
    batch_id = normalize_batch_id(batch)

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

                # 关键修改：
                # 不再发送固定文字，
                # 直接发送当前批次编号
                "content": batch_id,
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
            "调用 FastGPT 超时。请检查 FastGPT 工作流、"
            "cpolar 和 PDF 生成后端是否都在运行。"
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
            "FastGPT 工作流没有返回 download_url"
        )

    file_name = str(
        parsed.get("file_name")
        or f"第{batch_id}批医师复验清单.pdf"
    ).strip()

    return {
        "success": bool(
            parsed.get("success", True)
        ),
        "message": (
            f"第 {batch_id} 批医师复验 PDF 生成成功"
        ),
        "batch": batch_id,
        "file_name": file_name,
        "download_url": download_url,
    }


@router.post(
    "/export-pdf-via-fastgpt",
    summary="通过 FastGPT 生成当前批次医师复验 PDF",
)
def export_pdf_via_fastgpt(
    batch: str = Query(
        ...,
        min_length=1,
        max_length=64,
        description="当前复验批次编号，例如 4",
    ),
) -> dict[str, Any]:
    """
    前端调用示例：

    POST /api/review/export-pdf-via-fastgpt?batch=4
    """
    try:
        batch_id = normalize_batch_id(batch)

        return call_fastgpt_export_workflow(
            batch_id
        )

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