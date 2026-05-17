"""PubMed fetcher module for MedPaperHunter.

Fetches articles from PubMed using NCBI E-utilities (esearch + efetch).
Provides async interface with rate limiting and structured result parsing.
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
    """Parse a date range string into (start, end) tuples.

    Args:
        date_range: Date range in format "YYYY/MM/DD-YYYY/MM/DD" or
                    "YYYY-YYYY" or "YYYY/MM-YYYY/MM".

    Returns:
        Tuple of (start_date, end_date) strings in YYYY/MM/DD format.

    Raises:
        ValueError: If the date range format is invalid.
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
    """Parse a single PubmedArticle XML element into a structured dict.

    Args:
        article_el: The <PubmedArticle> XML element.

    Returns:
        Dict with keys: source, pmid, title, authors, journal, pub_date,
        abstract, doi.
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
    """Run esearch to get PMIDs matching the query.

    Args:
        client: httpx async client.
        query: PubMed search query string.
        max_results: Maximum number of results to retrieve.
        date_range: Date range string (e.g. "2020/01/01-2024/12/31").

    Returns:
        List of PMID strings.
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
    """Fetch and parse article details for a batch of PMIDs.

    NCBI efetch accepts up to 200 IDs per request.

    Args:
        client: httpx async client.
        pmids: List of PMID strings to fetch.

    Returns:
        List of parsed article dicts.
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
    """Fetch articles from PubMed using NCBI E-utilities.

    Performs an esearch to retrieve PMIDs, then batches efetch requests
    (max 200 IDs per request) to fetch full article metadata.

    Args:
        query: PubMed search query string (e.g. "cancer immunotherapy").
        max_results: Maximum number of articles to retrieve. Defaults to 500.
        date_range: Optional date range filter in format
                    "YYYY/MM/DD-YYYY/MM/DD" or "YYYY-YYYY".

    Returns:
        List of article dicts, each containing: source, pmid, title, authors,
        journal, pub_date, abstract, doi.

    Raises:
        httpx.HTTPStatusError: If any NCBI request returns an error status.
        ValueError: If the date range format is invalid.
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
