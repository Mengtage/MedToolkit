"""
文档导出路由
处理Word文档导出和参考文献格式
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pathlib import Path
import asyncio
import json

from services.session_manager import manager
from services.logger import logger

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/docx")
async def export_to_docx(
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
    logger.info(f"[routes_export] export_to_docx called", session_id=session_id, language=language, ref_style=ref_style)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_export] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    from core.document_generator import DocumentGenerator

    generator = DocumentGenerator()

    title = session.research_topic or session.research_question or "医学论文"
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    if len(safe_title) > 50:
        safe_title = safe_title[:50]

    output_path = OUTPUT_DIR / f"{safe_title}_{session_id[:8]}.docx"
    logger.debug(f"[routes_export] generating docx", session_id=session_id, output_path=str(output_path))

    try:
        generator.generate_paper(
            session=session,
            output_path=str(output_path),
            language=language,
            ref_style=ref_style
        )
        logger.info(f"[routes_export] docx exported successfully", session_id=session_id, output_path=str(output_path))

        return JSONResponse({
            "success": True,
            "message": "文档导出成功",
            "file_path": str(output_path),
            "file_name": f"{safe_title}.docx"
        })

    except Exception as e:
        logger.error(f"[routes_export] docx export failed", session_id=session_id, error=str(e), exc_info=True)
        return JSONResponse({
            "success": False,
            "message": f"导出失败: {str(e)}"
        }, status_code=500)


@router.get("/download/{session_id}")
async def download_document(
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
    logger.info(f"[routes_export] download_document called", session_id=session_id, language=language, ref_style=ref_style)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_export] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    from core.document_generator import DocumentGenerator

    generator = DocumentGenerator()

    title = session.research_topic or session.research_question or "医学论文"
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    if len(safe_title) > 50:
        safe_title = safe_title[:50]

    output_path = OUTPUT_DIR / f"{safe_title}_{session_id[:8]}.docx"
    logger.debug(f"[routes_export] generating docx for download", session_id=session_id, output_path=str(output_path))

    try:
        generator.generate_paper(
            session=session,
            output_path=str(output_path),
            language=language,
            ref_style=ref_style
        )
        logger.info(f"[routes_export] docx ready for download", session_id=session_id, output_path=str(output_path))

        return FileResponse(
            path=str(output_path),
            filename=f"{safe_title}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    except Exception as e:
        logger.error(f"[routes_export] download failed", session_id=session_id, error=str(e), exc_info=True)
        return JSONResponse({
            "success": False,
            "message": f"导出失败: {str(e)}"
        }, status_code=500)


@router.get("/ref/styles")
async def get_reference_styles():
    """
    获取支持的参考文献格式

    Returns:
        支持的格式列表
    """
    logger.debug(f"[routes_export] get_reference_styles called")
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
    logger.debug(f"[routes_export] preview_references called", style=style)

    import json

    try:
        ref_list = json.loads(references)
        logger.debug(f"[routes_export] references parsed", count=len(ref_list))
    except json.JSONDecodeError:
        logger.warning(f"[routes_export] invalid references JSON")
        return JSONResponse({
            "success": False,
            "message": "参考文献格式错误"
        }, status_code=400)

    from services.reference_formatter import ReferenceFormatter

    formatter = ReferenceFormatter(style)

    formatted = []
    for ref in ref_list:
        formatted.append(formatter.format_reference(ref))

    logger.info(f"[routes_export] references formatted", style=style, count=len(formatted))
    return JSONResponse({
        "success": True,
        "formatted": formatted,
        "style": style
    })


@router.get("/download/progress/{session_id}")
async def download_document_with_progress(
    session_id: str,
    language: str = "中文",
    ref_style: str = "vancouver"
):
    """
    下载Word文档（带实时进度推送）
    
    Args:
        session_id: 会话ID
        language: 文档语言
        ref_style: 参考文献格式
    
    Returns:
        SSE流，包含进度信息和最终下载链接
    """
    logger.info(f"[routes_export] download_document_with_progress called", session_id=session_id, language=language, ref_style=ref_style)

    async def generate():
        session = manager.get_session(session_id)
        if not session:
            yield f"data: {json.dumps({'type': 'error', 'message': '会话不存在'})}\n\n"
            return

        from core.document_generator import DocumentGenerator

        title = session.research_topic or session.research_question or "医学论文"
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        if len(safe_title) > 50:
            safe_title = safe_title[:50]

        output_path = OUTPUT_DIR / f"{safe_title}_{session_id[:8]}.docx"

        # 用于传递进度的队列（使用线程安全的队列）
        import queue
        progress_queue = queue.Queue()

        try:
            generator = DocumentGenerator()
            
            # 设置进度回调 - 将进度放入队列（线程安全）
            def progress_callback(message, progress):
                progress_queue.put({'message': message, 'progress': progress})
            
            generator.set_progress_callback(progress_callback)

            # 生成文档（在后台线程中执行，避免阻塞事件循环）
            def generate_paper_sync():
                generator.generate_paper(
                    session=session,
                    output_path=str(output_path),
                    language=language,
                    ref_style=ref_style
                )
            
            # 在后台线程中执行文档生成
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, generate_paper_sync)

            # 发送所有队列中的进度消息
            while not progress_queue.empty():
                progress = progress_queue.get()
                progress_data = json.dumps({
                    'type': 'progress',
                    'message': progress['message'],
                    'progress': progress['progress']
                })
                yield f"data: {progress_data}\n\n"
                await asyncio.sleep(0.1)

            # 返回下载链接
            yield f"data: {json.dumps({
                'type': 'complete',
                'message': '文档生成完成',
                'progress': 100,
                'file_path': f"/api/export/download/{session_id}?language={language}&ref_style={ref_style}"
            })}\n\n"

        except Exception as e:
            logger.error(f"[routes_export] download with progress failed", session_id=session_id, error=str(e), exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': f'导出失败: {str(e)}'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
