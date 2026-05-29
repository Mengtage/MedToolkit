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
from llm.client import LLMClient, ExpertFactory, LLMError

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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if clear_context:
        session.qa_context = []

    manager.add_qa_context(session_id, "user", message)
    context = build_qa_context(session_id)

    llm = LLMClient()

    async def generate():
        try:
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

            # 发送结束标记
            yield f"data: {json.dumps({'type': 'done', 'total_tokens': session.total_tokens})}\n\n"

        except Exception as e:
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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if clear_context:
        session.qa_context = []

    manager.add_qa_context(session_id, "user", message)

    context = build_qa_context(session_id)

    llm = LLMClient()

    try:
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

        return JSONResponse({
            "success": True,
            "message": response,
            "qa_context": session.qa_context[-5:],
            "token_usage": usage,
            "total_tokens": session.total_tokens
        })

    except LLMError as e:
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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    manager.set_research_question(session_id, question)

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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    llm = LLMClient()

    try:
        reference_text = build_references_text(session)
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

        outline = parse_outline(outline_text)
        manager.set_outline(session_id, outline)

        return JSONResponse({
            "success": True,
            "outline": outline.to_dict(),
            "outline_text": outline_text,
            "token_usage": usage
        })

    except LLMError as e:
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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    try:
        outline = parse_outline(outline_text)
        manager.set_outline(session_id, outline)

        return JSONResponse({
            "success": True,
            "outline": outline.to_dict(),
            "message": "提纲已更新"
        })

    except Exception as e:
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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    manager.confirm_outline(session_id)

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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    if not session.outline:
        return JSONResponse({
            "success": False,
            "message": "请先生成提纲"
        }, status_code=400)

    section_node = find_section_by_id(session.outline, section_id)
    if not section_node:
        return JSONResponse({
            "success": False,
            "message": "章节不存在"
        }, status_code=404)

    llm = LLMClient()

    try:
        reference_text = build_references_text(session)
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

        section_node.content_zh = content

        manager.update_token_usage(session_id, usage["total_tokens"])

        return JSONResponse({
            "success": True,
            "section_id": section_id,
            "content": content,
            "token_usage": usage,
            "total_tokens": session.total_tokens
        })

    except LLMError as e:
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
    language: str = Form("中文")
):
    """
    RCT模式 - 撰写章节内容

    Args:
        session_id: 会话ID
        chapter: 章节名称 (Introduction/Methods/Results/Discussion/Conclusions)
        language: 写作语言

    Returns:
        撰写的内容
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

    llm = LLMClient()

    try:
        study_info = f"研究方案：\n{session.protocol_text[:2000]}" if session.protocol_text else "暂无研究方案"
        analysis_results = f"统计分析结果：\n{session.analysis_text[:2000]}" if session.analysis_text else "暂无分析结果"

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

        manager.update_token_usage(session_id, usage["total_tokens"])

        # 更新章节内容
        session.current_chapter = chapter
        chapter_entry = next((s for s in session.sections if s.get("chapter") == chapter), None)
        if chapter_entry:
            chapter_entry["content"] = content
            chapter_entry["status"] = "pending_review"
        else:
            session.sections.append({
                "chapter": chapter,
                "content": content,
                "status": "pending_review"
            })

        return JSONResponse({
            "success": True,
            "chapter": chapter,
            "content": content,
            "token_usage": usage,
            "total_tokens": session.total_tokens
        })

    except LLMError as e:
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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    chapter_entry = next((s for s in session.sections if s.get("chapter") == chapter), None)
    if chapter_entry:
        chapter_entry["status"] = "approved"

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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    chapter_entry = next((s for s in session.sections if s.get("chapter") == chapter), None)
    if chapter_entry:
        chapter_entry["status"] = "revision"
        chapter_entry.setdefault("revisions", []).append(feedback)

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
    session = manager.get_session(session_id)
    if not session:
        return JSONResponse({
            "success": False,
            "message": "会话不存在"
        }, status_code=404)

    return JSONResponse({
        "success": True,
        "status": session.status,
        "mode": session.mode.value,
        "research_topic": session.research_topic,
        "research_question": session.research_question,
        "outline_confirmed": session.outline_confirmed,
        "total_tokens": session.total_tokens
    })
