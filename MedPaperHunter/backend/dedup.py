"""Deduplication and LLM screening module for MedPaperHunter.

Provides functions to remove duplicate articles (by PMID or normalized title)
and to screen articles for relevance using an LLM.
"""

from __future__ import annotations

import logging
import re
import string
from typing import Any

logger = logging.getLogger(__name__)


def _count_filled_fields(article: dict[str, Any]) -> int:
    """Count the number of non-empty fields in an article dict.

    Used to decide which duplicate to keep (the one with more data).

    Args:
        article: An article dict.

    Returns:
        The number of fields that have a truthy value.
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
    """Remove duplicate articles by PMID.

    When multiple articles share the same PMID, the one with the most
    complete data (most non-empty fields) is kept.

    Args:
        articles: List of article dicts, each potentially containing a "pmid" key.

    Returns:
        Deduplicated list of article dicts.
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
    """Normalize a title for deduplication comparison.

    Converts to lowercase, strips leading/trailing whitespace, and removes
    all punctuation characters.

    Args:
        title: The article title to normalize.

    Returns:
        Normalized title string.
    """
    title = title.lower().strip()
    # Remove punctuation
    title = title.translate(str.maketrans("", "", string.punctuation))
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title)
    return title


def deduplicate_by_title(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate articles by normalized title.

    For articles without a PMID, this function deduplicates by comparing
    normalized titles (lowercase, punctuation stripped, whitespace collapsed).
    When duplicates are found, the one with the most complete data is kept.

    Args:
        articles: List of article dicts, each containing a "title" key.

    Returns:
        Deduplicated list of article dicts.
    """
    seen: dict[str, dict[str, Any]] = {}

    for article in articles:
        title = article.get("title", "")
        if not title:
            continue

        normalized = _normalize_title(title)
        if not normalized:
            continue

        if normalized in seen:
            existing = seen[normalized]
            if _count_filled_fields(article) > _count_filled_fields(existing):
                seen[normalized] = article
        else:
            seen[normalized] = article

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
    """Screen articles for relevance using an LLM.

    Sends article titles and abstracts to the LLM in batches, asking
    whether each article is relevant to the given research question.
    Only articles marked as relevant (YES) are returned.

    The LLM prompt is always in English regardless of the input language.

    Args:
        articles: List of article dicts with "title" and "abstract" keys.
        llm_client: An LLM client object that supports an async
                    `chat(messages: list[dict]) -> str` method, or an
                    OpenAI-compatible client with
                    `chat.completions.create()`. The function will attempt
                    to detect and use the appropriate interface.
        question: The research question used for screening.
        batch_size: Number of articles to send per LLM request.
                   Defaults to 20.

    Returns:
        List of articles where screening_result="YES", with additional
        "screening_result" and "screening_reason" fields.
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
