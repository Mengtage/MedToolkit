"""
审核流程路由
处理综述模式和RCT模式的审核流程
"""

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from services.session_manager import manager, SessionMode

router = APIRouter()


@router.post("/submit")
async def submit_for_review(
    session_id: str = Form(...),
    section_id: str = Form(...),
    content: str = Form(...)
):
    """
    提交章节供审核

    Args:
        session_id: 会话ID
        section_id: 章节ID
        content: 章节内容

    Returns:
        提交结果
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    session.sections.append({
        "section_id": section_id,
        "content": content,
        "status": "pending_review",
        "submitted_at": session.updated_at
    })

    return JSONResponse({
        "success": True,
        "message": "章节已提交审核",
        "section_id": section_id
    })


@router.post("/approve")
async def approve_section(
    session_id: str = Form(...),
    section_id: str = Form(...)
):
    """
    审核通过

    Args:
        session_id: 会话ID
        section_id: 章节ID

    Returns:
        审核结果
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    for section in session.sections:
        if section["section_id"] == section_id:
            section["status"] = "approved"
            return JSONResponse({
                "success": True,
                "message": "章节审核通过",
                "section_id": section_id
            })

    return JSONResponse({
        "success": False,
        "message": "章节不存在"
    }, status_code=404)


@router.post("/revision")
async def request_revision(
    session_id: str = Form(...),
    section_id: str = Form(...),
    feedback: str = Form(...)
):
    """
    请求修订

    Args:
        session_id: 会话ID
        section_id: 章节ID
        feedback: 修订意见

    Returns:
        修订请求结果
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    for section in session.sections:
        if section["section_id"] == section_id:
            section["status"] = "revision"
            section["feedback"] = feedback
            return JSONResponse({
                "success": True,
                "message": "已提交修订意见",
                "section_id": section_id,
                "feedback": feedback
            })

    return JSONResponse({
        "success": False,
        "message": "章节不存在"
    }, status_code=404)


@router.get("/pending")
async def get_pending_reviews(
    session_id: str
):
    """
    获取待审核列表

    Args:
        session_id: 会话ID

    Returns:
        待审核章节列表
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    pending = [
        s for s in session.sections
        if s["status"] in ["pending_review", "revision"]
    ]

    return JSONResponse({
        "success": True,
        "pending_count": len(pending),
        "sections": pending
    })


@router.get("/all")
async def get_all_sections(
    session_id: str
):
    """
    获取所有章节状态

    Args:
        session_id: 会话ID

    Returns:
        所有章节及其状态
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    return JSONResponse({
        "success": True,
        "total_sections": len(session.sections),
        "approved_count": len([s for s in session.sections if s["status"] == "approved"]),
        "sections": session.sections
    })


@router.get("/progress")
async def get_review_progress(
    session_id: str
):
    """
    获取审核进度

    Args:
        session_id: 会话ID

    Returns:
        审核进度信息
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    total = len(session.sections)
    approved = len([s for s in session.sections if s["status"] == "approved"])
    pending = len([s for s in session.sections if s["status"] in ["pending_review", "revision"]])
    writing = len([s for s in session.sections if s["status"] == "writing"])

    progress = (approved / total * 100) if total > 0 else 0

    return JSONResponse({
        "success": True,
        "progress": round(progress, 1),
        "total": total,
        "approved": approved,
        "pending": pending,
        "writing": writing
    })
