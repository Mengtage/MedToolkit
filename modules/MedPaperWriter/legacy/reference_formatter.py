"""
参考文献格式化服务
支持多种参考文献格式
"""

from typing import Dict, Any, Optional


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
            article: 文献信息字典
                - authors: 作者列表或字符串
                - title: 标题
                - journal: 期刊名
                - year: 年份
                - volume: 卷
                - issue: 期
                - pages: 页码
                - doi: DOI

        Returns:
            格式化后的参考文献字符串
        """
        if self.style == "vancouver":
            return self._format_vancouver(article)
        elif self.style == "apa":
            return self._format_apa(article)
        elif self.style == "mla":
            return self._format_mla(article)
        elif self.style == "chicago":
            return self._format_chicago(article)
        elif self.style == "gb7714":
            return self._format_gb7714(article)
        else:
            return self._format_vancouver(article)

    def _format_authors(self, authors: Any, max_display: int = 6) -> str:
        """格式化作者列表"""
        if not authors:
            return ""

        if isinstance(authors, str):
            return authors

        if isinstance(authors, list):
            if len(authors) <= max_display:
                return ", ".join(authors)
            else:
                return ", ".join(authors[:max_display]) + ", et al."

        return str(authors)

    def _format_vancouver(self, article: Dict[str, Any]) -> str:
        """温哥华格式 - Author(s). Title. Journal. Year;Volume(Issue):Pages."""
        authors = self._format_authors(article.get("authors", ""), 6)
        title = article.get("title", "")
        journal = article.get("journal", "")
        year = article.get("year", "")
        volume = article.get("volume", "")
        issue = article.get("issue", "")
        pages = article.get("pages", "")

        parts = [authors]

        if title:
            parts.append(title + ".")

        if journal:
            parts.append(journal + ".")

        if year:
            parts.append(year)

        if volume:
            if issue:
                parts.append(f"{volume}({issue})")
            else:
                parts.append(str(volume))

        if pages:
            parts.append(f":{pages}")

        return " ".join(parts) + "."

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
