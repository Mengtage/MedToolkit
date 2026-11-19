"""
文档导出路由
处理Word文档导出和参考文献格式

设计依据：MedPaperWriter 设计审查 3.1 / 3.6 / 阶段1 节
    - 导出必须返回 warnings：缺摘要、缺参考文献、未审核章节都显式告知
    - 参考文献从会话的结构化条目渲染，并提供导入/预览接口（Hunter 适配入口）
    - 新增导出前质量报告接口（确定性校验 + 报告规范完整性）
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pathlib import Path
import asyncio
import json
import queue

from services.session_manager import manager
from services.logger import logger
from core.reference_formatter import ReferenceFormatter, normalize_reference
from core.reporting_guidelines import GUIDELINES
from core.validators import validate_manuscript, summarize

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_title(session) -> str:
    title = session.research_topic or session.research_question or "医学论文"
    safe = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    return (safe[:50] or "医学论文")


def _output_path(session) -> Path:
    return OUTPUT_DIR / f"{_safe_title(session)}_{session.session_id[:8]}.docx"


def _generate_docx(session, language: str, ref_style: str, progress_callback=None):
    """统一的文档生成入口，返回 (路径, 生成结果)"""
    from core.document_generator import DocumentGenerator

    generator = DocumentGenerator()
    if progress_callback:
        generator.set_progress_callback(progress_callback)

    output_path = _output_path(session)
    result = generator.generate_paper(
        session=session,
        output_path=str(output_path),
        language=language,
        ref_style=ref_style,
    )
    return output_path, result


def _manuscript_text(session) -> str:
    """把稿件正文拼成纯文本，供规范完整性与占位符检查"""
    parts = [session.research_topic or "", session.research_question or ""]
    if session.outline:
        for node in session.iter_outline_nodes():
            parts.append(node.title or "")
            parts.append(node.content_zh or node.content_en or "")
    else:
        for section in session.sections:
            parts.append(section.get("chapter") or section.get("title") or "")
            parts.append(section.get("content_zh") or section.get("content") or "")
    return "\n".join(part for part in parts if part)


@router.post("/docx")
async def export_to_docx(
    session_id: str = Form(...),
    language: str = Form("中文"),
    ref_style: str = Form("vancouver")
):
    """
    导出为Word文档

    Returns:
        文件路径 + warnings（缺失内容/未审核章节）+ 质量统计
    """
    logger.info("[routes_export] export_to_docx called", session_id=session_id,
                language=language, ref_style=ref_style)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_export] session not found", session_id=session_id)
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)

    try:
        output_path, result = _generate_docx(session, language, ref_style)
        issues = validate_manuscript(
            session,
            guideline=GUIDELINES.get(getattr(session, "guideline_id", "")),
            full_text=_manuscript_text(session),
        )
        session.quality_issues = issues
        manager.save(session_id)

        logger.info("[routes_export] docx exported", session_id=session_id,
                    output_path=str(output_path), warnings=len(result["warnings"]))

        return JSONResponse({
            "success": True,
            "message": "文档导出成功",
            "file_path": str(output_path),
            "file_name": f"{_safe_title(session)}.docx",
            "warnings": result["warnings"],
            "sections_written": result["sections_written"],
            "empty_sections": result["empty_sections"],
            "references": result["references"],
            "quality": summarize(issues),
            "quality_issues": issues,
        })

    except Exception as e:
        logger.error("[routes_export] docx export failed", session_id=session_id, error=str(e), exc_info=True)
        return JSONResponse({"success": False, "message": f"导出失败: {str(e)}"}, status_code=500)


@router.get("/download/{session_id}")
async def download_document(
    session_id: str,
    language: str = "中文",
    ref_style: str = "vancouver"
):
    """下载Word文档"""
    logger.info("[routes_export] download_document called", session_id=session_id,
                language=language, ref_style=ref_style)

    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)

    try:
        output_path, _ = _generate_docx(session, language, ref_style)
        return FileResponse(
            path=str(output_path),
            filename=f"{_safe_title(session)}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        logger.error("[routes_export] download failed", session_id=session_id, error=str(e), exc_info=True)
        return JSONResponse({"success": False, "message": f"导出失败: {str(e)}"}, status_code=500)


@router.get("/ref/styles")
async def get_reference_styles():
    """获取支持的参考文献格式"""
    return JSONResponse({"success": True, "styles": ReferenceFormatter.SUPPORTED_STYLES})


@router.post("/preview/references")
async def preview_references(
    references: str = Form(...),
    style: str = Form("vancouver")
):
    """预览参考文献格式化效果（自动适配 Hunter/PubMed 字段）"""
    try:
        ref_list = json.loads(references)
        if isinstance(ref_list, dict):
            ref_list = [ref_list]
        if not isinstance(ref_list, list):
            raise ValueError("references 必须是数组")
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"success": False, "message": "参考文献格式错误"}, status_code=400)

    formatter = ReferenceFormatter(style)
    formatted = formatter.format_references(ref_list)
    return JSONResponse({"success": True, "formatted": formatted, "style": style,
                         "count": len(formatted)})


@router.post("/references/{session_id}")
async def add_references(
    session_id: str,
    references: str = Form(...)
):
    """向会话导入结构化参考文献条目（Hunter → Writer 的接入点）

    Args:
        references: JSON 数组字符串。字段可为 PubMed/Hunter 原始字段
            （pub_date / journal_title / 作者对象列表），导入时统一规范化。
    """
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)

    try:
        payload = json.loads(references)
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"success": False, "message": "参考文献格式错误"}, status_code=400)

    added = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        normalized = normalize_reference(item)
        if not normalized.get("title"):
            continue
        added.append(normalized)

    session.references.extend(added)
    manager.save(session_id)

    logger.info("[routes_export] references imported", session_id=session_id, added=len(added))
    return JSONResponse({
        "success": True,
        "added": len(added),
        "total": len(session.references),
        "skipped": len(payload) - len(added),
        "references": session.references,
    })


@router.get("/references/{session_id}")
async def list_references(session_id: str):
    """列出已导入的参考文献条目"""
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)
    return JSONResponse({"success": True, "total": len(session.references),
                         "references": session.references})


@router.delete("/references/{session_id}/{index}")
async def delete_reference(session_id: str, index: int):
    """删除指定参考文献条目（按 0 基索引）"""
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)
    if index < 0 or index >= len(session.references):
        return JSONResponse({"success": False, "message": "索引越界"}, status_code=404)

    removed = session.references.pop(index)
    manager.save(session_id)
    return JSONResponse({"success": True, "removed": removed, "total": len(session.references)})


@router.get("/quality/{session_id}")
async def quality_report(
    session_id: str,
    ref_style: str = "vancouver"
):
    """导出前质量报告：确定性校验 + 报告规范完整性（不生成 docx）"""
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)

    guideline = GUIDELINES.get(getattr(session, "guideline_id", ""))
    issues = validate_manuscript(session, guideline=guideline, full_text=_manuscript_text(session))
    session.quality_issues = issues
    manager.save(session_id)

    return JSONResponse({
        "success": True,
        "guideline": guideline.to_dict() if guideline else None,
        "summary": summarize(issues),
        "issues": issues,
        "references": len(session.references),
    })


@router.get("/download/progress/{session_id}")
async def download_document_with_progress(
    session_id: str,
    language: str = "中文",
    ref_style: str = "vancouver"
):
    """下载Word文档（带实时进度推送）

    注意：SSE 的 data 行必须是单行 JSON，不能把多行 f-string 直接拼进去
    （旧实现在 Python 3.11 下直接 SyntaxError，导致整个应用无法导入）。
    """
    logger.info("[routes_export] download_document_with_progress called", session_id=session_id,
                language=language, ref_style=ref_style)

    async def generate():
        session = manager.get_session(session_id)
        if not session:
            yield f"data: {json.dumps({'type': 'error', 'message': '会话不存在'})}\n\n"
            return

        progress_queue: queue.Queue = queue.Queue()
        holder: dict = {}

        def progress_callback(message, progress):
            progress_queue.put({"message": message, "progress": progress})

        try:
            def generate_paper_sync():
                _, result = _generate_docx(session, language, ref_style, progress_callback)
                holder["result"] = result

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, generate_paper_sync)

            while not progress_queue.empty():
                progress = progress_queue.get()
                payload = json.dumps({
                    "type": "progress",
                    "message": progress["message"],
                    "progress": progress["progress"],
                }, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.05)

            # 导出后立刻跑一次确定性校验，把"缺内容/未审核/规范缺项"一并返回
            issues = validate_manuscript(
                session,
                guideline=GUIDELINES.get(getattr(session, "guideline_id", "")),
                full_text=_manuscript_text(session),
            )
            session.quality_issues = issues
            manager.save(session_id)

            complete = {
                "type": "complete",
                "message": "文档生成完成",
                "progress": 100,
                "file_path": f"/api/export/download/{session_id}?language={language}&ref_style={ref_style}",
                "warnings": holder.get("result", {}).get("warnings", []),
                "quality": summarize(issues),
                "quality_issues": issues,
            }
            yield f"data: {json.dumps(complete, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("[routes_export] download with progress failed", session_id=session_id,
                         error=str(e), exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': f'导出失败: {str(e)}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
