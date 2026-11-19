"""
对话交互路由
处理综述模式和RCT模式的对话交互
"""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
import re
import json
import asyncio

from services.session_manager import manager, SessionMode, OutlineNode
from core.llm_client import LLMClient, LLMError
from core.expert_factory import ExpertFactory
from core.content_cleaner import cleaner
from services.logger import logger

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

        match = re.match(r'^(\d+(?:\.\d+)*)\.\s*(.+)$', line)
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


def build_references_text(session) -> str:
    """
    构建参考资料文本
    
    Args:
        session: 会话对象
        
    Returns:
        格式化的参考资料文本
    """
    if not session.reference_materials:
        return ""
    
    references = []
    for i, ref in enumerate(session.reference_materials, 1):
        references.append(f"--- 参考资料 {i}: {ref['filename']} ---\n{ref['content']}")
    
    return "\n\n".join(references)


@router.post("/outline/generate")
async def generate_outline(
    session_id: str = Form(...),
    study_type: str = Form("综述")
):
    """
    生成论文提纲

    Args:
        session_id: 会话ID
        study_type: 研究类型

    Returns:
        生成的提纲
    """
    logger.info(f"[routes_chat] generate_outline called", session_id=session_id, study_type=study_type)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    llm = LLMClient()

    try:
        reference_text = build_references_text(session)
        logger.debug(f"[routes_chat] generating outline with references", session_id=session_id, ref_length=len(reference_text))

        outline_text, usage = llm.generate(
            prompt="",
            system_prompt=ExpertFactory.get_outline_expert_prompt(
                research_question=session.research_question or session.research_topic,
                study_type=study_type,
                reference_materials=reference_text
            ),
            temperature=0.7,
            max_tokens=3000
        )

        manager.update_token_usage(session_id, usage["total_tokens"])
        logger.debug(f"[routes_chat] outline generated", session_id=session_id, outline_length=len(outline_text))

        outline = parse_outline(outline_text)
        manager.set_outline(session_id, outline)
        logger.info(f"[routes_chat] outline generated and saved", session_id=session_id, token_usage=usage)

        return JSONResponse({
            "success": True,
            "outline": outline.to_dict(),
            "outline_text": outline_text,
            "token_usage": usage
        })

    except LLMError as e:
        logger.error(f"[routes_chat] outline generation failed", session_id=session_id, error=str(e))
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
        outline = parse_outline(outline_text)
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
    language: str = Form("中文")
):
    """
    撰写章节内容

    Args:
        session_id: 会话ID
        section_id: 章节ID
        language: 写作语言

    Returns:
        撰写的内容
    """
    logger.info(f"[routes_chat] write_section called", session_id=session_id, section_id=section_id, language=language)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if not session.outline:
        logger.warning(f"[routes_chat] no outline found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "请先生成提纲"
        }, status_code=400)

    section_node = find_section_by_id(session.outline, section_id)
    if not section_node:
        logger.warning(f"[routes_chat] section not found", session_id=session_id, section_id=section_id)
        return JSONResponse({
            "success": False,
            "message": "章节不存在"
        }, status_code=404)

    llm = LLMClient()

    try:
        reference_text = build_references_text(session)
        logger.debug(f"[routes_chat] writing section", session_id=session_id, section_id=section_id, section_title=section_node.title)

        content, usage = llm.generate(
            prompt="",
            system_prompt=ExpertFactory.get_writer_expert_prompt(
                chapter_name=section_node.title,
                language=language,
                background=session.research_question,
                outline=build_outline_text(session.outline),
                section_title=section_node.title,
                reference_materials=reference_text
            ),
            temperature=0.3,
            max_tokens=3000
        )

        # 清洗内容
        cleaned_content = cleaner.clean_content(content)
        if not cleaner.is_valid_content(cleaned_content):
            logger.warning(f"[routes_chat] invalid content detected", session_id=session_id, section_id=section_id, original_length=len(content))
            return JSONResponse({
                "success": False,
                "message": "生成的内容无效，请检查参考资料是否完整"
            }, status_code=400)

        section_node.content_zh = cleaned_content
        logger.debug(f"[routes_chat] section content generated and cleaned", session_id=session_id, section_id=section_id, original_length=len(content), cleaned_length=len(cleaned_content))

        manager.update_token_usage(session_id, usage["total_tokens"])
        logger.info(f"[routes_chat] section write completed", session_id=session_id, section_id=section_id, token_usage=usage)

        return JSONResponse({
            "success": True,
            "section_id": section_id,
            "content": content,
            "token_usage": usage,
            "total_tokens": session.total_tokens
        })

    except LLMError as e:
        logger.error(f"[routes_chat] section write failed", session_id=session_id, section_id=section_id, error=str(e))
        return JSONResponse({
            "success": False,
            "message": f"内容撰写失败: {str(e)}"
        }, status_code=500)


def find_section_by_id(node: OutlineNode, target_id: str) -> Optional[OutlineNode]:
    """根据ID查找章节节点"""
    if node.id == target_id:
        return node

    for child in node.children:
        result = find_section_by_id(child, target_id)
        if result:
            return result

    return None


def build_outline_text(node: OutlineNode, prefix: str = "") -> str:
    """构建提纲文本"""
    if node.level > 0:
        lines = [f"{prefix}{node.title}"]
    else:
        lines = []

    for child in node.children:
        child_prefix = prefix if node.level == 0 else prefix
        lines.append(build_outline_text(child, child_prefix))

    return "\n".join(filter(None, lines))


@router.post("/rct/write")
async def write_rct_chapter(
    session_id: str = Form(...),
    chapter: str = Form(...),
    language: str = Form("中文"),
    revision_feedback: str = Form("")
):
    """
    RCT模式 - 撰写章节内容

    Args:
        session_id: 会话ID
        chapter: 章节名称 (Introduction/Methods/Results/Discussion/Conclusions)
        language: 写作语言
        revision_feedback: 修订反馈（可选）

    Returns:
        撰写的内容
    """
    logger.info(f"[routes_chat] write_rct_chapter called", session_id=session_id, chapter=chapter, language=language, has_revision=bool(revision_feedback))

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if session.mode != SessionMode.RCT:
        logger.warning(f"[routes_chat] wrong mode for rct write", session_id=session_id, mode=session.mode.value)
        return JSONResponse({
            "success": False,
            "message": "此操作仅适用于RCT模式"
        }, status_code=400)

    llm = LLMClient()

    try:
        study_info = f"研究方案：\n{session.protocol_text[:2000]}" if session.protocol_text else "暂无研究方案"
        analysis_results = f"统计分析结果：\n{session.analysis_text[:2000]}" if session.analysis_text else "暂无分析结果"
        
        # 获取章节的修订历史
        chapter_entry = next((s for s in session.sections if s.get("chapter") == chapter), None)
        revision_history = ""
        if chapter_entry and chapter_entry.get("revisions"):
            revision_history = "\n\n【修订意见历史】：\n" + "\n".join([f"{i+1}. {r}" for i, r in enumerate(chapter_entry["revisions"][-3:])])
        
        # 如果有新的修订反馈，添加到历史
        if revision_feedback:
            revision_history += f"\n\n【最新修订意见】：\n{revision_feedback}"
        
        if revision_history:
            analysis_results += revision_history
            logger.debug(f"[routes_chat] revision feedback added", session_id=session_id, chapter=chapter, feedback_length=len(revision_feedback))
        
        logger.debug(f"[routes_chat] writing RCT chapter", session_id=session_id, chapter=chapter, study_info_length=len(study_info), analysis_length=len(analysis_results))

        content, usage = llm.generate(
            prompt="",
            system_prompt=ExpertFactory.get_rct_writer_prompt(
                chapter=chapter,
                language=language,
                study_info=study_info,
                analysis_results=analysis_results
            ),
            temperature=0.3,
            max_tokens=3000
        )

        # 清洗内容
        cleaned_content = cleaner.clean_content(content)
        if not cleaner.is_valid_content(cleaned_content):
            logger.warning(f"[routes_chat] invalid RCT content detected", session_id=session_id, chapter=chapter, original_length=len(content))
            return JSONResponse({
                "success": False,
                "message": "生成的内容无效，请检查研究方案和统计分析结果是否完整"
            }, status_code=400)

        manager.update_token_usage(session_id, usage["total_tokens"])
        logger.debug(f"[routes_chat] RCT chapter generated and cleaned", session_id=session_id, chapter=chapter, original_length=len(content), cleaned_length=len(cleaned_content))

        # 更新章节内容
        session.current_chapter = chapter
        if chapter_entry:
            chapter_entry["content_zh"] = cleaned_content
            chapter_entry["content"] = cleaned_content  # 保持向后兼容
            chapter_entry["status"] = "pending_review"
        else:
            session.sections.append({
                "chapter": chapter,
                "content_zh": cleaned_content,
                "content": cleaned_content,  # 保持向后兼容
                "status": "pending_review"
            })

        # 保存会话
        manager._save_session(session_id)
        logger.debug(f"[routes_chat] session saved after writing chapter", session_id=session_id, chapter=chapter)

        logger.info(f"[routes_chat] RCT chapter write completed", session_id=session_id, chapter=chapter, token_usage=usage)

        return JSONResponse({
            "success": True,
            "chapter": chapter,
            "content": cleaned_content,
            "token_usage": usage,
            "total_tokens": session.total_tokens
        })

    except LLMError as e:
        logger.error(f"[routes_chat] RCT chapter write failed", session_id=session_id, chapter=chapter, error=str(e))
        return JSONResponse({
            "success": False,
            "message": f"内容撰写失败: {str(e)}"
        }, status_code=500)


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
    logger.info(f"[routes_chat] approve_rct_chapter called", session_id=session_id, chapter=chapter)

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    chapter_entry = next((s for s in session.sections if s.get("chapter") == chapter), None)
    if chapter_entry:
        chapter_entry["status"] = "approved"
        logger.debug(f"[routes_chat] RCT chapter approved", session_id=session_id, chapter=chapter)

    logger.info(f"[routes_chat] RCT chapter approval completed", session_id=session_id, chapter=chapter)
    return JSONResponse({
        "success": True,
        "message": f"{chapter} 章节已审核通过"
    })


@router.post("/rct/revision")
async def revise_rct_chapter(
    session_id: str = Form(...),
    chapter: str = Form(...),
    feedback: str = Form(...)
):
    """
    RCT模式 - 提交修订意见

    Args:
        session_id: 会话ID
        chapter: 章节名称
        feedback: 修订意见

    Returns:
        修订结果
    """
    logger.info(f"[routes_chat] revise_rct_chapter called", session_id=session_id, chapter=chapter, feedback_length=len(feedback))

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"[routes_chat] session not found", session_id=session_id)
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    chapter_entry = next((s for s in session.sections if s.get("chapter") == chapter), None)
    if chapter_entry:
        chapter_entry["status"] = "revision"
        chapter_entry.setdefault("revisions", []).append(feedback)
        logger.debug(f"[routes_chat] revision added", session_id=session_id, chapter=chapter)

    logger.info(f"[routes_chat] revision submitted", session_id=session_id, chapter=chapter)
    return JSONResponse({
        "success": True,
        "message": "修订意见已提交"
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
