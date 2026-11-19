"""MedPaperHunter 核心纯函数单元测试。

覆盖本次修复的重点：
    1. DOI 去重（deduplicate_by_doi / _normalize_doi）
    2. LLM 筛选解析（JSON 逐篇对号、错位防护、截断容错、UNPARSED 显式上报）
    3. 日期范围解析（多格式、非法月份、跨分隔符）

运行方式（在 backend/ 目录下）：
    python -m pytest test_core_fixes.py -v
"""

from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

from dedup import (
    UNPARSED,
    _normalize_doi,
    _parse_screening_response,
    deduplicate_by_doi,
    deduplicate_by_pmid,
    deduplicate_by_title,
    llm_screen,
)
from pubmed_fetcher import _parse_date_range


# ---------------------------------------------------------------------------
# DOI 去重
# ---------------------------------------------------------------------------

class TestNormalizeDoi:
    def test_plain(self):
        assert _normalize_doi("10.1234/ABC.2024.567") == "10.1234/abc.2024.567"

    def test_url_prefix(self):
        assert _normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"

    def test_http_prefix(self):
        assert _normalize_doi("http://doi.org/10.1234/abc") == "10.1234/abc"

    def test_dx_and_bare(self):
        assert _normalize_doi("dx.doi.org/10.1234/abc") == "10.1234/abc"
        assert _normalize_doi("doi:10.1234/abc") == "10.1234/abc"

    def test_none_and_empty(self):
        assert _normalize_doi(None) == ""
        assert _normalize_doi("") == ""
        assert _normalize_doi("   ") == ""

    def test_trailing_dot(self):
        assert _normalize_doi("10.1234/abc.") == "10.1234/abc"


class TestDedupByDoi:
    def _article(self, doi=None, title="t", abstract=""):
        return {"source": "import", "pmid": None, "title": title,
                "authors": [], "journal": "", "pub_date": "",
                "abstract": abstract, "doi": doi}

    def test_cross_database_doi_dup(self):
        """同一文献从 PubMed 和 WoS 导入：PMID 不同、标题写法不同、DOI 相同 → 应合并。"""
        a = self._article(doi="10.1234/abc", title="Effect of metformin on T2DM")
        b = self._article(doi="https://doi.org/10.1234/ABC.", title="Effect of Metformin on T2DM!")
        out = deduplicate_by_doi([a, b])
        assert len(out) == 1

    def test_keeps_most_complete(self):
        a = self._article(doi="10.1234/abc", abstract="full abstract here")
        b = self._article(doi="10.1234/abc", abstract="")
        out = deduplicate_by_doi([a, b])
        assert len(out) == 1
        assert out[0]["abstract"] == "full abstract here"

    def test_no_doi_passthrough(self):
        a = self._article(doi=None)
        b = self._article(doi="")
        out = deduplicate_by_doi([a, b])
        assert len(out) == 2

    def test_full_chain_pmid_doi_title(self):
        """PMID → DOI → 标题 全链路：跨库三重重复只留一篇。"""
        a = {"source": "pubmed", "pmid": "111", "title": "Same Study",
             "authors": ["A B"], "journal": "J", "pub_date": "2024",
             "abstract": "abs", "doi": "10.1234/x"}
        b = {"source": "wos", "pmid": None, "title": "same study",
             "authors": ["A B"], "journal": "J", "pub_date": "2024",
             "abstract": "abs", "doi": "https://doi.org/10.1234/X"}
        c = {"source": "embase", "pmid": None, "title": "Same  Study!",
             "authors": [], "journal": "", "pub_date": "",
             "abstract": "", "doi": None}
        out = deduplicate_by_title(deduplicate_by_doi(deduplicate_by_pmid([a, b, c])))
        assert len(out) == 1


# ---------------------------------------------------------------------------
# LLM 筛选解析
# ---------------------------------------------------------------------------

BATCH = [
    {"title": f"Article {i}", "abstract": f"Abstract {i}"}
    for i in range(1, 4)
]


class TestParseScreeningResponse:
    def test_perfect_json(self):
        resp = '[{"index":1,"answer":"YES","reason":"相关"},{"index":2,"answer":"NO","reason":"不相关"},{"index":3,"answer":"YES","reason":"相关"}]'
        results, n = _parse_screening_response(resp, BATCH)
        assert n == 3
        assert [r["screening_result"] for r in results] == ["YES", "NO", "YES"]

    def test_markdown_fence_wrapped(self):
        resp = '```json\n[{"index":1,"answer":"YES","reason":"r"},{"index":2,"answer":"NO","reason":"r"},{"index":3,"answer":"YES","reason":"r"}]\n```'
        results, n = _parse_screening_response(resp, BATCH)
        assert n == 3

    def test_out_of_order_index_no_misattribution(self):
        """乱序 index 也按序号对号，不按出现顺序。"""
        resp = '[{"index":3,"answer":"NO","reason":"r3"},{"index":1,"answer":"YES","reason":"r1"},{"index":2,"answer":"YES","reason":"r2"}]'
        results, n = _parse_screening_response(resp, BATCH)
        assert n == 3
        assert results[0]["screening_result"] == "YES"
        assert results[2]["screening_result"] == "NO"

    def test_missing_article_marked_unparsed(self):
        """LLM 漏答第 2 篇：第 2 篇必须标 UNPARSED，绝不允许错位借用。"""
        resp = '[{"index":1,"answer":"YES","reason":"r1"},{"index":3,"answer":"NO","reason":"r3"}]'
        results, n = _parse_screening_response(resp, BATCH)
        assert n == 2
        assert results[0]["screening_result"] == "YES"
        assert results[1]["screening_result"] == UNPARSED
        assert results[2]["screening_result"] == "NO"

    def test_out_of_range_index_ignored(self):
        """index 越界（如 4）必须被丢弃，不得占用任何文献的判定。"""
        resp = '[{"index":1,"answer":"YES","reason":"r"},{"index":2,"answer":"YES","reason":"r"},{"index":3,"answer":"YES","reason":"r"},{"index":4,"answer":"NO","reason":"bad"}]'
        results, n = _parse_screening_response(resp, BATCH)
        assert n == 3
        assert all(r["screening_result"] == "YES" for r in results)

    def test_truncated_json_recovered(self):
        """响应被 max_tokens 截断：能恢复前几篇，剩余为 UNPARSED。"""
        resp = '[{"index":1,"answer":"YES","reason":"这是一段很长的理由"},{"index":2,"answer":"NO","reason":"另一段理由"},{"index":3,"ans'
        results, n = _parse_screening_response(resp, BATCH)
        assert n >= 2
        assert results[2]["screening_result"] == UNPARSED

    def test_garbage_response_all_unparsed(self):
        results, n = _parse_screening_response("I think these articles are great!", BATCH)
        assert n == 0
        assert all(r["screening_result"] == UNPARSED for r in results)

    def test_string_index_tolerated(self):
        resp = '[{"index":"1","answer":"YES","reason":"r"},{"index":"2","answer":"NO","reason":"r"},{"index":"3","answer":"YES","reason":"r"}]'
        results, n = _parse_screening_response(resp, BATCH)
        assert n == 3

    def test_invalid_answer_rejected(self):
        """answer 不是 YES/NO 的条目不能占用该 index。"""
        resp = '[{"index":1,"answer":"MAYBE","reason":"r"},{"index":1,"answer":"YES","reason":"r"},{"index":2,"answer":"NO","reason":"r"},{"index":3,"answer":"YES","reason":"r"}]'
        results, n = _parse_screening_response(resp, BATCH)
        assert n == 3
        assert results[0]["screening_result"] == "YES"


class _FakeLLM:
    """按调用顺序依次返回预设响应，模拟真实 LLM 客户端。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def chat(self, messages):
        resp = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return resp


class TestLLMScreen:
    def test_retry_on_incomplete_parse(self):
        """第一次响应不完整 → 自动重试 → 第二次补齐；全部文献都有判定。"""
        bad = '[{"index":1,"answer":"YES","reason":"r1"},{"index":3,"answer":"YES","reason":"r3"}]'
        good = '[{"index":1,"answer":"YES","reason":"r1"},{"index":2,"answer":"NO","reason":"r2"},{"index":3,"answer":"YES","reason":"r3"}]'
        client = _FakeLLM([bad, good])

        articles = [
            {"title": f"A{i}", "abstract": f"B{i}"} for i in range(1, 4)
        ]
        out = asyncio.run(llm_screen(articles, client, "test question"))
        assert client.calls == 2
        assert all(a["screening_result"] in ("YES", "NO") for a in out)
        assert len(out) == 3

    def test_unparsed_survives_after_retry(self):
        bad = "garbage"
        bad2 = '[{"index":1,"answer":"YES","reason":"r"}]'
        client = _FakeLLM([bad, bad2])
        articles = [{"title": f"A{i}", "abstract": f"B{i}"} for i in range(1, 3)]
        out = asyncio.run(llm_screen(articles, client, "q"))
        assert client.calls == 2
        assert out[0]["screening_result"] == "YES"
        assert out[1]["screening_result"] == UNPARSED

    def test_empty_input(self):
        client = _FakeLLM([])
        assert asyncio.run(llm_screen([], client, "q")) == []


# ---------------------------------------------------------------------------
# 日期范围解析
# ---------------------------------------------------------------------------

class TestParseDateRange:
    def test_year_only(self):
        assert _parse_date_range("2020-2024") == ("2020/01/01", "2024/12/31")

    def test_year_month(self):
        assert _parse_date_range("2020/01-2024/12") == ("2020/01/01", "2024/12/31")

    def test_full_dates(self):
        assert _parse_date_range("2020/01/01-2024/12/31") == ("2020/01/01", "2024/12/31")

    def test_hyphen_dates(self):
        """含 '-' 的日期分隔符（旧实现会因 split('-') 产出 4 段而报错）。"""
        assert _parse_date_range("2020-01-01 - 2024-12-31") == ("2020/01/01", "2024/12/31")
        assert _parse_date_range("2020-01-01-2024-12-31") == ("2020/01/01", "2024/12/31")

    def test_leap_year_february_end(self):
        """2 月末自动补齐为真实月末（闰年 29 天），不再是非法的 31 日。"""
        assert _parse_date_range("2024/02-2024/02")[1] == "2024/02/29"
        assert _parse_date_range("2023/02-2023/02")[1] == "2023/02/28"

    def test_empty(self):
        assert _parse_date_range("") == ("", "")
        assert _parse_date_range("   ") == ("", "")

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            _parse_date_range("last year to now")

    def test_invalid_month_raises(self):
        with pytest.raises(ValueError):
            _parse_date_range("2020/13-2024/12")

    def test_reversed_range_raises(self):
        with pytest.raises(ValueError):
            _parse_date_range("2024-2020")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
