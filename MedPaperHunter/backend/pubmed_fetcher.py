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
import calendar
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ESEARCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# NCBI recommends no more than 3 requests per second without an API key
# (10 req/s with one). Using 0.4s delay keeps us safely under that limit.
REQUEST_DELAY = 0.4

# Optional NCBI API key (raises the rate limit from 3 to 10 req/s)
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")

# A date component: YYYY, YYYY/MM, YYYY/MM/DD (also accepts '-' separator)
_DATE_COMPONENT = r"\d{4}(?:[-/]\d{1,2}(?:[-/]\d{1,2})?)?"
_DATE_RANGE_RE = re.compile(
    rf"^\s*({_DATE_COMPONENT})\s*[-–—]\s*({_DATE_COMPONENT})\s*$"
)


def _normalize_date(date_str: str, is_start: bool) -> str:
    """将 YYYY / YYYY/MM / YYYY-MM-DD 等格式补齐为 NCBI 的 YYYY/MM/DD。

    - 开始日期缺省部分补最小值（01/01）
    - 结束日期缺省部分补最大值：年→12月31日，月→该月最后一天
      （用 calendar.monthrange 取真实月末，避免 "2024/02/31" 这类非法日期）

    Raises:
        ValueError: 日期组件无法解析时
    """
    parts = [p for p in re.split(r"[-/]", date_str.strip()) if p]
    if not parts or not parts[0].isdigit() or len(parts[0]) != 4:
        raise ValueError(f"Invalid date component: '{date_str}'")

    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else (1 if is_start else 12)
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month in date component: '{date_str}'")
    if len(parts) > 2:
        day = int(parts[2])
    else:
        day = 1 if is_start else calendar.monthrange(year, month)[1]
    if not 1 <= day <= 31:
        raise ValueError(f"Invalid day in date component: '{date_str}'")

    return f"{year:04d}/{month:02d}/{day:02d}"


def _parse_date_range(date_range: str) -> tuple[str, str]:
    """解析日期范围字符串。

    支持的格式（起止日期可分别省略月/日，分隔符可用 / 或 -）:
        - "2020-2024"                    # 年份范围
        - "2020/01-2024/12"              # 年月范围
        - "2020/01/01-2024/12/31"        # 完整日期（/ 分隔）
        - "2020-01-01 - 2024-12-31"      # 完整日期（- 分隔，可用正则区分）

    Args:
        date_range: 日期范围字符串

    Returns:
        (start_date, end_date): 标准化为 YYYY/MM/DD 的开始和结束日期

    Raises:
        ValueError: 如果日期格式无效
    """
    date_range = date_range.strip()
    if not date_range:
        return "", ""

    match = _DATE_RANGE_RE.match(date_range)
    if not match:
        raise ValueError(
            f"Invalid date range format: '{date_range}'. "
            "Expected format: 'start-end' (e.g. '2020-2024' or '2020/01/01-2024/12/31')."
        )

    start = _normalize_date(match.group(1), is_start=True)
    end = _normalize_date(match.group(2), is_start=False)
    if start > end:
        raise ValueError(
            f"Invalid date range: start '{start}' is after end '{end}'."
        )
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


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str],
    max_retries: int = 3,
) -> httpx.Response:
    """GET 请求，带指数退避重试。

    对 429（限流）和 5xx（服务端错误）自动重试，
    退避间隔 1s、2s、4s……；其他错误直接抛出。

    Args:
        client: httpx异步客户端
        url: 请求URL
        params: 查询参数
        max_retries: 最大重试次数

    Returns:
        成功的 HTTP 响应

    Raises:
        httpx.HTTPStatusError: 重试耗尽后仍失败
    """
    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "NCBI returned %d, retrying in %ds (attempt %d/%d)",
                        resp.status_code, wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue
            resp.raise_for_status()
            return resp
        except (httpx.TimeoutException, httpx.TransportError) as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "NCBI request failed (%s), retrying in %ds (attempt %d/%d)",
                    e, wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)
                continue
            raise
    raise httpx.HTTPStatusError(  # pragma: no cover - 兜底，逻辑上不可达
        "NCBI request failed after retries", request=None, response=resp
    )


def _apply_api_key(params: dict[str, str]) -> dict[str, str]:
    """如果配置了 NCBI_API_KEY，附加到请求参数中。"""
    if NCBI_API_KEY:
        params = dict(params)
        params["api_key"] = NCBI_API_KEY
    return params


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

    resp = await _get_with_retry(client, ESEARCH_BASE, _apply_api_key(params))
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

    resp = await _get_with_retry(
        client,
        EFETCH_BASE,
        _apply_api_key({
            "db": "pubmed",
            "id": ids_str,
            "rettype": "xml",
            "retmode": "xml",
        }),
    )

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
