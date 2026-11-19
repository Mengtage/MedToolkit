"""
审核流程路由
处理综述模式和RCT模式的审核流程
"""

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from services.session_manager import manager, SessionMode, OutlineNode, SectionStatus
from services.logger import logger

router = APIRouter()


def find_outline_node(node: OutlineNode, target_id: str) -> Optional[OutlineNode]:
    """
    在 outline 树中查找指定 id 的节点
    
    Args:
        node: 当前节点
        target_id: 目标节点 id
        
    Returns:
        找到的节点或 None
    """
    if node.id == target_id:
        return node
    for child in node.children:
        found = find_outline_node(child, target_id)
        if found:
            return found
    return None


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
    logger.info(f"[routes_review] submit_for_review called", session_id=session_id, section_id=section_id, content_length=len(content))

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    # 更新 outline 中的节点状态
    if session.outline:
        node = find_outline_node(session.outline, section_id)
        if node:
            node.status = SectionStatus.PENDING_REVIEW
            logger.info(f"[routes_review] section submitted (outline)", session_id=session_id, section_id=section_id)
            return JSONResponse({
                "success": True,
                "message": "章节已提交审核",
                "section_id": section_id
            })

    # 兼容旧版本的 sections 列表
    session.sections.append({
        "section_id": section_id,
        "content": content,
        "status": "pending_review",
        "submitted_at": session.updated_at
    })
    logger.info(f"[routes_review] section submitted (legacy)", session_id=session_id, section_id=section_id)

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
    logger.info(f"[routes_review] approve_section called", session_id=session_id, section_id=section_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    # 优先更新 outline 中的节点状态
    if session.outline:
        node = find_outline_node(session.outline, section_id)
        if node:
            node.status = SectionStatus.APPROVED
            logger.info(f"[routes_review] section approved (outline)", session_id=session_id, section_id=section_id)
            return JSONResponse({
                "success": True,
                "message": "章节审核通过",
                "section_id": section_id
            })

    # 兼容旧版本的 sections 列表
    for section in session.sections:
        if section["section_id"] == section_id:
            section["status"] = "approved"
            logger.info(f"[routes_review] section approved (legacy)", session_id=session_id, section_id=section_id)
            return JSONResponse({
                "success": True,
                "message": "章节审核通过",
                "section_id": section_id
            })

    logger.warning(f"[routes_review] section not found", session_id=session_id, section_id=section_id)
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
    logger.info(f"[routes_review] request_revision called", session_id=session_id, section_id=section_id, feedback_length=len(feedback))

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    # 优先更新 outline 中的节点状态
    if session.outline:
        node = find_outline_node(session.outline, section_id)
        if node:
            node.status = SectionStatus.REVISION
            if not hasattr(node, 'feedback'):
                node.feedback = feedback
            else:
                node.feedback = feedback
            logger.info(f"[routes_review] revision requested (outline)", session_id=session_id, section_id=section_id)
            return JSONResponse({
                "success": True,
                "message": "已提交修订意见",
                "section_id": section_id,
                "feedback": feedback
            })

    # 兼容旧版本的 sections 列表
    for section in session.sections:
        if section["section_id"] == section_id:
            section["status"] = "revision"
            section["feedback"] = feedback
            logger.info(f"[routes_review] revision requested (legacy)", session_id=session_id, section_id=section_id)
            return JSONResponse({
                "success": True,
                "message": "已提交修订意见",
                "section_id": section_id,
                "feedback": feedback
            })

    logger.warning(f"[routes_review] section not found", session_id=session_id, section_id=section_id)
    return JSONResponse({
        "success": False,
        "message": "章节不存在"
    }, status_code=404)


def collect_all_sections(node: OutlineNode, result: list = None):
    """
    递归收集所有章节节点
    
    Args:
        node: 当前节点
        result: 结果列表
        
    Returns:
        所有章节节点的列表
    """
    if result is None:
        result = []
    
    # 只收集有内容的节点（level > 0）
    if node.level > 0:
        result.append(node)
    
    for child in node.children:
        collect_all_sections(child, result)
    
    return result


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
    logger.debug(f"[routes_review] get_pending_reviews called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    pending = []

    # 优先从 outline 中获取
    if session.outline:
        all_sections = collect_all_sections(session.outline)
        pending = [
            {
                "section_id": s.id,
                "title": s.title,
                "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                "content_zh": s.content_zh,
                "content_en": s.content_en
            }
            for s in all_sections
            if s.status and str(s.status) in ["pending_review", "revision"]
        ]
    else:
        # 兼容旧版本的 sections 列表
        pending = [
            s for s in session.sections
            if s["status"] in ["pending_review", "revision"]
        ]

    logger.debug(f"[routes_review] pending reviews retrieved", session_id=session_id, count=len(pending))
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
    logger.debug(f"[routes_review] get_all_sections called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    all_sections_list = []
    approved_count = 0

    # 优先从 outline 中获取
    if session.outline:
        all_nodes = collect_all_sections(session.outline)
        all_sections_list = [
            {
                "section_id": s.id,
                "title": s.title,
                "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                "content_zh": s.content_zh,
                "content_en": s.content_en
            }
            for s in all_nodes
        ]
        approved_count = len([
            s for s in all_nodes
            if s.status and str(s.status) == "approved"
        ])
    else:
        # 兼容旧版本的 sections 列表
        all_sections_list = session.sections
        approved_count = len([
            s for s in session.sections
            if s["status"] == "approved"
        ])

    logger.debug(f"[routes_review] all sections retrieved", session_id=session_id, total=len(all_sections_list), approved=approved_count)
    return JSONResponse({
        "success": True,
        "total_sections": len(all_sections_list),
        "approved_count": approved_count,
        "sections": all_sections_list
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
    logger.debug(f"[routes_review] get_review_progress called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    total = 0
    approved = 0
    pending = 0
    writing = 0

    # 优先从 outline 中获取
    if session.outline:
        all_nodes = collect_all_sections(session.outline)
        total = len(all_nodes)
        approved = len([s for s in all_nodes if s.status and str(s.status) == "approved"])
        pending = len([s for s in all_nodes if s.status and str(s.status) in ["pending_review", "revision"]])
        writing = len([s for s in all_nodes if s.status and str(s.status) == "writing"])
    else:
        # 兼容旧版本的 sections 列表
        total = len(session.sections)
        approved = len([s for s in session.sections if s["status"] == "approved"])
        pending = len([s for s in session.sections if s["status"] in ["pending_review", "revision"]])
        writing = len([s for s in session.sections if s["status"] == "writing"])

    progress = (approved / total * 100) if total > 0 else 0
    logger.debug(f"[routes_review] progress calculated", session_id=session_id, progress=round(progress, 1), total=total, approved=approved, pending=pending, writing=writing)

    return JSONResponse({
        "success": True,
        "progress": round(progress, 1),
        "total": total,
        "approved": approved,
        "pending": pending,
        "writing": writing
    })
