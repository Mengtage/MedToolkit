"""
模式选择路由
处理综述模式和RCT模式的选择
"""

from fastapi import APIRouter, Form, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import io

from services.session_manager import manager, SessionMode
from config.settings import settings
from core.file_parser import extract_text_from_file
from services.logger import logger

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
    logger.info(f"[routes_mode] select_mode called", mode=mode, research_topic=research_topic, paper_title=paper_title)

    if mode not in ["review", "rct"]:
        logger.warning(f"[routes_mode] select_mode invalid mode", mode=mode)
        return JSONResponse({
            "success": False,
            "message": "无效的写作模式"
        }, status_code=400)

    session_mode = SessionMode.RCT if mode == "rct" else SessionMode.REVIEW
    logger.debug(f"[routes_mode] creating session", session_mode=session_mode.value)

    session_id = manager.create_session(session_mode)
    logger.info(f"[routes_mode] session created", session_id=session_id, mode=session_mode.value)

    # 获取创建的会话以获取user_token
    session = manager.get_session(session_id)
    user_token = session.user_token if session else None
    logger.debug(f"[routes_mode] session retrieved", session_id=session_id, has_token=bool(user_token))

    if session_mode == SessionMode.REVIEW and research_topic:
        manager.update_session(session_id, {"research_topic": research_topic})
        logger.debug(f"[routes_mode] research_topic updated", session_id=session_id, research_topic=research_topic)
    elif session_mode == SessionMode.RCT and paper_title:
        manager.update_session(session_id, {"research_topic": paper_title})
        logger.debug(f"[routes_mode] paper_title updated", session_id=session_id, paper_title=paper_title)

    logger.info(f"[routes_mode] select_mode completed", session_id=session_id, mode=mode)
    return JSONResponse({
        "success": True,
        "message": f"{'综述' if mode == 'review' else 'RCT'}模式会话已创建",
        "session_id": session_id,
        "user_token": user_token,  # 返回用户令牌用于后续验证
        "mode": mode
    })


@router.get("/info/{session_id}")
async def get_mode_info(session_id: str):
    """获取会话的模式信息"""
    logger.info(f"[routes_mode] get_mode_info called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_mode] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    logger.debug(f"[routes_mode] session info retrieved", session_id=session_id, mode=session.mode.value, status=session.status)
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
    logger.info(f"[routes_mode] upload_protocol called", session_id=session_id, filename=protocol.filename)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_mode] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if session.mode != SessionMode.RCT:
        logger.warning(f"[routes_mode] wrong mode for protocol upload", session_id=session_id, mode=session.mode.value)
        return JSONResponse({
            "success": False,
            "message": "此操作仅适用于RCT模式"
        }, status_code=400)

    try:
        content = await protocol.read()
        filename = protocol.filename or 'protocol.txt'
        logger.debug(f"[routes_mode] reading protocol file", session_id=session_id, filename=filename, file_size=len(content))

        protocol_text = extract_text_from_file(content, filename)
        logger.debug(f"[routes_mode] protocol extracted", session_id=session_id, text_length=len(protocol_text))

        manager.update_session(session_id, {"protocol_text": protocol_text})
        logger.info(f"[routes_mode] protocol uploaded successfully", session_id=session_id, file_size=len(content))

        return JSONResponse({
            "success": True,
            "message": "研究方案上传成功",
            "file_size": len(content)
        })
    except ValueError as e:
        logger.error(f"[routes_mode] protocol upload value error", session_id=session_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"[routes_mode] protocol upload failed", session_id=session_id, error=str(e), exc_info=True)
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
    logger.info(f"[routes_mode] upload_analysis called", session_id=session_id, filename=analysis.filename)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_mode] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if session.mode != SessionMode.RCT:
        logger.warning(f"[routes_mode] wrong mode for analysis upload", session_id=session_id, mode=session.mode.value)
        return JSONResponse({
            "success": False,
            "message": "此操作仅适用于RCT模式"
        }, status_code=400)

    try:
        content = await analysis.read()
        filename = analysis.filename or 'analysis.txt'
        logger.debug(f"[routes_mode] reading analysis file", session_id=session_id, filename=filename, file_size=len(content))

        analysis_text = extract_text_from_file(content, filename)
        logger.debug(f"[routes_mode] analysis extracted", session_id=session_id, text_length=len(analysis_text))

        manager.update_session(session_id, {"analysis_text": analysis_text})
        logger.info(f"[routes_mode] analysis uploaded successfully", session_id=session_id, file_size=len(content))

        return JSONResponse({
            "success": True,
            "message": "统计分析报告上传成功",
            "file_size": len(content)
        })
    except ValueError as e:
        logger.error(f"[routes_mode] analysis upload value error", session_id=session_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"[routes_mode] analysis upload failed", session_id=session_id, error=str(e), exc_info=True)
        return JSONResponse({
            "success": False,
            "message": f"上传失败: {str(e)}"
        }, status_code=500)


@router.post("/upload/references")
async def upload_references(
    session_id: str = Form(...),
    references: UploadFile = File(...)
):
    """
    上传参考资料（综述模式）

    Args:
        session_id: 会话ID
        references: 参考资料文件

    Returns:
        上传结果
    """
    logger.info(f"[routes_mode] upload_references called", session_id=session_id, filename=references.filename)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_mode] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    try:
        # 安全限制：文件大小最大 10MB
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        ALLOWED_EXTENSIONS = {'txt', 'md', 'docx', 'pdf', 'xlsx', 'xls'}

        # 检查文件扩展名
        filename = references.filename or 'unknown.txt'
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning(f"[routes_mode] invalid file type", session_id=session_id, ext=ext)
            return JSONResponse({
                "success": False,
                "message": f"不支持的文件类型 .{ext}，仅支持 .txt, .md, .docx, .pdf, .xlsx 文件"
            }, status_code=400)

        # 安全文件名处理：移除路径遍历字符
        safe_filename = filename.replace('/', '_').replace('\\', '_').replace('..', '')

        # 读取文件内容并检查大小
        content = await references.read()
        logger.debug(f"[routes_mode] reading references file", session_id=session_id, filename=safe_filename, file_size=len(content))

        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"[routes_mode] file too large", session_id=session_id, file_size=len(content), max_size=MAX_FILE_SIZE)
            return JSONResponse({
                "success": False,
                "message": "文件过大，最大支持 10MB"
            }, status_code=400)

        # 使用通用文件解析函数提取文本
        text_content = extract_text_from_file(content, filename)
        logger.debug(f"[routes_mode] references extracted", session_id=session_id, text_length=len(text_content))

        # 存储参考资料（限制数量）
        MAX_REFERENCES = 10
        if len(session.reference_materials) >= MAX_REFERENCES:
            logger.warning(f"[routes_mode] max references reached", session_id=session_id, count=len(session.reference_materials))
            return JSONResponse({
                "success": False,
                "message": f"最多只能上传 {MAX_REFERENCES} 份参考资料"
            }, status_code=400)

        session.reference_materials.append({
            "filename": safe_filename,
            "content": text_content,
            "upload_time": session.updated_at
        })
        logger.info(f"[routes_mode] references uploaded successfully", session_id=session_id, filename=safe_filename, total_refs=len(session.reference_materials))

        return JSONResponse({
            "success": True,
            "message": f"参考资料 {safe_filename} 上传成功",
            "file_size": len(content),
            "total_references": len(session.reference_materials)
        })
    except ValueError as e:
        logger.error(f"[routes_mode] references upload value error", session_id=session_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"[routes_mode] references upload failed", session_id=session_id, error=str(e), exc_info=True)
        return JSONResponse({
            "success": False,
            "message": f"上传失败: {str(e)}"
        }, status_code=500)


@router.get("/references/list/{session_id}")
async def list_references(session_id: str):
    """
    获取已上传的参考资料列表

    Args:
        session_id: 会话ID

    Returns:
        参考资料列表
    """
    logger.info(f"[routes_mode] list_references called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_mode] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    refs_count = len(session.reference_materials)
    logger.debug(f"[routes_mode] references listed", session_id=session_id, count=refs_count)

    return JSONResponse({
        "success": True,
        "references": [
            {
                "filename": ref["filename"],
                "upload_time": ref["upload_time"],
                "content_preview": ref["content"][:200] + "..." if len(ref["content"]) > 200 else ref["content"]
            }
            for ref in session.reference_materials
        ]
    })


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
