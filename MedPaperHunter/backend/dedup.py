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

import json
import logging
import os
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


_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "dx.doi.org/", "doi.org/", "doi:")


def _normalize_doi(doi: Any) -> str:
    """规范化 DOI 用于去重比对。

    处理步骤:
        1. 转字符串、去首尾空白、转小写
        2. 剥离常见前缀（https://doi.org/、doi: 等）
        3. 去除结尾多余的句点/斜杠

    Args:
        doi: 原始 DOI 值（可能是 None、str 或其他类型）

    Returns:
        规范化后的 DOI 字符串；无效输入返回空字符串
    """
    if doi is None:
        return ""
    d = str(doi).strip().lower()
    if not d:
        return ""
    for prefix in _DOI_PREFIXES:
        if d.startswith(prefix):
            d = d[len(prefix):]
            break
    return d.rstrip("./").strip()


def deduplicate_by_doi(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 DOI 去重。

    DOI 是跨数据库最稳定的文献唯一标识。PMID 只覆盖 PubMed 收录文献，
    而 WoS/Scopus/Embase 导入的文献通常没有 PMID，但绝大多数有 DOI。
    因此去重顺序应为：PMID -> DOI -> 规范化标题。

    去重策略:
        1. 遍历所有文献，按规范化 DOI 分组
        2. 对于相同 DOI 的文献，保留数据最完整的那篇
        3. 没有 DOI 的文献单独保留（后续按标题去重兜底）

    Args:
        articles: 文献列表，每个文献可能包含 "doi" 字段

    Returns:
        去重后的文献列表
    """
    seen: dict[str, dict[str, Any]] = {}
    no_doi: list[dict[str, Any]] = []

    for article in articles:
        doi = _normalize_doi(article.get("doi"))
        if not doi:
            no_doi.append(article)
            continue

        if doi in seen:
            existing = seen[doi]
            if _count_filled_fields(article) > _count_filled_fields(existing):
                seen[doi] = article
        else:
            seen[doi] = article

    result = list(seen.values()) + no_doi
    logger.info(
        "Deduplicated by DOI: %d articles -> %d unique",
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

# 解析失败时的标记值：禁止静默落到 YES/NO，必须显式上报
UNPARSED = "UNPARSED"

SCREENING_SYSTEM_PROMPT = (
    "You are a research assistant helping to screen academic articles for "
    "relevance to a specific research question. For each article, judge "
    "relevance based on its title and abstract.\n"
    "OUTPUT RULES (strict):\n"
    "- Output ONLY a JSON array. No extra text, no markdown fences.\n"
    "- One object per article, in the SAME ORDER as the input:\n"
    '  {"index": <int, 1-based>, "answer": "YES" or "NO", "reason": "<brief reason in Chinese>"}\n'
    "- Be inclusive rather than exclusive -- when in doubt, answer YES."
)

SCREENING_USER_TEMPLATE = (
    "研究问题: {question}\n"
    "\n"
    "请评估以下{count}篇文章。严格按输入顺序输出一个 JSON 数组，每篇文章一个对象：\n"
    '[{{"index": <1到{count}>, "answer": "YES"或"NO", "reason": "<中文简要理由>"}}]\n'
    "只输出 JSON 数组本身，不要输出任何其他内容。\n"
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


def _extract_json_array(text: str) -> list[Any]:
    """从 LLM 响应中提取 JSON 数组，带两级容错。

    容错策略:
        1. 剥离 markdown 代码块围栏
        2. 截取第一个 '[' 到最后一个 ']' 之间的内容解析
        3. 若解析失败（如响应被截断），截断到最后一个完整对象再解析

    Args:
        text: LLM 原始响应文本

    Returns:
        解析出的列表；完全无法解析时返回空列表
    """
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()

    start = s.find("[")
    if start == -1:
        return []
    end = s.rfind("]")

    if end > start:
        try:
            data = json.loads(s[start : end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass  # 落入下方的截断修复路径

    # 响应可能被 max_tokens 截断（无闭合 ']' 或 JSON 不完整）：
    # 截到最后一个完整对象，补上 ']' 再解析，至少恢复前面的条目
    last_brace = s.rfind("}")
    if last_brace <= start:
        return []
    try:
        data = json.loads(s[start : last_brace + 1] + "]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _parse_screening_response(
    response_text: str,
    batch_articles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """解析 LLM 筛选响应，按 index 逐篇对号。

    设计原则（替代旧的文本块对齐方案）:
        - LLM 按约定输出 JSON 数组，每篇含 index/answer/reason
        - 按 index 对号入座，index 缺失、越界、answer 非法的条目一律
          标记为 UNPARSED，绝不借用其他条目的答案（防止张冠李戴）
        - 返回解析成功数，供调用方做数量守恒校验

    Args:
        response_text: LLM 原始响应文本
        batch_articles: 本批次送筛的文献列表

    Returns:
        (results, n_parsed):
            - results: 带 screening_result ("YES"/"NO"/"UNPARSED") 和
              screening_reason 字段的文献列表，顺序与输入一致
            - n_parsed: 成功解析出判定的文献数量
    """
    items = _extract_json_array(response_text)

    by_index: dict[int, dict[str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        answer = str(item.get("answer", "")).strip().upper()
        # 兼容个别模型把 index 输出为字符串
        if isinstance(idx, str) and idx.strip().isdigit():
            idx = int(idx.strip())
        if not isinstance(idx, int) or answer not in ("YES", "NO"):
            continue
        if idx < 1 or idx > len(batch_articles):
            continue
        reason = str(item.get("reason", "")).strip()
        by_index[idx] = {"answer": answer, "reason": reason}

    results: list[dict[str, Any]] = []
    n_parsed = 0
    for i, article in enumerate(batch_articles):
        article_copy = dict(article)
        got = by_index.get(i + 1)
        if got is not None:
            article_copy["screening_result"] = got["answer"]
            article_copy["screening_reason"] = got["reason"]
            n_parsed += 1
        else:
            article_copy["screening_result"] = UNPARSED
            article_copy["screening_reason"] = (
                "LLM 响应中缺少该文献的判定，需人工复核"
            )
        results.append(article_copy)

    return results, n_parsed


async def llm_screen(
    articles: list[dict[str, Any]],
    llm_client: Any,
    question: str,
    batch_size: int = 20,
    max_retries: int = 1,
) -> list[dict[str, Any]]:
    """AI相关性筛选（返回全部文献的判定结果）。

    处理流程:
        1. 将文献分批（每批最多 batch_size 篇）
        2. 构建包含研究问题和文献信息的提示词（要求 LLM 输出 JSON 数组）
        3. 调用LLM进行判断
        4. 按 index 逐篇解析，做数量守恒校验
        5. 解析不完整的批次自动重试（最多 max_retries 次）

    筛选规则:
        - 包容性原则：不确定时标记为相关(YES)
        - 根据标题和摘要判断相关性
        - 解析失败的文献标记为 UNPARSED，显式上报，绝不静默归类

    Args:
        articles: 文献列表，每个文献应包含 "title" 和 "abstract" 字段
        llm_client: LLM客户端对象
        question: 研究问题，用于判断相关性
        batch_size: 每批处理的文献数量，默认20
        max_retries: 解析不完整时的最大重试次数，默认1

    Returns:
        全部文献列表（顺序不变），每篇添加了:
            - screening_result: "YES" / "NO" / "UNPARSED"
            - screening_reason: 判断理由（UNPARSED 时为提示语）
    """
    if not articles:
        return []

    all_screened: list[dict[str, Any]] = []
    total_parsed = 0

    for offset in range(0, len(articles), batch_size):
        batch = articles[offset : offset + batch_size]
        logger.info(
            "Screening batch %d-%d of %d articles",
            offset + 1,
            min(offset + batch_size, len(articles)),
            len(articles),
        )

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

        screened: list[dict[str, Any]] = []
        n_parsed = 0
        for attempt in range(1, max_retries + 2):
            response_text = await _call_llm(llm_client, messages)
            screened, n_parsed = _parse_screening_response(response_text, batch)

            if n_parsed == len(batch):
                break
            logger.warning(
                "Screening batch %d-%d: parsed %d/%d articles (attempt %d/%d)",
                offset + 1,
                offset + len(batch),
                n_parsed,
                len(batch),
                attempt,
                max_retries + 1,
            )

        all_screened.extend(screened)
        total_parsed += n_parsed

    yes_count = sum(1 for a in all_screened if a.get("screening_result") == "YES")
    unparsed_count = len(all_screened) - total_parsed
    logger.info(
        "LLM screening complete: %d relevant / %d excluded / %d unparsed of %d total",
        yes_count,
        len(all_screened) - yes_count - unparsed_count,
        unparsed_count,
        len(articles),
    )

    return all_screened


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
        model = (
            getattr(llm_client, "model", None)
            or os.getenv("LLM_MODEL")
            or "default"
        )
        response = await llm_client.chat.completions.create(
            model=model,
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
