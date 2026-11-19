"""
报告规范路由、确定性校验与文献字段适配的单元测试
"""

import pytest

from core.reporting_guidelines import GUIDELINES, resolve
from core.reference_formatter import ReferenceFormatter, normalize_reference
from core.validators import (
    check_abbreviations,
    check_citations,
    check_cross_section_consistency,
    check_guideline_completeness,
    check_numbers,
    check_placeholders,
    infer_section_kind,
    summarize,
    validate_manuscript,
)
from services.session_manager import OutlineNode, Session, SessionMode
from services.writing import truncate_preserving_structure, unified_diff


# --------------------------------------------------------------------------- 路由
@pytest.mark.parametrize("study_type,expected", [
    ("系统评价", "prisma_2020"),
    ("Meta分析", "prisma_2020"),
    ("随机对照试验", "consort_2025"),
    ("RCT", "consort_2025"),
    ("观察性研究", "strobe"),
    ("队列研究", "strobe"),
    ("诊断准确性研究", "stard_2015"),
    ("临床预测模型", "tripod"),
    ("叙述性综述", "narrative_review"),
])
def test_guideline_routing(study_type, expected):
    guideline, _ = resolve(study_type)
    assert guideline.id == expected


def test_bare_review_is_flagged_not_silently_prisma():
    """只写“综述”时按 PRISMA 生成，但必须提示可能与叙述性综述不符"""
    guideline, note = resolve("综述")
    assert guideline.id == "prisma_2020"
    assert "叙述性综述" in note


def test_unknown_study_type_falls_back_with_warning():
    guideline, note = resolve("某种没听过的研究")
    assert guideline.id == "prisma_2020"
    assert "无法识别" in note


def test_guideline_registry_has_sources_and_items():
    for guideline in GUIDELINES.values():
        assert guideline.source and guideline.version
        assert guideline.key_items, f"{guideline.id} 缺少必报条目"


# --------------------------------------------------------------------------- 校验
def test_placeholder_is_detected():
    issues = check_placeholders("如表1所示[待引用-指南]，干预有效。")
    assert any(issue["code"] == "placeholder" for issue in issues)


def test_numeric_citation_without_reference_list_is_error():
    issues = check_citations("既往研究显示有效[1,2]。", has_reference_list=False)
    assert any(issue["code"] == "citation_unresolved" and issue["severity"] == "error" for issue in issues)

    ok = check_citations("既往研究显示有效[1,2]。", has_reference_list=True)
    assert not ok


def test_numbers_must_be_traceable_in_results():
    text = "共纳入 240 例，主要结局差异 3.5。"
    source = "共纳入 240 例。"
    issues = check_numbers(text, source, section_kind="results")
    assert any(issue["code"] == "number_untraceable" and issue["severity"] == "error" for issue in issues)

    clean = check_numbers(text, "共纳入 240 例，差异 3.5。", section_kind="results")
    assert not clean


def test_numbers_are_lenient_in_discussion():
    issues = check_numbers("一项纳入 5000 例的研究报告了风险。", "共纳入 240 例。", section_kind="discussion")
    assert all(issue["severity"] != "error" for issue in issues)


def test_abbreviation_without_expansion_is_info():
    issues = check_abbreviations("采用 PCSK9 抑制剂治疗。")
    assert issues and issues[0]["code"] == "abbreviation_undefined"

    defined = check_abbreviations("采用前蛋白转化酶枯草溶菌素9（PCSK9）抑制剂治疗。")
    assert not defined


def test_guideline_completeness_lists_missing_items():
    text = "随机 双盲 主要结局 基线 流程图"
    issues = check_guideline_completeness(text, GUIDELINES["consort_2025"])
    assert issues and issues[0]["code"] == "guideline_incomplete"
    assert "分配隐藏" in issues[0]["excerpt"]


def test_cross_section_sample_size_conflict():
    sections = [
        {"title": "结果", "content": "共纳入 240 例患者。"},
        {"title": "讨论", "content": "本研究纳入 210 例患者。"},
    ]
    issues = check_cross_section_consistency(sections)
    assert issues and issues[0]["code"] == "sample_size_conflict"


def test_validate_manuscript_collects_session_issues():
    session = Session(SessionMode.REVIEW)
    root = OutlineNode(0, "论文提纲")
    session.outline = root
    node = OutlineNode(1, "结果", root)
    node.content_zh = "共纳入 240 例[待引用-样本量]。"
    session.references = []

    issues = validate_manuscript(session, GUIDELINES["prisma_2020"], full_text="共纳入 240 例[待引用-样本量]。")
    codes = {issue["code"] for issue in issues}
    assert "placeholder" in codes
    assert "guideline_incomplete" in codes
    assert summarize(issues)["total"] == len(issues)


def test_infer_section_kind():
    assert infer_section_kind("3.2 研究方法") == "methods"
    assert infer_section_kind("Results") == "results"
    assert infer_section_kind("亚组分析") == "other"


# --------------------------------------------------------------------------- 上下文
def test_truncate_keeps_head_tail_and_priority():
    text = "\n\n".join([f"普通段落{i}" * 20 for i in range(6)] + ["样本量：共 240 例"] + [f"结尾段落{i}" * 20 for i in range(3)])
    result = truncate_preserving_structure(text, 400)
    assert len(result) <= 400 + 100
    assert "普通段落0" in result          # 保留开头
    assert "结尾段落2" in result          # 保留结尾
    assert "样本量：共 240 例" in result   # 关键事实优先


def test_truncate_noop_when_short():
    assert truncate_preserving_structure("短文本", 100) == "短文本"


def test_unified_diff_counts_lines():
    diff = unified_diff("第一行\n第二行", "第一行\n第二行\n第三行")
    assert diff["has_changes"] is True
    assert diff["added_lines"] == 1
    assert "第三行" in diff["unified"]


# --------------------------------------------------------------------------- 文献适配
def test_normalize_hunter_reference():
    ref = normalize_reference({
        "title": "A trial",
        "authors": [{"last_name": "Zhang", "initials": "Y"}, {"collective_name": "XYZ Group"}],
        "journal_title": "Lancet",
        "pub_date": "2021-05-03",
        "doi": "10.1000/x",
        "pages": "1-10",
    })
    assert ref["year"] == "2021"
    assert ref["journal"] == "Lancet"
    assert "Zhang Y" in ref["authors"]
    assert "XYZ Group" in ref["authors"]


def test_vancouver_includes_doi_and_year():
    formatted = ReferenceFormatter("vancouver").format_reference({
        "title": "A trial",
        "authors": "Zhang Y, Li M",
        "journal": "Lancet",
        "pub_date": "2021",
        "doi": "10.1000/x",
    })
    assert "2021" in formatted
    assert "doi: 10.1000/x" in formatted


def test_format_references_batch():
    formatted = ReferenceFormatter("gb7714").format_references([
        {"title": "甲", "authors": "张三", "journal": "中华医学杂志", "year": "2020"},
        {"title": "乙", "authors": "李四", "journal": "中国循环杂志", "year": "2021"},
    ])
    assert len(formatted) == 2
    assert all("[J]" in item for item in formatted)
