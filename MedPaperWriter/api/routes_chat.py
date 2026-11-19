"""
对话交互路由
处理综述模式和RCT模式的对话交互
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
import re
import json
import asyncio

from services.session_manager import manager, SessionMode, OutlineNode
from core.llm_client import LLMClient, LLMError
from core.expert_factory import ExpertFactory
from core.reporting_guidelines import GUIDELINES, list_guidelines, resolve
from services.writing import (
    select_reference_materials,
    write_outline_section,
    write_rct_section,
)
from services.logger import logger
from config.settings import settings

router = APIRouter()


def build_qa_context(session_id: str) -> str:
    """构建追问上下文"""
    qa_context = manager.get_qa_context(session_id)
    if not qa_context:
        return "暂无信息"

    context_str = []
    for item in qa_context[-10:]:  # 最近10轮对话
        role = "用户" if item["role"] == "user" else "AI"
        context_str.append(f"{role}: {item['content']}")

    return "\n".join(context_str)


def parse_outline(outline_text: str) -> OutlineNode:
    """解析提纲文本为树结构"""
    lines = outline_text.strip().split("\n")
    root = OutlineNode(0, "论文提纲")

    stack = [(root, 0)]  # (节点, 层级)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 编号兼容三种写法："1. 摘要"、"2.1 研究对象"（无尾点）、"2.1. 研究对象"
        # 旧正则要求编号后必须紧跟句点，导致 "2.1 研究对象" 被解析成
        # 一级标题 "1 研究对象"，整棵提纲的层级与父子关系错乱。
        match = re.match(r'^(\d+(?:\.\d+)*)\.?\s+(.+)$', line)
        if match:
            level = len(match.group(1).split("."))
            title = match.group(2).strip()

            new_node = OutlineNode(level, title)

            while stack and stack[-1][1] >= level:
                stack.pop()

            if stack:
                new_node.parent = stack[-1][0]
                stack[-1][0].children.append(new_node)

            stack.append((new_node, level))

    return root


def merge_outline_state(new_root: OutlineNode, old_root: Optional[OutlineNode]) -> OutlineNode:
    """把旧提纲的正文、状态、版本历史按"层级 + 标题"继承到新提纲

    设计依据：审查报告 3.1 节。重新生成或修改提纲要重新解析文本，
    若直接替换整棵树，节点 id 会全部变化，已写好的正文、审核状态和修订
    历史都会丢失（前端还持有旧 id，写入直接 404）。这里按标题做一次
    确定性合并，命中则复用旧 id 与内容。
    """
    if not old_root:
        return new_root

    def walk(node: OutlineNode):
        yield node
        for child in node.children:
            yield from walk(child)

    index: dict = {}
    for node in walk(old_root):
        index.setdefault((node.level, node.title.strip()), []).append(node)

    for node in walk(new_root):
        if node.level == 0:
            continue
        candidates = index.get((node.level, node.title.strip()))
        if not candidates:
            continue
        old = candidates.pop(0)
        node.id = old.id
        node.title_en = old.title_en
        node.content_zh = old.content_zh
        node.content_en = old.content_en
        node.status = old.status
        node.feedback = old.feedback
        node.revisions = old.revisions
        node.versions = old.versions
        node.quality_issues = old.quality_issues
        node.updated_at = old.updated_at

    return new_root


@router.post("/qa/stream")
async def qa_chat_stream(
    session_id: str = Form(...),
    message: str = Form(...),
    clear_context: bool = Form(False)
):
    """
    综述模式 - 漏斗式追问对话（流式输出）

    Args:
        session_id: 会话ID
        message: 用户消息
        clear_context: 是否清除上下文

    Returns:
        SSE流式响应
    """
    logger.info(f"[routes_chat] qa_chat_stream called", session_id=session_id, message_length=len(message), clear_context=clear_context)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if clear_context:
        session.qa_context = []
        logger.debug(f"[routes_chat] qa_context cleared", session_id=session_id)

    manager.add_qa_context(session_id, "user", message)
    context = build_qa_context(session_id)
    logger.debug(f"[routes_chat] user message added to context", session_id=session_id, context_length=len(context))

    llm = LLMClient()

    async def generate():
        try:
            logger.debug(f"[routes_chat] starting stream generation", session_id=session_id)
            # 发送开始标记
            yield f"data: {json.dumps({'type': 'start'})}\n\n"

            # 调用流式API
            stream_gen, _ = llm.chat(
                messages=[
                    {"role": "system", "content": ExpertFactory.get_qa_expert_prompt(
                        progress="漏斗式追问进行中",
                        collected_info=context
                    )},
                    {"role": "user", "content": f"用户最新回复：{message}\n\n请继续追问或总结研究问题。"}
                ],
                temperature=0.8,
                max_tokens=2000,
                stream=True
            )

            full_response = ""
            for chunk in stream_gen:
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    await asyncio.sleep(0.01)  # 避免过快刷新

            # 保存上下文
            manager.add_qa_context(session_id, "assistant", full_response)
            manager.update_token_usage(session_id, llm.token_usage.total_tokens)
            logger.info(f"[routes_chat] stream completed", session_id=session_id, response_length=len(full_response), total_tokens=llm.token_usage.total_tokens)

            # 发送结束标记
            yield f"data: {json.dumps({'type': 'done', 'total_tokens': session.total_tokens})}\n\n"

        except Exception as e:
            logger.error(f"[routes_chat] stream error", session_id=session_id, error=str(e), exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/qa")
async def qa_chat(
    session_id: str = Form(...),
    message: str = Form(...),
    clear_context: bool = Form(False)
):
    """
    综述模式 - 漏斗式追问对话

    Args:
        session_id: 会话ID
        message: 用户消息
        clear_context: 是否清除上下文

    Returns:
        AI回复和Token使用信息
    """
    logger.info(f"[routes_chat] qa_chat called", session_id=session_id, message_length=len(message), clear_context=clear_context)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if clear_context:
        session.qa_context = []
        logger.debug(f"[routes_chat] qa_context cleared", session_id=session_id)

    manager.add_qa_context(session_id, "user", message)
    logger.debug(f"[routes_chat] user message added", session_id=session_id)

    context = build_qa_context(session_id)

    llm = LLMClient()

    try:
        logger.debug(f"[routes_chat] calling LLM for QA response", session_id=session_id)
        response, usage = llm.generate(
            prompt=f"用户最新回复：{message}\n\n请继续追问或总结研究问题。",
            system_prompt=ExpertFactory.get_qa_expert_prompt(
                progress="漏斗式追问进行中",
                collected_info=context
            ),
            temperature=0.8,
            max_tokens=2000
        )

        manager.add_qa_context(session_id, "assistant", response)
        manager.update_token_usage(session_id, usage["total_tokens"])
        logger.info(f"[routes_chat] qa_chat completed", session_id=session_id, response_length=len(response), token_usage=usage)

        return JSONResponse({
            "success": True,
            "message": response,
            "qa_context": session.qa_context[-5:],
            "token_usage": usage,
            "total_tokens": session.total_tokens
        })

    except LLMError as e:
        logger.error(f"[routes_chat] qa_chat LLM error", session_id=session_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": f"AI回复失败: {str(e)}"
        }, status_code=500)


@router.post("/confirm/question")
async def confirm_research_question(
    session_id: str = Form(...),
    question: str = Form(...)
):
    """
    确认研究问题

    Args:
        session_id: 会话ID
        question: 确定的研究问题

    Returns:
        确认结果
    """
    logger.info(f"[routes_chat] confirm_research_question called", session_id=session_id, question_length=len(question))

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    manager.set_research_question(session_id, question)
    logger.info(f"[routes_chat] research question confirmed", session_id=session_id, question=question[:100])

    return JSONResponse({
        "success": True,
        "message": "研究问题已确认",
        "research_question": question
    })


def build_references_text(session, section_title: str = "", section_kind: str = "") -> str:
    """构建参考资料文本（按章节检索，而非整包灌入）

    旧实现把全部参考资料拼成一段塞进每个章节，既浪费上下文，也让模型
    在不同章节间串用证据。现在按章节标题与关键词挑最相关的材料。

    Args:
        session: 会话对象
        section_title: 当前章节标题（用于检索）
        section_kind: 章节类型（methods/results/...）

    Returns:
        与本节最相关的参考资料片段
    """
    if not session.reference_materials:
        return ""
    budget = int(getattr(settings, "CONTEXT_CHAR_BUDGET", 12000) * 0.5)
    text, stats = select_reference_materials(
        session,
        section_title or session.research_question or session.research_topic,
        section_kind,
        budget,
    )
    logger.debug(
        "[routes_chat] reference selection",
        total=stats.get("total"),
        selected=stats.get("selected"),
        chars=stats.get("chars"),
    )
    return text


@router.get("/guidelines")
async def get_reporting_guidelines():
    """获取可选的报告规范规则包（供前端研究类型选择）"""
    return JSONResponse({"success": True, "guidelines": list_guidelines()})


@router.post("/outline/generate")
async def generate_outline(
    session_id: str = Form(...),
    study_type: str = Form(""),
    guideline_id: str = Form("")
):
    """
    生成论文提纲

    Args:
        session_id: 会话ID
        study_type: 研究类型（用于路由报告规范）
        guideline_id: 显式指定报告规范（优先于 study_type）

    Returns:
        生成的提纲 + 实际采用的报告规范
    """
    logger.info("[routes_chat] generate_outline called", session_id=session_id,
                study_type=study_type, guideline_id=guideline_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    # 未显式传入时沿用会话里已保存的研究类型；RCT 模式默认 CONSORT
    resolved_type = study_type or session.study_type or ("RCT" if session.mode == SessionMode.RCT else "综述")
    guideline, note = resolve(resolved_type)
    if guideline_id and guideline_id in {g["id"] for g in list_guidelines()}:
        from core.reporting_guidelines import GUIDELINES
        guideline = GUIDELINES[guideline_id]
        note = ""

    llm = LLMClient()

    try:
        reference_text = build_references_text(session)
        logger.debug("[routes_chat] generating outline with references", session_id=session_id,
                     ref_length=len(reference_text), guideline=guideline.id)

        outline_text, usage = llm.generate(
            prompt="",
            system_prompt=ExpertFactory.get_outline_expert_prompt(
                research_question=session.research_question or session.research_topic,
                study_type=resolved_type,
                reference_materials=reference_text,
                guideline_id=guideline.id,
            ),
            temperature=0.7,
            max_tokens=3000
        )

        manager.update_token_usage(session_id, usage["total_tokens"])
        logger.debug("[routes_chat] outline generated", session_id=session_id, outline_length=len(outline_text))

        outline = merge_outline_state(parse_outline(outline_text), session.outline)
        manager.set_outline(session_id, outline)

        # 记录规范路由结果，导出前的完整性检查会用到
        session.study_type = resolved_type
        session.guideline_id = guideline.id
        session.guideline_note = note
        manager.save(session_id)

        logger.info("[routes_chat] outline generated and saved", session_id=session_id,
                    guideline=guideline.id, token_usage=usage)

        return JSONResponse({
            "success": True,
            "outline": outline.to_dict(),
            "outline_text": outline_text,
            "guideline": guideline.to_dict(),
            "guideline_note": note,
            "token_usage": usage
        })

    except LLMError as e:
        logger.error("[routes_chat] outline generation failed", session_id=session_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": f"提纲生成失败: {str(e)}"
        }, status_code=500)


@router.post("/outline/modify")
async def modify_outline(
    session_id: str = Form(...),
    outline_text: str = Form(...)
):
    """
    修改提纲

    Args:
        session_id: 会话ID
        outline_text: 修改后的提纲文本

    Returns:
        更新后的提纲
    """
    logger.info(f"[routes_chat] modify_outline called", session_id=session_id, outline_length=len(outline_text))

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    try:
        outline = merge_outline_state(parse_outline(outline_text), session.outline)
        manager.set_outline(session_id, outline)
        logger.info(f"[routes_chat] outline modified", session_id=session_id)

        return JSONResponse({
            "success": True,
            "outline": outline.to_dict(),
            "message": "提纲已更新"
        })

    except Exception as e:
        logger.error(f"[routes_chat] outline modification failed", session_id=session_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": f"提纲解析失败: {str(e)}"
        }, status_code=500)


@router.post("/outline/confirm")
async def confirm_outline(
    session_id: str = Form(...)
):
    """
    确认提纲

    Args:
        session_id: 会话ID

    Returns:
        确认结果
    """
    logger.info(f"[routes_chat] confirm_outline called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    manager.confirm_outline(session_id)
    logger.info(f"[routes_chat] outline confirmed", session_id=session_id)

    return JSONResponse({
        "success": True,
        "message": "提纲已确认，开始撰写正文"
    })


@router.post("/section/write")
async def write_section(
    session_id: str = Form(...),
    section_id: str = Form(...),
    language: str = Form("中文"),
    feedback: str = Form("")
):
    """
    撰写章节内容（feedback 非空时进入修订模式）

    Args:
        session_id: 会话ID
        section_id: 章节ID
        language: 写作语言
        feedback: 修订意见（可选）。传入时保留旧稿、按意见重写并返回差异

    Returns:
        正文、版本号、与上一稿的差异、确定性校验结果
    """
    logger.info("[routes_chat] write_section called", session_id=session_id,
                section_id=section_id, language=language, has_feedback=bool(feedback))

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if not session.outline:
        logger.warning("[routes_chat] no outline found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "请先生成提纲"
        }, status_code=400)

    section_node = find_section_by_id(session.outline, section_id)
    if not section_node:
        logger.warning("[routes_chat] section not found", session_id=session_id, section_id=section_id)
        return JSONResponse({
            "success": False,
            "message": "章节不存在"
        }, status_code=404)

    # 修订必须基于已有正文，否则退回普通撰写（否则会把空稿当旧稿，产生空 diff）
    if feedback and not (section_node.content_zh or section_node.content_en):
        return JSONResponse({
            "success": False,
            "message": "该章节尚无正文，无法提交修订意见；请先撰写本章"
        }, status_code=400)

    try:
        result = write_outline_section(session, section_node, language=language, feedback=feedback)
    except ValueError as e:
        logger.warning("[routes_chat] invalid content generated", session_id=session_id,
                       section_id=section_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=400)
    except LLMError as e:
        logger.error("[routes_chat] section write failed", session_id=session_id,
                     section_id=section_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": f"内容撰写失败: {str(e)}"
        }, status_code=500)

    logger.info("[routes_chat] section write completed", session_id=session_id,
                section_id=section_id, version=result["version"],
                revision=result["revision"], quality_issues=len(result["quality"]))

    return JSONResponse({
        "success": True,
        "section_id": section_id,
        "content": result["content"],
        "version": result["version"],
        "diff": result["diff"],
        "quality": result["quality"],
        "revision": result["revision"],
        "section_kind": result["section_kind"],
        "token_usage": result["usage"],
        "total_tokens": session.total_tokens
    })

def find_section_by_id(node: OutlineNode, target_id: str) -> Optional[OutlineNode]:
    """根据ID查找章节节点"""
    if node.id == target_id:
        return node

    for child in node.children:
        result = find_section_by_id(child, target_id)
        if result:
            return result

    return None


@router.post("/rct/write")
async def write_rct_chapter(
    session_id: str = Form(...),
    chapter: str = Form(...),
    language: str = Form("中文"),
    revision_feedback: str = Form("")
):
    """
    RCT模式 - 撰写章节内容（revision_feedback 非空时进入修订模式）

    Args:
        session_id: 会话ID
        chapter: 章节名称 (Introduction/Methods/Results/Discussion/Conclusions)
        language: 写作语言
        revision_feedback: 修订反馈（可选）

    Returns:
        正文、版本号、与上一稿的差异、确定性校验结果
    """
    logger.info("[routes_chat] write_rct_chapter called", session_id=session_id, chapter=chapter,
                language=language, has_revision=bool(revision_feedback))

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if session.mode != SessionMode.RCT:
        logger.warning("[routes_chat] wrong mode for rct write", session_id=session_id, mode=session.mode.value)
        return JSONResponse({
            "success": False,
            "message": "此操作仅适用于RCT模式"
        }, status_code=400)

    entry = session.rct_section(chapter)
    if revision_feedback and not (entry and (entry.get("content_zh") or entry.get("content"))):
        return JSONResponse({
            "success": False,
            "message": f"{chapter} 章节尚无正文，无法提交修订意见；请先撰写本章"
        }, status_code=400)

    try:
        result = write_rct_section(session, chapter, language=language, feedback=revision_feedback)
    except ValueError as e:
        logger.warning("[routes_chat] invalid RCT content", session_id=session_id, chapter=chapter, error=str(e))
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=400)
    except LLMError as e:
        logger.error("[routes_chat] RCT chapter write failed", session_id=session_id, chapter=chapter, error=str(e))
        return JSONResponse({
            "success": False,
            "message": f"内容撰写失败: {str(e)}"
        }, status_code=500)

    logger.info("[routes_chat] RCT chapter write completed", session_id=session_id, chapter=chapter,
                version=result["version"], revision=result["revision"])

    return JSONResponse({
        "success": True,
        "chapter": chapter,
        "content": result["content"],
        "version": result["version"],
        "diff": result["diff"],
        "quality": result["quality"],
        "revision": result["revision"],
        "section_kind": result["section_kind"],
        "token_usage": result["usage"],
        "total_tokens": session.total_tokens
    })


@router.post("/rct/approve")
async def approve_rct_chapter(
    session_id: str = Form(...),
    chapter: str = Form(...)
):
    """
    RCT模式 - 审核通过章节

    Args:
        session_id: 会话ID
        chapter: 章节名称

    Returns:
        审核结果
    """
    logger.info("[routes_chat] approve_rct_chapter called", session_id=session_id, chapter=chapter)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    chapter_entry = session.rct_section(chapter)
    if not chapter_entry:
        return JSONResponse({
            "success": False,
            "message": f"{chapter} 章节不存在或无正文"
        }, status_code=404)

    chapter_entry["status"] = "approved"
    chapter_entry["approved_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    # 审核状态必须落盘，否则重启后回到"待审核"
    manager.save(session_id)

    logger.info("[routes_chat] RCT chapter approval completed", session_id=session_id, chapter=chapter)
    return JSONResponse({
        "success": True,
        "message": f"{chapter} 章节已审核通过",
        "chapter": chapter,
        "status": "approved"
    })


@router.post("/rct/revision")
async def revise_rct_chapter(
    session_id: str = Form(...),
    chapter: str = Form(...),
    feedback: str = Form(...),
    regenerate: bool = Form(True)
):
    """
    RCT模式 - 提交修订意见并生成新版本

    设计依据：审查报告 3.1 节。旧实现只把意见记在会话里、等前端另发一次
    写作请求，导致"提交了意见但稿子没变"。现在一次调用完成：
        记录意见 → 保留旧稿 → 生成新稿 → 返回差异 → 回到待审核

    Args:
        session_id: 会话ID
        chapter: 章节名称
        feedback: 修订意见
        regenerate: 是否立即重新生成（默认 True）

    Returns:
        修订后的正文、版本、差异
    """
    logger.info("[routes_chat] revise_rct_chapter called", session_id=session_id,
                chapter=chapter, feedback_length=len(feedback), regenerate=regenerate)

    session = manager.get_session(session_id)
    if not session:
        logger.warning("[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    chapter_entry = session.rct_section(chapter)
    if not chapter_entry:
        return JSONResponse({
            "success": False,
            "message": f"{chapter} 章节不存在或无正文"
        }, status_code=404)

    chapter_entry.setdefault("revisions", []).append({
        "feedback": feedback,
        "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "status": "pending_regeneration",
    })
    chapter_entry["status"] = "revision"
    chapter_entry["feedback"] = feedback
    manager.save(session_id)

    if not regenerate:
        return JSONResponse({
            "success": True,
            "message": "修订意见已记录",
            "chapter": chapter,
            "regenerated": False
        })

    try:
        result = write_rct_section(session, chapter, feedback=feedback)
    except (LLMError, ValueError) as e:
        logger.error("[routes_chat] RCT revision regeneration failed", session_id=session_id,
                     chapter=chapter, error=str(e))
        # 意见已保存，稿件仍是旧版——明确告知，避免用户误以为已修改
        return JSONResponse({
            "success": False,
            "message": f"修订意见已保存，但重新生成失败：{str(e)}",
            "feedback_saved": True,
            "chapter": chapter
        }, status_code=500)

    return JSONResponse({
        "success": True,
        "message": "已按修订意见生成新版本",
        "chapter": chapter,
        "regenerated": True,
        "content": result["content"],
        "version": result["version"],
        "diff": result["diff"],
        "quality": result["quality"]
    })
@router.get("/status")
async def get_chat_status(
    session_id: str
):
    """
    获取会话状态

    Args:
        session_id: 会话ID

    Returns:
        会话状态信息
    """
    logger.debug(f"[routes_chat] get_chat_status called", session_id=session_id)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    logger.debug(f"[routes_chat] status retrieved", session_id=session_id, status=session.status)
    return JSONResponse({
        "success": True,
        "status": session.status,
        "mode": session.mode.value,
        "research_topic": session.research_topic,
        "research_question": session.research_question,
        "outline_confirmed": session.outline_confirmed,
        "total_tokens": session.total_tokens
    })
