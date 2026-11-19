"""
章节写作服务

设计依据：MedPaperWriter 设计审查 3.1 / 3.3 / 6.1-6.4 节

集中处理三件事，避免对话路由与审核路由各写一套导致行为漂移：
    1. 证据与上下文的**按章节检索**（不再把全部参考资料塞进每个章节，
       也不再对研究方案做硬编码 [:2000] 截断）
    2. 修订链：旧稿 → 按意见重写 → 版本留痕 → 差异返回
    3. 写作后立即执行确定性校验（引用占位、数字保真、缩写、过度表述）
"""

from __future__ import annotations

import difflib
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config.settings import settings
from core.content_cleaner import cleaner
from core.expert_factory import ExpertFactory
from core.llm_client import LLMClient
from core.validators import infer_section_kind, validate_section
from services.logger import logger
from services.session_manager import OutlineNode, SectionStatus, Session

# 统计结果/方案里优先保留的片段关键词（截断时先保这些段落）
PRIORITY_KEYWORDS = (
    "样本量", "主要结局", "次要结局", "随机", "盲法", "效应量", "置信区间",
    "p值", "P<", "P=", "OR", "RR", "HR", "均值", "标准差", "例", "不良事件",
)


def _int_setting(name: str, default: int) -> int:
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def truncate_preserving_structure(text: str, budget: int) -> str:
    """按预算截断长文本：保留开头、结尾，并优先保留含关键结构的段落。

    替代原来的 ``text[:2000]``——样本量、主要结局、效应量往往不在前 2000 字符内，
    直接从头截断会让模型"看不见"最关键的事实，进而编造。
    """
    if not text:
        return ""
    text = text.strip()
    if len(text) <= budget:
        return text

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    if not paragraphs:
        return text[:budget]

    head_budget = int(budget * 0.4)
    tail_budget = int(budget * 0.2)
    middle_budget = budget - head_budget - tail_budget

    head: List[str] = []
    used = 0
    for para in paragraphs:
        if used + len(para) > head_budget:
            break
        head.append(para)
        used += len(para) + 1

    tail: List[str] = []
    used = 0
    for para in reversed(paragraphs[len(head):]):
        remaining = tail_budget - used
        if remaining <= 0:
            break
        if len(para) > remaining:
            # 尾部段落更长时截取末尾，保证"结论/结尾"这类信息不丢
            tail.insert(0, para[-remaining:])
            break
        tail.insert(0, para)
        used += len(para) + 1

    # 中间部分按关键结构优先挑选
    middle_candidates = paragraphs[len(head): len(paragraphs) - len(tail)]
    scored = sorted(
        middle_candidates,
        key=lambda p: sum(1 for kw in PRIORITY_KEYWORDS if kw in p),
        reverse=True,
    )
    middle: List[str] = []
    used = 0
    for para in scored:
        if used + len(para) > middle_budget:
            continue
        middle.append(para)
        used += len(para) + 1

    parts = head + ["……（此处省略与本节无关的内容）……"] + middle + ["……（省略）……"] + tail
    return "\n\n".join(p for p in parts if p)


def _ngrams(text: str, size: int = 2) -> set:
    text = re.sub(r"\s+", "", text or "")
    return {text[i:i + size] for i in range(max(0, len(text) - size + 1))}


def select_reference_materials(
    session: Session,
    section_title: str,
    section_kind: str,
    budget: int,
) -> Tuple[str, Dict[str, int]]:
    """按章节检索参考资料（关键词重叠打分），返回选中文本与统计信息。

    这是对"把全部参考资料塞进每个三级章节"的替代：既省 token，也降低
    模型在不同章节间串用证据的概率。
    """
    materials = getattr(session, "reference_materials", []) or []
    if not materials:
        return "", {"total": 0, "selected": 0, "chars": 0}

    query = f"{section_title} {session.research_question} {session.research_topic}"
    query_grams = _ngrams(query)
    ranked = []
    for index, material in enumerate(materials):
        content = material.get("content", "")
        score = len(query_grams & _ngrams(content[:8000]))
        ranked.append((score, index, material))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    # 命中不足时按原始顺序补齐，保证 Methods 章节仍能看到上传的方案类材料
    selected: List[str] = []
    used = 0
    for score, _, material in ranked:
        name = material.get("filename", "未命名")
        content = material.get("content", "")
        snippet = _best_snippet(content, query_grams, max(600, budget // 2))
        block = f"--- 参考资料：{name} ---\n{snippet}"
        if used + len(block) > budget:
            continue
        selected.append(block)
        used += len(block)
        if used >= budget * 0.9:
            break

    return "\n\n".join(selected), {"total": len(materials), "selected": len(selected), "chars": used}


def _best_snippet(content: str, query_grams: set, max_chars: int) -> str:
    """取与本节最相关的一段，而不是永远取开头"""
    if len(content) <= max_chars:
        return content

    content_grams = _ngrams(content)
    if not (query_grams & content_grams):
        return content[:max_chars]

    # 以命中的首个关键词位置为中心取窗口
    for gram in query_grams:
        pos = content.find(gram)
        if pos >= 0:
            start = max(0, pos - max_chars // 3)
            return content[start:start + max_chars]
    return content[:max_chars]


def build_fact_sheet(session: Session) -> str:
    """从方案与统计结果抽取全文事实表（供跨章节一致性约束）"""
    lines: List[str] = []
    if session.research_question:
        lines.append(f"研究问题：{session.research_question}")
    if getattr(session, "guideline_id", ""):
        from core.reporting_guidelines import GUIDELINES
        guideline = GUIDELINES.get(session.guideline_id)
        if guideline:
            lines.append(f"报告规范：{guideline.name}（{guideline.applies_to}）")

    source = "\n".join(filter(None, [session.protocol_text, session.analysis_text]))
    if source:
        sizes = sorted(set(re.findall(r"(?:n\s*=\s*|共|纳入|随机(?:化)?)\s*(\d{1,5})\s*(?:例|人|名)", source)))
        if sizes:
            lines.append(f"样本量（原文表述）：{'、'.join(sizes)}")
        outcomes = re.findall(r"主要结局[：:]\s*([^\n。；]{2,40})", source)
        if outcomes:
            lines.append(f"主要结局：{outcomes[0]}")
        groups = re.findall(r"(?:试验组|对照组|干预组|观察组)[^\n。；]{0,30}", source)
        if groups:
            lines.append("组别：" + "；".join(dict.fromkeys(groups[:3])))

    return "\n".join(lines)


def build_approved_context(session: Session, exclude_id: str = "", budget: int = 3000) -> str:
    """已批准章节的要点 + 事实表，作为后续章节的强制一致性上下文"""
    limit = _int_setting("SECTION_SUMMARY_CHARS", 400)
    blocks: List[str] = []
    facts = build_fact_sheet(session)
    if facts:
        blocks.append("【全文事实表】\n" + facts)

    for node in session.approved_sections(exclude_id):
        content = (node.content_zh or node.content_en).strip().replace("\n", " ")
        if not content:
            continue
        blocks.append(f"【已批准】{node.title}：{content[:limit]}")

    if not blocks:
        return ""
    return truncate_preserving_structure("\n\n".join(blocks), budget)


def unified_diff(old: str, new: str, context_lines: int = 2) -> Dict[str, object]:
    """生成可读差异，供界面展示与修订留痕"""
    old_lines = (old or "").splitlines()
    new_lines = (new or "").splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile="上一稿", tofile="本次稿", lineterm="", n=context_lines))
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    # 差异过长时截断，避免响应体过大
    text = "\n".join(diff[:400])
    return {
        "has_changes": added > 0 or removed > 0,
        "added_lines": added,
        "removed_lines": removed,
        "unified": text,
    }


def _source_text(session: Session, section_kind: str) -> str:
    if section_kind in ("methods", "results"):
        return "\n".join(filter(None, [session.protocol_text, session.analysis_text]))
    return "\n".join(filter(None, [session.protocol_text, session.analysis_text,
                                   " ".join(m.get("content", "")[:2000] for m in session.reference_materials)]))


def _generate(
    system_prompt: str,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
) -> Tuple[str, dict]:
    llm = LLMClient()
    return llm.generate(
        prompt="",
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens or _int_setting("WRITER_MAX_TOKENS", 3000),
    )


def _resolve_section_kind(node: OutlineNode) -> str:
    """章节类型识别：先看本节标题，未命中再看父级标题

    三级标题常是「主要结局」「研究对象」「检索策略」这类子项，
    单独看标题判断不出属于结果还是方法，必须结合上一级。
    """
    kind = infer_section_kind(node.title)
    parent = node.parent
    while kind == "other" and parent is not None and parent.level > 0:
        kind = infer_section_kind(parent.title)
        parent = parent.parent
    return kind


def write_outline_section(
    session: Session,
    node: OutlineNode,
    language: str = "中文",
    feedback: str = "",
) -> Dict[str, object]:
    """撰写或修订综述模式下的一个章节节点。

    Returns:
        {"content", "version", "diff", "quality", "usage", "revision": bool}
    Raises:
        LLMError, ValueError
    """
    section_kind = _resolve_section_kind(node)
    budget = _int_setting("CONTEXT_CHAR_BUDGET", 12000)

    reference_text, ref_stats = select_reference_materials(
        session, node.title, section_kind, int(budget * 0.55)
    )
    approved_context = build_approved_context(session, exclude_id=node.id)
    outline_text = _outline_digest(session, node)

    revision = None
    if feedback:
        revision = {
            "previous_content": node.content_zh or node.content_en,
            "feedback": feedback,
            "version": node.current_version + 2,
        }

    previous_content = node.content_zh or node.content_en
    system_prompt = ExpertFactory.get_writer_expert_prompt(
        chapter_name=node.title,
        language=language,
        background=session.research_question or session.research_topic,
        outline=outline_text,
        section_title=node.title,
        reference_materials=reference_text,
        approved_context=approved_context,
        section_kind=section_kind,
        revision=revision,
    )

    raw_content, usage = _generate(system_prompt)
    cleaned = cleaner.clean_content(raw_content)

    if not cleaner.is_valid_content(cleaned):
        raise ValueError("生成的内容无效：可能是资料不足或模型返回了说明性文字，请补充资料后重试")

    quality = validate_section(
        cleaned,
        source_text=_source_text(session, section_kind),
        section_kind=section_kind,
        has_reference_list=bool(session.references),
    )

    if feedback:
        version_entry = node.apply_revision(cleaned, feedback, quality=quality)
        diff = unified_diff(previous_content, cleaned)
    else:
        node.content_zh = cleaned
        node.quality_issues = quality
        version_entry = node.snapshot(feedback="", source="generate", quality=quality)
        node.updated_at = version_entry["created_at"]
        diff = {"has_changes": True, "added_lines": 0, "removed_lines": 0, "unified": ""}

    node.status = SectionStatus.PENDING_REVIEW
    session.total_tokens += usage.get("total_tokens", 0)
    from services.session_manager import manager
    manager.save(session.session_id)

    logger.info(
        "[writing] section written",
        section_id=node.id,
        section_kind=section_kind,
        revision=bool(feedback),
        length=len(cleaned),
        quality_issues=len(quality),
        ref_selected=ref_stats.get("selected", 0),
    )

    return {
        "content": cleaned,
        "version": version_entry.get("version", node.current_version),
        "diff": diff,
        "quality": quality,
        "usage": usage,
        "revision": bool(feedback),
        "section_kind": section_kind,
        "context": {"references": ref_stats, "approved_chars": len(approved_context)},
    }


def _outline_digest(session: Session, node: OutlineNode) -> str:
    """把提纲压成紧凑文本：本节标题 + 同级与上下级标题，避免整棵提纲灌入"""
    lines: List[str] = []
    parent = node.parent
    if parent and parent.level > 0:
        lines.append(f"{parent.title}")
    lines.append(f"{node.title}")
    for child in node.children[:10]:
        lines.append(f"  - {child.title}")
    siblings = [s for s in (parent.children if parent else []) if s.id != node.id]
    if siblings:
        lines.append("同级章节：" + "、".join(s.title for s in siblings[:8]))
    return "\n".join(lines)


def write_rct_section(
    session: Session,
    chapter: str,
    language: str = "中文",
    feedback: str = "",
) -> Dict[str, object]:
    """撰写或修订 RCT 模式下的一个章节"""
    budget = _int_setting("CONTEXT_CHAR_BUDGET", 12000)
    section_kind = infer_section_kind(chapter)

    study_info = truncate_preserving_structure(
        session.protocol_text or "暂无研究方案", int(budget * 0.45)
    )
    analysis_results = truncate_preserving_structure(
        session.analysis_text or "暂无分析结果", int(budget * 0.45)
    )

    # 前序已批准章节：保证术语、组名、样本量一致
    approved = []
    for section in session.sections:
        if section.get("chapter") == chapter:
            continue
        if section.get("status") == "approved" and (section.get("content_zh") or section.get("content")):
            body = (section.get("content_zh") or section.get("content"))[:300].replace("\n", " ")
            approved.append(f"【已批准】{section.get('chapter')}：{body}")
    previous_chapters = "\n".join(approved)

    entry = session.rct_section(chapter)
    if entry is None:
        entry = {
            "chapter": chapter,
            "content_zh": "",
            "content": "",
            "status": "pending",
            "revisions": [],
            "versions": [],
        }
        session.sections.append(entry)

    previous_content = entry.get("content_zh") or entry.get("content") or ""
    revision = None
    if feedback:
        revision = {
            "previous_content": previous_content,
            "feedback": feedback,
            "version": len(entry.get("versions", [])) + 2,
        }

    system_prompt = ExpertFactory.get_rct_writer_prompt(
        chapter=chapter,
        language=language,
        study_info=study_info,
        analysis_results=analysis_results,
        previous_chapters=previous_chapters,
        revision=revision,
    )

    raw_content, usage = _generate(system_prompt)
    cleaned = cleaner.clean_content(raw_content)
    if not cleaner.is_valid_content(cleaned):
        raise ValueError("生成的内容无效：请检查研究方案与统计分析结果是否完整")

    quality = validate_section(
        cleaned,
        source_text=_source_text(session, section_kind),
        section_kind=section_kind,
        has_reference_list=bool(session.references),
    )

    versions: List[dict] = entry.setdefault("versions", [])
    last_version = (versions[-1].get("content_zh") or "").strip() if versions else ""
    if previous_content.strip() and previous_content.strip() != last_version:
        versions.append({
            "version": len(versions) + 1,
            "content_zh": previous_content,
            "feedback": "",
            "source": "before_revision" if feedback else "generate",
            "created_at": entry.get("updated_at", ""),
        })

    entry["content_zh"] = cleaned
    entry["content"] = cleaned
    entry["status"] = "pending_review"
    entry["quality_issues"] = quality
    entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
    if feedback:
        entry.setdefault("revisions", []).append({"feedback": feedback, "created_at": entry["updated_at"]})
        entry["feedback"] = ""
    versions.append({
        "version": len(versions) + 1,
        "content_zh": cleaned,
        "feedback": feedback,
        "source": "revision" if feedback else "generate",
        "created_at": entry["updated_at"],
    })

    session.current_chapter = chapter
    session.total_tokens += usage.get("total_tokens", 0)
    from services.session_manager import manager
    manager.save(session.session_id)

    diff = unified_diff(previous_content, cleaned) if feedback else {
        "has_changes": True, "added_lines": 0, "removed_lines": 0, "unified": ""
    }

    logger.info(
        "[writing] RCT chapter written",
        chapter=chapter,
        revision=bool(feedback),
        length=len(cleaned),
        quality_issues=len(quality),
    )

    return {
        "content": cleaned,
        "version": len(versions),
        "diff": diff,
        "quality": quality,
        "usage": usage,
        "revision": bool(feedback),
        "section_kind": section_kind,
    }
