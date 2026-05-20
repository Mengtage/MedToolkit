"""PubMed文献获取模块
====================

本模块负责从PubMed数据库获取文献数据，使用NCBI E-utilities API。

核心功能:
    1. 检索执行：使用esearch API搜索文献
    2. 详情获取：使用efetch API获取文献详细信息
    3. 结果解析：将XML响应解析为结构化的文献对象
    4. 限流控制：遵守NCBI API使用规范

NCBI E-utilities API说明:
    - esearch: 搜索PubMed数据库，返回PMID列表
    - efetch: 根据PMID获取文献详细信息（XML格式）
    
API使用限制:
    - 无API密钥：最多3请求/秒
    - 有API密钥：最多10请求/秒
    - 本模块使用0.4秒延迟，确保安全

文献数据结构:
    {
        "source": "pubmed",           # 数据来源
        "pmid": "12345678",           # PubMed标识符
        "title": "...",               # 文献标题
        "authors": ["Author1", ...],  # 作者列表
        "journal": "...",             # 期刊名称
        "pub_date": "...",            # 发表日期
        "abstract": "...",            # 摘要
        "doi": "..."                  # DOI标识符
    }

使用示例:
    >>> articles = await fetch_pubmed(
    ...     query="diabetes mellitus metformin",
    ...     max_results=100,
    ...     date_range="2020-2024"
    ... )
    >>> print(f"获取到 {len(articles)} 篇文献")
"""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ESEARCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# NCBI recommends no more than 3 requests per second without an API key.
# Using 0.4s delay keeps us safely under that limit.
REQUEST_DELAY = 0.4


def _parse_date_range(date_range: str) -> tuple[str, str]:
    """解析日期范围字符串。
    
    支持多种日期格式:
        - "2020/01/01-2024/12/31"  # 完整日期范围
        - "2020-2024"              # 年份范围
        - "2020/01-2024/12"        # 年月范围
    
    自动补齐不完整的日期:
        - 开始日期: 年 → 年/01/01, 年月 → 年月/01
        - 结束日期: 年 → 年/12/31, 年月 → 年月/31
    
    Args:
        date_range: 日期范围字符串
    
    Returns:
        (start_date, end_date): 标准化后的开始和结束日期
    
    Raises:
        ValueError: 如果日期格式无效
    """
    date_range = date_range.strip()
    if not date_range:
        return "", ""

    parts = date_range.split("-")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid date range format: '{date_range}'. "
            "Expected format: 'start-end' (e.g. '2020/01/01-2024/12/31')."
        )

    start = parts[0].strip()
    end = parts[1].strip()

    # Normalize partial dates to full YYYY/MM/DD format
    for d in (start, end):
        parts_count = d.count("/")
        if parts_count == 0 and len(d) == 4:
            # Year only: 2020 -> 2020/01/01 or 2020/12/31
            pass
        elif parts_count == 1:
            # Year/Month: 2020/01
            pass
        elif parts_count == 2:
            # Full date: 2020/01/01
            pass
        else:
            raise ValueError(f"Invalid date component: '{d}'")

    # Pad partial dates
    if len(start) == 4:
        start = f"{start}/01/01"
    elif start.count("/") == 1:
        start = f"{start}/01"

    if len(end) == 4:
        end = f"{end}/12/31"
    elif end.count("/") == 1:
        # Get last day of month (approximate with 31)
        end = f"{end}/31"

    return start, end


def _parse_article_xml(article_el: ET.Element) -> dict[str, Any]:
    """解析单个PubMed文献的XML元素。
    
    从NCBI efetch返回的XML中提取文献信息，转换为结构化字典。
    
    XML结构说明:
        <PubmedArticle>
            <MedlineCitation>
                <PMID>...</PMID>
                <Article>
                    <ArticleTitle>...</ArticleTitle>
                    <AuthorList>...</AuthorList>
                    <Journal>...</Journal>
                    <PublicationTypeList>...</PublicationTypeList>
                </Article>
                <ArticleDate>...</ArticleDate>
                <Abstract>...</Abstract>
            </MedlineCitation>
            <PubmedData>
                <ArticleIdList>
                    <ArticleId IdType="doi">...</ArticleId>
                </ArticleIdList>
            </PubmedData>
        </PubmedArticle>
    
    Args:
        article_el: <PubmedArticle> XML元素
    
    Returns:
        包含文献信息的字典，包含以下字段:
            - source: 数据来源 ("pubmed")
            - pmid: PubMed标识符
            - title: 文献标题
            - authors: 作者列表
            - journal: 期刊名称
            - pub_date: 发表日期
            - abstract: 摘要
            - doi: DOI标识符
    """
    article: dict[str, Any] = {
        "source": "pubmed",
        "pmid": None,
        "title": "",
        "authors": [],
        "journal": "",
        "pub_date": "",
        "abstract": "",
        "doi": None,
    }

    # PMID
    pmid_el = article_el.find(".//PMID")
    if pmid_el is not None and pmid_el.text:
        article["pmid"] = pmid_el.text.strip()

    # Title
    title_el = article_el.find(".//ArticleTitle")
    if title_el is not None and title_el.text:
        article["title"] = title_el.text.strip()

    # Authors
    author_list = article_el.findall(".//Author")
    authors: list[str] = []
    for author_el in author_list:
        last_name = author_el.findtext("LastName", "").strip()
        fore_name = author_el.findtext("ForeName", "").strip()
        if last_name:
            if fore_name:
                authors.append(f"{last_name} {fore_name}")
            else:
                authors.append(last_name)
        elif fore_name:
            authors.append(fore_name)
    article["authors"] = authors

    # Journal
    journal_el = article_el.find(".//Journal/Title")
    if journal_el is not None and journal_el.text:
        article["journal"] = journal_el.text.strip()

    # Publication date
    pub_date_el = article_el.find(".//PubDate")
    if pub_date_el is not None:
        year = pub_date_el.findtext("Year", "").strip()
        month = pub_date_el.findtext("Month", "").strip()
        day = pub_date_el.findtext("Day", "").strip()
        parts = [p for p in [year, month, day] if p]
        article["pub_date"] = " ".join(parts)

    # Abstract
    abstract_parts: list[str] = []
    abstract_el = article_el.find(".//Abstract")
    if abstract_el is not None:
        for abs_text in abstract_el.findall(".//AbstractText"):
            label = abs_text.get("Label", "").strip()
            text = (abs_text.text or "").strip()
            if label:
                abstract_parts.append(f"{label}: {text}")
            elif text:
                abstract_parts.append(text)
    article["abstract"] = "\n".join(abstract_parts)

    # DOI
    for eid in article_el.findall(".//ArticleId"):
        if eid.get("IdType") == "doi" and eid.text:
            article["doi"] = eid.text.strip()
            break

    return article


async def _esearch(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
    date_range: str,
) -> list[str]:
    """执行PubMed搜索，获取PMID列表。
    
    使用NCBI E-utilities的esearch API搜索文献。
    
    API调用参数:
        - db: "pubmed"（固定）
        - term: 检索式
        - retmax: 返回数量限制
        - retmode: "json"（返回JSON格式）
        - datetype: "pdat"（出版日期）
        - mindate/maxdate: 日期范围（可选）
    
    Args:
        client: httpx异步客户端
        query: PubMed检索式字符串
        max_results: 最大返回数量
        date_range: 日期范围（如 "2020/01/01-2024/12/31"）
    
    Returns:
        PMID字符串列表
    """
    params: dict[str, str] = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "json",
    }

    if date_range:
        start, end = _parse_date_range(date_range)
        if start and end:
            params["datetype"] = "pdat"
            params["mindate"] = start
            params["maxdate"] = end

    logger.info("Running esearch with query: %s (max_results=%d)", query, max_results)

    resp = await client.get(ESEARCH_BASE, params=params)
    resp.raise_for_status()
    data = resp.json()

    result = data.get("esearchresult", {})
    count = int(result.get("count", 0))
    id_list = result.get("idlist", [])

    logger.info("esearch found %d results, retrieved %d PMIDs", count, len(id_list))

    return id_list


async def _efetch_batch(
    client: httpx.AsyncClient,
    pmids: list[str],
) -> list[dict[str, Any]]:
    """批量获取文献详情。
    
    使用NCBI E-utilities的efetch API获取一批PMID的详细信息。
    
    注意事项:
        - NCBI efetch API最多支持一次请求200个PMID
        - 返回XML格式数据
        - 需要解析XML提取文献信息
    
    Args:
        client: httpx异步客户端
        pmids: PMID字符串列表（最大200个）
    
    Returns:
        解析后的文献字典列表
    """
    if not pmids:
        return []

    ids_str = ",".join(pmids)
    logger.info("Fetching %d articles via efetch", len(pmids))

    resp = await client.get(
        EFETCH_BASE,
        params={
            "db": "pubmed",
            "id": ids_str,
            "rettype": "xml",
            "retmode": "xml",
        },
    )
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    articles: list[dict[str, Any]] = []

    for article_el in root.findall(".//PubmedArticle"):
        try:
            parsed = _parse_article_xml(article_el)
            articles.append(parsed)
        except Exception:
            logger.exception("Failed to parse PubmedArticle element")
            continue

    logger.info("Parsed %d articles from efetch response", len(articles))
    return articles


async def fetch_pubmed(
    query: str,
    max_results: int = 500,
    date_range: str = "",
) -> list[dict[str, Any]]:
    """从PubMed获取文献。
    
    完整的PubMed文献获取流程：
        1. 使用esearch API搜索文献，获取PMID列表
        2. 将PMID分批（每批最多200个）
        3. 使用efetch API批量获取文献详情
        4. 解析XML响应，转换为结构化字典
    
    处理流程:
        ┌─────────────────────────────────────────────────────────┐
        │  1. esearch: 执行检索，获取PMID列表                    │
        └───────────────────────────┬───────────────────────────┘
                                    ↓
        ┌─────────────────────────────────────────────────────────┐
        │  2. 分批处理: 每批200个PMID（NCBI限制）              │
        └───────────────────────────┬───────────────────────────┘
                                    ↓
        ┌─────────────────────────────────────────────────────────┐
        │  3. efetch: 批量获取文献详情（XML格式）               │
        └───────────────────────────┬───────────────────────────┘
                                    ↓
        ┌─────────────────────────────────────────────────────────┐
        │  4. 解析: XML → 结构化字典                            │
        └─────────────────────────────────────────────────────────┘
    
    Args:
        query: PubMed检索式字符串（如 "(diabetes[MeSH]) AND (metformin)"）
        max_results: 最大返回文献数量，默认500
        date_range: 日期范围过滤，格式如 "2020/01/01-2024/12/31"
    
    Returns:
        文献字典列表，每个字典包含:
            - source: "pubmed"
            - pmid: PubMed标识符
            - title: 标题
            - authors: 作者列表
            - journal: 期刊
            - pub_date: 发表日期
            - abstract: 摘要
            - doi: DOI标识符
    
    Raises:
        httpx.HTTPStatusError: 如果NCBI API请求失败
        ValueError: 如果日期范围格式无效
    """
    articles: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: esearch to get PMIDs
        pmids = await _esearch(client, query, max_results, date_range)
        if not pmids:
            logger.info("No PMIDs found for query: %s", query)
            return articles

        # Step 2: efetch in batches of 200
        batch_size = 200
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            batch_articles = await _efetch_batch(client, batch)
            articles.extend(batch_articles)

            # Rate limiting: wait between batches
            if i + batch_size < len(pmids):
                await asyncio.sleep(REQUEST_DELAY)

    logger.info(
        "fetch_pubmed complete: %d articles retrieved for query '%s'",
        len(articles),
        query,
    )
    return articles
