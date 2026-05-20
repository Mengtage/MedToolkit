"""文献去重与AI筛选模块
=======================

本模块提供文献处理的两个核心功能：

1. **文献去重**
   - 按PMID去重：相同PMID的文献只保留数据最完整的
   - 按标题去重：对于没有PMID的文献，通过规范化标题比对去重

2. **AI相关性筛选**
   - 使用大语言模型判断文献与研究问题的相关性
   - 分批处理，每批最多20篇文献
   - 返回筛选结果和判断理由

去重策略:
    1. 优先按PMID去重（最准确）
    2. 对无PMID的文献按标题去重
    3. 去重时保留数据最完整的文献

AI筛选规则:
    - 包容性原则：不确定时标记为相关
    - 根据标题和摘要判断相关性
    - 返回每篇文献的筛选结果和理由

文献数据完整性判断:
    - 统计非空字段数量
    - 字段越多表示数据越完整
    - 用于去重时选择保留哪篇重复文献

使用示例:
    >>> # 去重
    >>> articles = deduplicate_by_pmid(raw_articles)
    >>> articles = deduplicate_by_title(articles)
    >>> 
    >>> # AI筛选
    >>> screened = await llm_screen(articles, llm_client, research_question)
"""

from __future__ import annotations

import logging
import re
import string
from typing import Any

logger = logging.getLogger(__name__)


def _count_filled_fields(article: dict[str, Any]) -> int:
    """计算文献数据完整度分数。
    
    统计文献字典中非空字段的数量，用于去重时判断保留哪篇文献。
    
    计算规则:
        - 跳过 "source" 字段（所有文献都有）
        - None 值不计入
        - 空字符串不计入
        - 空列表不计入
        - 其他非空值计入
    
    Args:
        article: 文献字典
    
    Returns:
        非空字段数量（完整度分数）
    """
    count = 0
    for key, value in article.items():
        if key == "source":
            continue
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            count += 1
        elif isinstance(value, list) and value:
            count += 1
        elif not isinstance(value, (str, list)):
            count += 1
    return count


def deduplicate_by_pmid(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按PMID去重。
    
    PubMed标识符(PMID)是文献的唯一标识，相同PMID表示同一篇文献。
    
    去重策略:
        1. 遍历所有文献，按PMID分组
        2. 对于相同PMID的文献，保留数据最完整的那篇
        3. 没有PMID的文献单独处理（后续按标题去重）
    
    Args:
        articles: 文献列表，每个文献可能包含 "pmid" 字段
    
    Returns:
        去重后的文献列表
    """
    seen: dict[str, dict[str, Any]] = {}
    no_pmid: list[dict[str, Any]] = []

    for article in articles:
        pmid = article.get("pmid")
        if not pmid:
            no_pmid.append(article)
            continue

        if pmid in seen:
            existing = seen[pmid]
            if _count_filled_fields(article) > _count_filled_fields(existing):
                seen[pmid] = article
        else:
            seen[pmid] = article

    result = list(seen.values()) + no_pmid
    logger.info(
        "Deduplicated by PMID: %d articles -> %d unique",
        len(articles),
        len(result),
    )
    return result


def _normalize_title(title: str) -> str:
    """规范化标题用于去重比对。
    
    将标题转换为统一格式，消除格式差异导致的误判。
    
    规范化步骤:
        1. 转换为小写
        2. 去除首尾空格
        3. 删除所有标点符号
        4. 合并连续空白字符
    
    Args:
        title: 文献标题
    
    Returns:
        规范化后的标题字符串
    """
    title = title.lower().strip()
    # Remove punctuation
    title = title.translate(str.maketrans("", "", string.punctuation))
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title)
    return title


def deduplicate_by_title(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按标题去重。
    
    对于没有PMID的文献（如从其他数据库导入的文献），通过标题比对去重。
    
    去重策略:
        1. 对每篇文献的标题进行规范化处理
        2. 按规范化标题分组
        3. 对于相同标题的文献，保留数据最完整的那篇
    
    适用场景:
        - 从Web of Science、Scopus等数据库导入的文献
        - 没有PMID的预印本
        - 其他缺少唯一标识符的文献
    
    Args:
        articles: 文献列表，每个文献应包含 "title" 字段
    
    Returns:
        去重后的文献列表
    """
    seen: dict[str, dict[str, Any]] = {}
    normalized_count: dict[str, int] = {}

    for article in articles:
        title = article.get("title", "")
        if not title:
            continue

        normalized = _normalize_title(title)
        if not normalized:
            continue
        
        normalized_count[normalized] = normalized_count.get(normalized, 0) + 1

        if normalized in seen:
            existing = seen[normalized]
            if _count_filled_fields(article) > _count_filled_fields(existing):
                seen[normalized] = article
        else:
            seen[normalized] = article
    
    # Log the most frequent normalized titles to debug
    if len(normalized_count) > 0:
        sorted_counts = sorted(normalized_count.items(), key=lambda x: x[1], reverse=True)[:10]
        logger.info(f"Most frequent normalized titles (top 10): {sorted_counts}")

    result = list(seen.values())
    logger.info(
        "Deduplicated by title: %d articles -> %d unique",
        len(articles),
        len(result),
    )
    return result


# ------------------------------------------------------------------
# LLM screening
# ------------------------------------------------------------------

SCREENING_SYSTEM_PROMPT = (
    "You are a research assistant helping to screen academic articles for "
    "relevance to a specific research question. For each article provided, "
    "determine whether it is relevant based on its title and abstract. "
    "IMPORTANT: Respond in the following exact format for each article using CHINESE language:\n"
    "\n"
    "ANSWER: YES or NO\n"
    "REASON: <简要说明原因>\n"
    "\n"
    "Be inclusive rather than exclusive -- when in doubt, mark as YES."
)

SCREENING_USER_TEMPLATE = (
    "研究问题: {question}\n"
    "\n"
    "请评估以下{count}篇文章。对于每篇文章，请使用以下格式回复（使用中文）：\n"
    "ANSWER: YES or NO\n"
    "REASON: <简要说明原因>\n"
    "\n"
    "{articles_text}"
)


def _format_article_for_screening(index: int, article: dict[str, Any]) -> str:
    """Format a single article for inclusion in the LLM screening prompt.

    Args:
        index: The article index number.
        article: The article dict.

    Returns:
        Formatted string with article number, title, and abstract.
    """
    title = article.get("title", "No title")
    abstract = article.get("abstract", "No abstract available")
    return f"Article {index}:\nTitle: {title}\nAbstract: {abstract}\n"


def _parse_screening_response(
    response_text: str,
    batch_articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse the LLM response and attach screening results to articles.

    Expects the response to contain ANSWER: YES/NO and REASON: lines
    for each article.

    Args:
        response_text: The raw text response from the LLM.
        batch_articles: The articles that were sent for screening.

    Returns:
        List of articles with "screening_result" and "screening_reason" fields added.
    """
    # Split response into per-article blocks
    # Try to match patterns like "Article N:" or numbered sections
    blocks = re.split(r"Article\s+\d+[:\s]*", response_text, flags=re.IGNORECASE)

    # If splitting didn't produce enough blocks, try splitting by ANSWER
    if len(blocks) < len(batch_articles):
        blocks = re.split(r"ANSWER:", response_text, flags=re.IGNORECASE)
        if blocks and blocks[0].strip():
            # First block might be preamble, keep it
            pass

    results: list[dict[str, Any]] = []

    for i, article in enumerate(batch_articles):
        article_copy = dict(article)

        # Find the relevant block for this article
        block = ""
        if i + 1 < len(blocks):
            block = blocks[i + 1] if len(blocks) > len(batch_articles) else (
                blocks[i] if i < len(blocks) else ""
            )

        # If blocks don't align well, search the full response for this article's section
        if not block and len(batch_articles) > 1:
            pattern = rf"Article\s+{i + 1}[:\s]*(.*?)(?=Article\s+{i + 2}|$)"
            match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            if match:
                block = match.group(1)

        # Extract ANSWER - handle multiple formats:
        # 1. ANSWER: YES/NO (expected format)
        # 2. YES/NO followed by reason (actual format from some LLMs)
        answer_match = re.search(
            r"(?:ANSWER\s*:\s*)?(YES|NO)",
            block or response_text,
            re.IGNORECASE,
        )
        screening_result = "YES" if (
            answer_match and answer_match.group(1).upper() == "YES"
        ) else "NO"

        # Extract REASON - handle multiple formats:
        # 1. REASON: <explanation> (expected format)
        # 2. YES/NO\t<reason> or YES/NO <reason> (actual format from some LLMs)
        reason_match = re.search(
            r"REASON\s*:\s*(.+?)(?=\n\s*(?:ANSWER|REASON|Article|\Z))",
            block or response_text,
            re.IGNORECASE | re.DOTALL,
        )
        screening_reason = ""
        if reason_match:
            screening_reason = reason_match.group(1).strip()
        else:
            # Fallback: extract text after YES/NO (handle both tab and space separated)
            if answer_match:
                rest = response_text[answer_match.end():].strip()
                # Remove leading tabs/spaces and take the rest as reason
                rest = rest.lstrip('\t ').strip()
                screening_reason = rest[:200] if rest else "No reason provided"

        article_copy["screening_result"] = screening_result
        article_copy["screening_reason"] = screening_reason
        results.append(article_copy)

    return results


async def llm_screen(
    articles: list[dict[str, Any]],
    llm_client: Any,
    question: str,
    batch_size: int = 20,
) -> list[dict[str, Any]]:
    """AI相关性筛选。
    
    使用大语言模型判断文献与研究问题的相关性。
    
    处理流程:
        1. 将文献分批（每批最多20篇）
        2. 构建包含研究问题和文献信息的提示词
        3. 调用LLM进行判断
        4. 解析LLM响应，标记每篇文献的相关性
        5. 只返回标记为相关的文献
    
    筛选规则:
        - 包容性原则：不确定时标记为相关(YES)
        - 根据标题和摘要判断相关性
        - 返回每篇文献的判断理由
    
    支持的LLM客户端类型:
        - OpenAI兼容客户端（chat.completions.create接口）
        - 自定义客户端（chat方法）
        - 可调用对象
    
    Args:
        articles: 文献列表，每个文献应包含 "title" 和 "abstract" 字段
        llm_client: LLM客户端对象
        question: 研究问题，用于判断相关性
        batch_size: 每批处理的文献数量，默认20
    
    Returns:
        筛选后的文献列表（仅包含标记为相关的文献），每个文献添加了:
            - screening_result: "YES" 或 "NO"
            - screening_reason: 判断理由
    """
    if not articles:
        return []

    all_screened: list[dict[str, Any]] = []

    for offset in range(0, len(articles), batch_size):
        batch = articles[offset : offset + batch_size]
        logger.info(
            "Screening batch %d-%d of %d articles",
            offset + 1,
            min(offset + batch_size, len(articles)),
            len(articles),
        )

        # Format articles for the prompt
        articles_text = "\n".join(
            _format_article_for_screening(i + 1, article)
            for i, article in enumerate(batch)
        )

        user_message = SCREENING_USER_TEMPLATE.format(
            question=question,
            count=len(batch),
            articles_text=articles_text,
        )

        messages = [
            {"role": "system", "content": SCREENING_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # Call the LLM
        response_text = await _call_llm(llm_client, messages)

        # Parse the response
        screened = _parse_screening_response(response_text, batch)
        all_screened.extend(screened)

    # Filter to only YES results
    relevant = [a for a in all_screened if a.get("screening_result") == "YES"]

    logger.info(
        "LLM screening complete: %d of %d articles marked as relevant",
        len(relevant),
        len(articles),
    )

    return relevant


async def _call_llm(llm_client: Any, messages: list[dict[str, str]]) -> str:
    """Call the LLM with the given messages.

    Supports multiple LLM client interfaces:
    - OpenAI-compatible clients with chat.completions.create()
    - Generic clients with a chat() method
    - Generic clients with an __call__ method

    Args:
        llm_client: The LLM client instance.
        messages: List of message dicts with "role" and "content" keys.

    Returns:
        The LLM response text.
    """
    # Try OpenAI-compatible interface
    if hasattr(llm_client, "chat") and hasattr(llm_client.chat, "completions"):
        response = await llm_client.chat.completions.create(
            model="default",
            messages=messages,
            temperature=0.1,
        )
        return response.choices[0].message.content or ""

    # Try async chat method
    if hasattr(llm_client, "chat") and callable(llm_client.chat):
        result = llm_client.chat(messages)
        if hasattr(result, "__await__"):
            return str(await result)
        return str(result)

    # Try direct async call
    if callable(llm_client):
        result = llm_client(messages)
        if hasattr(result, "__await__"):
            return str(await result)
        return str(result)

    raise TypeError(
        "Unsupported LLM client interface. The client must support one of: "
        "OpenAI chat.completions.create(), a chat() method, or be callable."
    )
