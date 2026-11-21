"""
参考文献格式化服务
支持多种参考文献格式

设计依据：MedPaperWriter 设计审查 3.6 节
    MedPaperHunter 输出的是 ``pub_date``、``journal_title``、作者对象列表，
    Writer 早期只认 ``year`` / ``journal`` / 字符串作者，直接传入 Hunter 的
    文章字典会丢年份。这里增加一层规范化（canonical schema adapter），
    让三个子模块的字段差异在入口处被吸收，而不是各写一套。
"""

import re
from typing import Any, Dict, List, Optional


def _author_to_text(author: Any) -> str:
    """把 Hunter / PubMed / 手工录入的作者统一成字符串"""
    if isinstance(author, str):
        return author.strip()
    if isinstance(author, dict):
        # PubMed 风格：LastName + Initials；也兼容 CollectiveName
        if author.get("collective_name") or author.get("CollectiveName"):
            return str(author.get("collective_name") or author.get("CollectiveName"))
        last = author.get("last_name") or author.get("LastName") or author.get("last") or ""
        initials = author.get("initials") or author.get("Initials") or author.get("first") or ""
        name = " ".join(part for part in (last, initials) if part).strip()
        return name or str(author.get("name", "")).strip()
    return str(author)


def _derive_year(article: Dict[str, Any]) -> str:
    """年份字段容错：year / pub_date / publication_date / date"""
    year = article.get("year")
    if year:
        match = re.search(r"(19|20)\d{2}", str(year))
        return match.group(0) if match else str(year)

    for key in ("pub_date", "publication_date", "date", "published_at", "epub_date"):
        value = article.get(key)
        if value:
            match = re.search(r"(19|20)\d{2}", str(value))
            if match:
                return match.group(0)
    return ""


def normalize_reference(article: Dict[str, Any]) -> Dict[str, str]:
    """把不同来源的文献字典规范化为格式化器可消费的字段"""
    authors = article.get("authors") or article.get("author_list") or article.get("author")
    if isinstance(authors, list):
        author_text = ", ".join(filter(None, (_author_to_text(a) for a in authors)))
    else:
        author_text = _author_to_text(authors) if authors else ""

    return {
        "authors": author_text,
        "title": (article.get("title") or "").strip(),
        "journal": (article.get("journal") or article.get("journal_title")
                    or article.get("source") or article.get("ta") or "").strip(),
        "year": _derive_year(article),
        "volume": str(article.get("volume") or "").strip(),
        "issue": str(article.get("issue") or "").strip(),
        "pages": str(article.get("pages") or article.get("page_info") or article.get("pages_or_elocation") or "").strip(),
        "doi": (article.get("doi") or "").strip(),
        "pmid": str(article.get("pmid") or "").strip(),
    }


class ReferenceFormatter:
    """参考文献格式化器"""

    SUPPORTED_STYLES = {
        "vancouver": "温哥华格式（医学期刊，如NEJM、Lancet）",
        "apa": "APA格式（心理学、社会科学）",
        "mla": "MLA格式（人文学科）",
        "chicago": "芝加哥格式（历史学）",
        "gb7714": "GB/T 7714（中文学术期刊）"
    }

    def __init__(self, style: str = "vancouver"):
        self.style = style

    def format_reference(self, article: Dict[str, Any]) -> str:
        """
        格式化参考文献

        Args:
            article: 文献信息字典（字段可来自 PubMed/Hunter/手工录入，
                由 normalize_reference 统一）

        Returns:
            格式化后的参考文献字符串
        """
        article = normalize_reference(article)

        if self.style == "apa":
            return self._format_apa(article)
        if self.style == "mla":
            return self._format_mla(article)
        if self.style == "chicago":
            return self._format_chicago(article)
        if self.style == "gb7714":
            return self._format_gb7714(article)
        return self._format_vancouver(article)

    def format_references(self, references: List[Dict[str, Any]]) -> List[str]:
        return [self.format_reference(ref) for ref in references or []]

    def _format_authors(self, authors: Any, max_display: int = 6) -> str:
        """格式化作者列表（兼容列表或已逗号拼接的字符串，超过 max_display 自动加 et al.）"""
        if not authors:
            return ""

        if isinstance(authors, str):
            names = [a.strip().rstrip(".") for a in authors.split(",") if a.strip()]
        elif isinstance(authors, list):
            names = [a.rstrip(".") for a in (_author_to_text(x) for x in authors) if a]
        else:
            names = [str(authors).strip().rstrip(".")]

        if not names:
            return ""
        if len(names) <= max_display:
            return ", ".join(names)
        return ", ".join(names[:max_display]) + ", et al"

    def _format_vancouver(self, article: Dict[str, Any]) -> str:
        """温哥华格式 (ICMJE / NLM) - Author(s). Title. Journal. Year;Volume(Issue):Pages. doi: xxx. PMID: xxx."""
        authors = self._format_authors(article.get("authors", ""), 6)
        title = (article.get("title", "") or "").strip()
        journal = (article.get("journal", "") or "").strip().rstrip(".")
        year = (article.get("year", "") or "").strip()
        volume = (article.get("volume", "") or "").strip()
        issue = (article.get("issue", "") or "").strip()
        pages = (article.get("pages", "") or "").strip()

        parts: List[str] = []
        if authors:
            parts.append(authors if authors.endswith(".") else authors + ".")

        if title:
            parts.append(title if title[-1] in ".?!" else title + ".")

        if journal:
            parts.append(journal + ".")

        loc = year
        if volume:
            loc += (f";{volume}" if loc else str(volume))
            if issue:
                loc += f"({issue})"
            if pages:
                loc += f":{pages}"
        elif pages:
            loc += (f":{pages}" if loc else pages)
        if loc:
            parts.append(loc if loc.endswith(".") else loc + ".")

        # DOI 是引用可核验性的关键：有就附上，便于读者定位原文
        if article.get("doi"):
            doi_clean = article["doi"].strip().rstrip(".")
            parts.append(f"doi: {doi_clean}.")

        if article.get("pmid"):
            pmid_clean = str(article["pmid"]).strip().rstrip(".")
            parts.append(f"PMID: {pmid_clean}.")

        out = " ".join(parts).strip()
        return out if out.endswith(".") else (out + "." if out else "")

    def _format_apa(self, article: Dict[str, Any]) -> str:
        """APA格式 - Author(s). (Year). Title. Journal, Volume(Issue), Pages."""
        authors = self._format_authors(article.get("authors", ""), 7)
        year = article.get("year", "")
        title = article.get("title", "")
        journal = article.get("journal", "")
        volume = article.get("volume", "")
        issue = article.get("issue", "")
        pages = article.get("pages", "")

        parts = [f"{authors} ({year})."]

        if title:
            parts.append(f"{title}.")

        if journal:
            journal_part = journal
            if volume:
                journal_part += f", {volume}"
                if issue:
                    journal_part += f"({issue})"
            if pages:
                journal_part += f", {pages}"
            parts.append(journal_part + ".")

        return " ".join(parts)

    def _format_mla(self, article: Dict[str, Any]) -> str:
        """MLA格式 - Author(s). "Title." Journal, vol. Volume, no. Issue, Year, pp. Pages."""
        authors = self._format_authors(article.get("authors", ""), 3)
        title = article.get("title", "")
        journal = article.get("journal", "")
        volume = article.get("volume", "")
        issue = article.get("issue", "")
        year = article.get("year", "")
        pages = article.get("pages", "")

        parts = [f"{authors}."]

        if title:
            parts.append(f'"{title}."')

        if journal:
            parts.append(f"{journal},")

        if volume:
            parts.append(f"vol. {volume},")

        if issue:
            parts.append(f"no. {issue},")

        if year:
            parts.append(f"{year},")

        if pages:
            parts.append(f"pp. {pages}.")

        return " ".join(parts)

    def _format_chicago(self, article: Dict[str, Any]) -> str:
        """芝加哥格式 - Author(s). "Title." Journal Volume, no. Issue (Year): Pages."""
        authors = self._format_authors(article.get("authors", ""), 10)
        title = article.get("title", "")
        journal = article.get("journal", "")
        volume = article.get("volume", "")
        issue = article.get("issue", "")
        year = article.get("year", "")
        pages = article.get("pages", "")

        parts = [f"{authors}."]

        if title:
            parts.append(f'"{title}."')

        if journal:
            if volume:
                journal_part = f"{journal} {volume}"
                if issue:
                    journal_part += f", no. {issue}"
                parts.append(journal_part + ",")

        if year:
            parts.append(f"({year}):")

        if pages:
            parts.append(f"{pages}.")

        return " ".join(parts)

    def _format_gb7714(self, article: Dict[str, Any]) -> str:
        """GB/T 7714格式 - 作者. 题名[J]. 期刊名, 年, 卷(期): 页码."""
        authors = self._format_authors(article.get("authors", ""), 10)
        title = article.get("title", "")
        journal = article.get("journal", "")
        year = article.get("year", "")
        volume = article.get("volume", "")
        issue = article.get("issue", "")
        pages = article.get("pages", "")

        parts = [f"{authors}."]

        if title:
            parts.append(f"{title}[J].")

        if journal:
            journal_part = journal
            if year:
                journal_part += f", {year}"
            if volume:
                journal_part += f", {volume}"
                if issue:
                    journal_part += f"({issue})"
            parts.append(journal_part)

        if pages:
            parts.append(f": {pages}.")

        return " ".join(parts)
