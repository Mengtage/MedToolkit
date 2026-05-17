"""
文档导出路由
处理Word文档导出和参考文献格式
"""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional
import os
import re
import time
from pathlib import Path

from services.session_manager import manager, SessionMode

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
_request_counts: dict[str, list[float]] = {}


def _check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit."""
    current_time = time.time()
    if client_ip not in _request_counts:
        _request_counts[client_ip] = []
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip]
        if current_time - t < RATE_LIMIT_WINDOW
    ]
    if len(_request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    _request_counts[client_ip].append(current_time)
    return True


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks."""
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    filename = re.sub(r'\.\.', '', filename)
    return filename[:255]


@router.post("/docx")
async def export_to_docx(
    request: Request,
    session_id: str = Form(...),
    language: str = Form("中文"),
    ref_style: str = Form("vancouver")
):
    """
    导出为Word文档

    Args:
        session_id: 会话ID
        language: 文档语言
        ref_style: 参考文献格式

    Returns:
        下载文件路径
    """
    client_ip = _get_client_ip(request)
    if not _check_rate_limit(client_ip):
        return JSONResponse({
            "success": False,
            "message": "请求过于频繁，请稍后再试"
        }, status_code=429)

    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    from services.document_generator import DocumentGenerator

    generator = DocumentGenerator()

    title = session.research_topic or session.research_question or "医学论文"
    safe_title = sanitize_filename(title)
    safe_session_id = sanitize_filename(session_id)

    output_path = OUTPUT_DIR / f"{safe_title}_{safe_session_id[:8]}.docx"

    try:
        generator.generate_paper(
            session=session,
            output_path=str(output_path),
            language=sanitize_filename(language),
            ref_style=sanitize_filename(ref_style)
        )

        return JSONResponse({
            "success": True,
            "message": "文档导出成功",
            "file_path": str(output_path),
            "file_name": f"{safe_title}.docx"
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": "导出失败"
        }, status_code=500)


@router.get("/download/{session_id}")
async def download_document(
    request: Request,
    session_id: str,
    language: str = "中文",
    ref_style: str = "vancouver"
):
    """
    下载Word文档

    Args:
        session_id: 会话ID
        language: 文档语言
        ref_style: 参考文献格式

    Returns:
        文件下载响应
    """
    client_ip = _get_client_ip(request)
    if not _check_rate_limit(client_ip):
        return JSONResponse({
            "success": False,
            "message": "请求过于频繁，请稍后再试"
        }, status_code=429)

    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    from services.document_generator import DocumentGenerator

    generator = DocumentGenerator()

    title = session.research_topic or session.research_question or "医学论文"
    safe_title = sanitize_filename(title)
    safe_session_id = sanitize_filename(session_id)

    output_path = OUTPUT_DIR / f"{safe_title}_{safe_session_id[:8]}.docx"

    try:
        generator.generate_paper(
            session=session,
            output_path=str(output_path),
            language=sanitize_filename(language),
            ref_style=sanitize_filename(ref_style)
        )

        return FileResponse(
            path=str(output_path),
            filename=f"{safe_title}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": "导出失败"
        }, status_code=500)


@router.get("/ref/styles")
async def get_reference_styles():
    """
    获取支持的参考文献格式

    Returns:
        支持的格式列表
    """
    from services.reference_formatter import ReferenceFormatter

    return JSONResponse({
        "success": True,
        "styles": ReferenceFormatter.SUPPORTED_STYLES
    })


@router.post("/preview/references")
async def preview_references(
    references: str = Form(...),
    style: str = Form("vancouver")
):
    """
    预览参考文献格式化效果

    Args:
        references: 参考文献JSON字符串
        style: 格式风格

    Returns:
        格式化后的参考文献列表
    """
    import json

    try:
        ref_list = json.loads(references)
    except json.JSONDecodeError:
        return JSONResponse({
            "success": False,
            "message": "参考文献格式错误"
        }, status_code=400)

    from services.reference_formatter import ReferenceFormatter

    formatter = ReferenceFormatter(style)

    formatted = []
    for ref in ref_list:
        formatted.append(formatter.format_reference(ref))

    return JSONResponse({
        "success": True,
        "formatted": formatted,
        "style": style
    })
