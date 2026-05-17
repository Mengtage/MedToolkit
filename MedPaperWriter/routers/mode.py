"""
模式选择路由
处理综述模式和RCT模式的选择
"""

from fastapi import APIRouter, Form, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from services.session_manager import manager, SessionMode

router = APIRouter()


@router.post("/select")
async def select_mode(
    mode: str = Form(...),
    research_topic: Optional[str] = Form(None),
    paper_title: Optional[str] = Form(None)
):
    """
    选择写作模式并创建会话

    Args:
        mode: 模式类型 ("review" 或 "rct")
        research_topic: 研究主题（综述模式）
        paper_title: 论文标题（RCT模式）

    Returns:
        session_id: 新创建的会话ID
    """
    if mode not in ["review", "rct"]:
        return JSONResponse({
            "success": False,
            "message": "无效的写作模式"
        }, status_code=400)

    session_mode = SessionMode.RCT if mode == "rct" else SessionMode.REVIEW
    session_id = manager.create_session(session_mode)

    if session_mode == SessionMode.REVIEW and research_topic:
        manager.update_session(session_id, {"research_topic": research_topic})
    elif session_mode == SessionMode.RCT and paper_title:
        manager.update_session(session_id, {"research_topic": paper_title})

    return JSONResponse({
        "success": True,
        "message": f"{'综述' if mode == 'review' else 'RCT'}模式会话已创建",
        "session_id": session_id,
        "mode": mode
    })


@router.get("/info/{session_id}")
async def get_mode_info(session_id: str):
    """获取会话的模式信息"""
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    return JSONResponse({
        "success": True,
        "mode": session.mode.value,
        "status": session.status,
        "research_topic": session.research_topic,
        "research_question": session.research_question
    })


@router.post("/upload/protocol")
async def upload_protocol(
    session_id: str = Form(...),
    protocol: UploadFile = File(...)
):
    """
    上传研究方案（RCT模式）

    Args:
        session_id: 会话ID
        protocol: 研究方案文件

    Returns:
        success: 上传是否成功
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if session.mode != SessionMode.RCT:
        return JSONResponse({
            "success": False,
            "message": "此操作仅适用于RCT模式"
        }, status_code=400)

    try:
        content = await protocol.read()
        protocol_text = content.decode("utf-8")
        manager.update_session(session_id, {"protocol_text": protocol_text})

        return JSONResponse({
            "success": True,
            "message": "研究方案上传成功",
            "file_size": len(content)
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"上传失败: {str(e)}"
        }, status_code=500)


@router.post("/upload/analysis")
async def upload_analysis(
    session_id: str = Form(...),
    analysis: UploadFile = File(...)
):
    """
    上传统计分析报告（RCT模式）

    Args:
        session_id: 会话ID
        analysis: 统计分析报告文件

    Returns:
        success: 上传是否成功
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if session.mode != SessionMode.RCT:
        return JSONResponse({
            "success": False,
            "message": "此操作仅适用于RCT模式"
        }, status_code=400)

    try:
        content = await analysis.read()
        analysis_text = content.decode("utf-8")
        manager.update_session(session_id, {"analysis_text": analysis_text})

        return JSONResponse({
            "success": True,
            "message": "统计分析报告上传成功",
            "file_size": len(content)
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"上传失败: {str(e)}"
        }, status_code=500)


@router.get("/rct/protocol/generate")
async def rct_protocol_reserved():
    """
    RCT研究方案生成接口（预留）

    此功能暂未开放
    """
    return JSONResponse({
        "status": "reserved",
        "message": "此功能暂未开放，敬请期待",
        "estimated_release": "TBD"
    })
