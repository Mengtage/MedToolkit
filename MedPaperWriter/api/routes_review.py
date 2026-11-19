"""
审核流程路由
处理综述模式和RCT模式的审核流程

设计依据：MedPaperWriter 设计审查 3.1 / 6.4 节
    - 审核状态、正文、修订意见都必须持久化（重启后可恢复）
    - 修订意见必须真正触发重写：旧稿留痕 → 新版本 → 差异 → 再审核
    - 状态判断使用 SectionStatus.value，不能拿 str(枚举) 去比字符串
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from typing import Optional

from services.session_manager import manager, OutlineNode, SectionStatus
from services.writing import unified_diff, write_outline_section
from services.logger import logger
from core.llm_client import LLMError
from datetime import datetime

router = APIRouter()


def find_outline_node(node: OutlineNode, target_id: str) -> Optional[OutlineNode]:
    """在 outline 树中查找指定 id 的节点"""
    if node.id == target_id:
        return node
    for child in node.children:
        found = find_outline_node(child, target_id)
        if found:
            return found
    return None


def _status_value(node: OutlineNode) -> str:
    """统一取状态字符串（SectionStatus 是 str 混入枚举，

    str(SectionStatus.APPROVED) 在 Python 3.11 下得到 'SectionStatus.APPROVED'，
    旧代码用它做比较导致"待审核列表永远为空、进度永远 0%"。
    """
    return node.status.value if isinstance(node.status, SectionStatus) else str(node.status)


@router.post("/submit")
async def submit_for_review(
    session_id: str = Form(...),
    section_id: str = Form(...),
    content: str = Form("")
):
    """
    提交章节供审核

    Args:
        session_id: 会话ID
        section_id: 章节ID
        content: 章节内容（可选；若传入则以该内容为准）

    Returns:
        提交结果
    """
    logger.info("[routes_review] submit_for_review called", session_id=session_id,
                section_id=section_id, content_length=len(content))

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    # 优先更新 outline 中的节点状态
    if session.outline:
        node = find_outline_node(session.outline, section_id)
        if node:
            if content.strip():
                node.content_zh = content
            node.status = SectionStatus.PENDING_REVIEW
            manager.save(session_id)
            logger.info("[routes_review] section submitted (outline)", session_id=session_id, section_id=section_id)
            return JSONResponse({
                "success": True,
                "message": "章节已提交审核",
                "section_id": section_id,
                "status": "pending_review"
            })

    # 兼容旧版本的 sections 列表
    session.sections.append({
        "section_id": section_id,
        "content": content,
        "status": "pending_review",
        "submitted_at": datetime.now().isoformat(timespec="seconds")
    })
    manager.save(session_id)
    logger.info("[routes_review] section submitted (legacy)", session_id=session_id, section_id=section_id)

    return JSONResponse({
        "success": True,
        "message": "章节已提交审核",
        "section_id": section_id,
        "status": "pending_review"
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
    logger.info("[routes_review] approve_section called", session_id=session_id, section_id=section_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    # 优先更新 outline 中的节点状态
    if session.outline:
        node = find_outline_node(session.outline, section_id)
        if node:
            if not (node.content_zh or node.content_en):
                return JSONResponse({
                    "success": False,
                    "message": "该章节尚无正文，无法审核通过"
                }, status_code=400)
            node.status = SectionStatus.APPROVED
            node.feedback = ""
            manager.save(session_id)
            logger.info("[routes_review] section approved (outline)", session_id=session_id, section_id=section_id)
            return JSONResponse({
                "success": True,
                "message": "章节审核通过",
                "section_id": section_id,
                "status": "approved"
            })

    # 兼容旧版本的 sections 列表
    for section in session.sections:
        if section.get("section_id") == section_id:
            section["status"] = "approved"
            manager.save(session_id)
            logger.info("[routes_review] section approved (legacy)", session_id=session_id, section_id=section_id)
            return JSONResponse({
                "success": True,
                "message": "章节审核通过",
                "section_id": section_id,
                "status": "approved"
            })

    logger.warning("[routes_review] section not found", session_id=session_id, section_id=section_id)
    return JSONResponse({
        "success": False,
        "message": "章节不存在"
    }, status_code=404)


@router.post("/revision")
async def request_revision(
    session_id: str = Form(...),
    section_id: str = Form(...),
    feedback: str = Form(...),
    language: str = Form("中文"),
    regenerate: bool = Form(True)
):
    """
    请求修订并生成新版本

    设计依据：审查报告 3.1 节。旧实现只设置 node.feedback 就返回，前端显示
    "等待 AI 修改"却永远不会变。现在一次调用完成：
        记录修订事件 → 旧稿快照 → 按意见重写 → 返回差异 → 回到待审核

    Args:
        session_id: 会话ID
        section_id: 章节ID
        feedback: 修订意见
        language: 重新生成使用的语言
        regenerate: 是否立即重写（默认 True；False 时仅记录意见）

    Returns:
        修订后的正文、版本号、差异、校验问题
    """
    logger.info("[routes_review] request_revision called", session_id=session_id,
                section_id=section_id, feedback_length=len(feedback), regenerate=regenerate)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    node = find_outline_node(session.outline, section_id) if session.outline else None
    if not node:
        # 兼容旧版本的 sections 列表：只记录意见，无法自动重写
        for section in session.sections:
            if section.get("section_id") == section_id:
                section["status"] = "revision"
                section["feedback"] = feedback
                section.setdefault("revisions", []).append({
                    "feedback": feedback,
                    "created_at": datetime.now().isoformat(timespec="seconds")
                })
                manager.save(session_id)
                return JSONResponse({
                    "success": True,
                    "message": "已记录修订意见（旧版章节不支持自动重写）",
                    "section_id": section_id,
                    "regenerated": False,
                    "feedback_saved": True,
                    "feedback": feedback
                })
        return JSONResponse({
            "success": False,
            "message": "章节不存在"
        }, status_code=404)

    if not (node.content_zh or node.content_en):
        return JSONResponse({
            "success": False,
            "message": "该章节尚无正文，无法提交修订意见；请先撰写本章"
        }, status_code=400)

    # 1) 先落盘修订事件：即使重写失败，意见也不会丢
    node.feedback = feedback
    node.status = SectionStatus.REVISION
    node.revisions.append({
        "feedback": feedback,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "pending_regeneration" if regenerate else "recorded",
        "version": node.current_version,
    })
    manager.save(session_id)

    if not regenerate:
        return JSONResponse({
            "success": True,
            "message": "已记录修订意见",
            "section_id": section_id,
            "regenerated": False,
            "feedback_saved": True,
            "feedback": feedback
        })

    # 2) 旧稿已在 apply_revision 内部快照，这里触发生成新版本
    previous = node.content_zh or node.content_en
    try:
        result = write_outline_section(session, node, language=language, feedback=feedback)
    except (LLMError, ValueError) as e:
        logger.error("[routes_review] revision regeneration failed", session_id=session_id,
                     section_id=section_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": f"修订意见已保存，但重新生成失败：{str(e)}",
            "feedback_saved": True,
            "section_id": section_id,
            "regenerated": False
        }, status_code=500)

    # 3) 修订后回到待审核，而不是自动通过
    node.status = SectionStatus.PENDING_REVIEW
    node.revisions[-1]["status"] = "regenerated"
    node.revisions[-1]["version"] = result["version"]
    manager.save(session_id)

    return JSONResponse({
        "success": True,
        "message": "已按修订意见生成新版本",
        "section_id": section_id,
        "regenerated": True,
        "content": result["content"],
        "version": result["version"],
        "diff": result["diff"] or unified_diff(previous, result["content"]),
        "quality": result["quality"],
        "status": "pending_review"
    })


@router.get("/versions/{session_id}/{section_id}")
async def get_section_versions(session_id: str, section_id: str):
    """查看章节的版本历史（修订链可审计）"""
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)

    node = find_outline_node(session.outline, section_id) if session.outline else None
    if not node:
        return JSONResponse({"success": False, "message": "章节不存在"}, status_code=404)

    return JSONResponse({
        "success": True,
        "section_id": section_id,
        "title": node.title,
        "current_version": node.current_version,
        "status": node.status.value,
        "versions": [
            {
                "version": v.get("version"),
                "source": v.get("source"),
                "created_at": v.get("created_at"),
                "feedback": v.get("feedback", ""),
                "length": len(v.get("content_zh") or v.get("content_en") or ""),
                "quality_issues": len(v.get("quality") or []),
            }
            for v in node.versions
        ],
        "revisions": node.revisions,
    })


@router.post("/rollback")
async def rollback_section(
    session_id: str = Form(...),
    section_id: str = Form(...),
    version: int = Form(...)
):
    """回滚到指定版本（回滚同样留痕，便于事后追溯）"""
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)

    node = find_outline_node(session.outline, section_id) if session.outline else None
    if not node:
        return JSONResponse({"success": False, "message": "章节不存在"}, status_code=404)

    if not node.restore_version(int(version)):
        return JSONResponse({"success": False, "message": f"版本 {version} 不存在"}, status_code=404)

    node.status = SectionStatus.PENDING_REVIEW
    manager.save(session_id)

    return JSONResponse({
        "success": True,
        "message": f"已回滚到版本 {version}",
        "section_id": section_id,
        "content": node.content_zh,
        "version": node.current_version,
        "status": "pending_review"
    })


def collect_all_sections(node: OutlineNode, result: list = None):
    """递归收集所有章节节点（level > 0）"""
    if result is None:
        result = []

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
    logger.debug("[routes_review] get_pending_reviews called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    pending = []

    if session.outline:
        for node in collect_all_sections(session.outline):
            status = _status_value(node)
            if status in ("pending_review", "revision"):
                pending.append({
                    "section_id": node.id,
                    "title": node.title,
                    "status": status,
                    "content_zh": node.content_zh,
                    "content_en": node.content_en,
                    "feedback": node.feedback,
                })
    else:
        pending = [
            s for s in session.sections
            if s.get("status") in ("pending_review", "revision")
        ]

    logger.debug("[routes_review] pending reviews retrieved", session_id=session_id, count=len(pending))
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
    logger.debug("[routes_review] get_all_sections called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    all_sections_list = []
    approved_count = 0

    if session.outline:
        nodes = collect_all_sections(session.outline)
        for node in nodes:
            status = _status_value(node)
            if status == "approved":
                approved_count += 1
            all_sections_list.append({
                "section_id": node.id,
                "title": node.title,
                "status": status,
                "content_zh": node.content_zh,
                "content_en": node.content_en,
                "version": node.current_version,
                "quality_issues": len(node.quality_issues),
            })
    else:
        all_sections_list = session.sections
        approved_count = len([s for s in session.sections if s.get("status") == "approved"])

    logger.debug("[routes_review] all sections retrieved", session_id=session_id,
                 total=len(all_sections_list), approved=approved_count)
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
    logger.debug("[routes_review] get_review_progress called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_review] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    total = approved = pending = writing = 0

    if session.outline:
        nodes = [n for n in collect_all_sections(session.outline) if (n.content_zh or n.content_en)
                 or _status_value(n) != "pending"]
        total = len(nodes)
        for node in nodes:
            status = _status_value(node)
            if status == "approved":
                approved += 1
            elif status in ("pending_review", "revision"):
                pending += 1
            elif status == "writing":
                writing += 1
    else:
        total = len(session.sections)
        approved = len([s for s in session.sections if s.get("status") == "approved"])
        pending = len([s for s in session.sections if s.get("status") in ("pending_review", "revision")])
        writing = len([s for s in session.sections if s.get("status") == "writing"])

    progress = (approved / total * 100) if total > 0 else 0
    logger.debug("[routes_review] progress calculated", session_id=session_id,
                 progress=round(progress, 1), total=total, approved=approved,
                 pending=pending, writing=writing)

    return JSONResponse({
        "success": True,
        "progress": round(progress, 1),
        "total": total,
        "approved": approved,
        "pending": pending,
        "writing": writing
    })
