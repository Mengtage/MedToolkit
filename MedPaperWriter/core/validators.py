"""
确定性质量校验（Deterministic Validators）

设计依据：MedPaperWriter 设计审查 3.5 / 6.3 节
    - 学术质量控制不能靠"长度 ≥ 50 字"这类文本清洗规则
    - 能用程序判定的（引用占位、数字保真、缩写定义、因果强度、规范条目缺失、
      跨章节数字冲突）优先用程序判定，LLM 只做逻辑与语言的二次评审

本模块不做医学判断，只做**可复现、可解释、可测试**的规则检查，
避免"用同一个模型的自我评价当作唯一质量门禁"。
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Set

# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

_PLACEHOLDER_PATTERNS = [
    (r"\[待引用[^\]]*\]", "引用占位符"),
    (r"\[待核实[^\]]*\]", "待核实标记"),
    (r"\[引用待补[^\]]*\]", "引用占位符"),
    (r"\[参考文献?[^\]]*\]", "参考文献占位符"),
    (r"\[(?:请)?补充[^\]]*\]", "补充占位符"),
    (r"\[[A-Za-z][^\]]{0,40}(?:to be|TBD)[^\]]*\]", "英文占位符"),
]

_NUMERIC_CITATION = re.compile(r"(?<![\[\d])\[(\d{1,3})(?:[,\-–]\s*\d{1,3})*\](?!\()")
_AUTHOR_YEAR = re.compile(r"[（(]\s*[A-Za-z\u4e00-\u9fa5][^()（）]{1,40}?[，,]\s*(?:19|20)\d{2}[a-z]?\s*[)）]")

# 数字：允许 1,234.5 / 12.3% / -0.45 / 1.2e-3
_NUMBER = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?![\w])")

_ABBREV = re.compile(r"(?<![\w-])([A-Z][A-Za-z0-9]{1,9})(?![\w-])")

_OVERCLAIM = {
    "证明": "使用“证明”属于过强因果表述",
    "证实": "使用“证实”属于过强因果表述",
    "必然": "使用“必然”属于绝对化表述",
    "肯定": "使用“肯定”属于绝对化表述",
    "完全治愈": "疗效表述超出研究设计可支持的范围",
    "显著优于": "需给出统计检验与效应量，避免仅用“显著优于”",
    "无任何副作用": "安全性结论需有不良事件数据支持",
}

_UNIT_HINTS = ("%", "mg", "ml", "kg", "cm", "mm", "mmhg", "周", "天", "月", "年", "例", "人")


def _issue(code: str, severity: str, message: str, excerpt: str = "") -> Dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "excerpt": excerpt.strip()[:120],
    }


def _extract_numbers(text: str) -> List[str]:
    """提取文本中的数字，归一化（去逗号、去尾随 .0）"""
    out: List[str] = []
    for raw in _NUMBER.findall(text or ""):
        token = raw.replace(",", "")
        try:
            value = float(token)
        except ValueError:
            continue
        # 归一化：1.0 -> 1，0.50 -> 0.5
        if abs(value - round(value)) < 1e-9:
            out.append(str(int(round(value))))
        else:
            out.append(f"{value:.6g}")
    return out


def _is_noise_number(token: str, context: str) -> bool:
    """过滤结构性数字：年份、图表编号、章节编号、p 值阈值、置信水平"""
    value = float(token)
    if 1900 <= value <= 2100 and value == int(value):
        return True
    if value in (0, 1, 2, 3, 4, 5, 95, 99, 80, 90, 0.05, 0.5):
        return True
    return False


# ---------------------------------------------------------------------------
# 单项检查
# ---------------------------------------------------------------------------

def check_placeholders(text: str) -> List[Dict[str, str]]:
    """未替换的占位符：这是"导出成品"与"草稿"的分界线"""
    issues: List[Dict[str, str]] = []
    for pattern, label in _PLACEHOLDER_PATTERNS:
        for match in re.finditer(pattern, text or "", re.IGNORECASE):
            issues.append(_issue(
                "placeholder",
                "warning",
                f"存在未处理的{label}",
                match.group(0),
            ))
    return issues


def check_citations(text: str, has_reference_list: bool) -> List[Dict[str, str]]:
    """引用可核验性：编号引用是否能落到参考文献表；作者-年份引用是否可核对"""
    issues: List[Dict[str, str]] = []
    text = text or ""

    numeric = _NUMERIC_CITATION.findall(text)
    author_year = _AUTHOR_YEAR.findall(text)

    if numeric and not has_reference_list:
        issues.append(_issue(
            "citation_unresolved",
            "error",
            f"正文含 {len(numeric)} 处编号引用，但参考文献表为空——编号无法解析",
            str(numeric[:5]),
        ))

    if author_year and not has_reference_list:
        issues.append(_issue(
            "citation_unverified",
            "warning",
            f"正文含 {len(author_year)} 处“作者-年份”引用，需逐条核对是否真实存在",
            str(author_year[:3]),
        ))

    return issues


def check_numbers(text: str, source_text: str, section_kind: str = "") -> List[Dict[str, str]]:
    """数字保真：正文数字必须能在研究方案/统计结果中找到来源

    Results/Methods 的数字应当来自 ResultPack（此处为统计报告与方案原文）；
    其他章节允许出现文献中的数字，因此只在 Methods/Results 上提高严重级别。
    """
    issues: List[Dict[str, str]] = []
    text = text or ""
    source_numbers: Set[str] = set(_extract_numbers(source_text or ""))
    if not text.strip():
        return issues

    missing: List[str] = []
    for match in _NUMBER.finditer(text):
        raw = match.group(0)
        token = raw.replace(",", "")
        try:
            value = float(token)
        except ValueError:
            continue
        if token not in source_numbers and f"{value:.6g}" not in source_numbers:
            if 1900 <= value <= 2100 and value == int(value):
                continue
            if value in (0, 1, 2, 3, 4, 5, 95, 99):
                continue
            missing.append(raw)

    if missing:
        strict = section_kind in ("results", "methods")
        issues.append(_issue(
            "number_untraceable",
            "error" if strict else "warning",
            (
                f"{len(missing)} 个数字未在方案/统计结果中找到来源"
                + ("（结果/方法章节的数字必须可追溯）" if strict else "")
            ),
            ", ".join(missing[:8]),
        ))

    return issues


def check_abbreviations(text: str) -> List[Dict[str, str]]:
    """缩写首次出现应给出全称（“（全称，ABBR）”或 “ABBR（全称）”）"""
    issues: List[Dict[str, str]] = []
    text = text or ""
    common = {"AI", "CI", "OR", "RR", "HR", "SD", "SE", "IQR", "ITT", "PP", "RCT", "BMI",
              "CT", "MRI", "ECG", "ICU", "WHO", "FDA", "SPSS", "SAS", "ROC", "AUC"}
    undefined: List[str] = []
    for match in _ABBREV.finditer(text):
        token = match.group(1)
        if token in common or len(token) < 2:
            continue
        # 全大写且长度 >= 3 才视为缩写，避免误伤普通英文单词
        if token.isupper() and len(token) >= 3:
            window = text[max(0, match.start() - 2): match.end() + 40]
            if not re.search(r"[（(][^）)]{2,}[）)]", window):
                if token not in undefined:
                    undefined.append(token)

    if undefined:
        issues.append(_issue(
            "abbreviation_undefined",
            "info",
            f"{len(undefined)} 个缩写首次出现时未见全称",
            ", ".join(undefined[:8]),
        ))
    return issues


def check_overclaiming(text: str, section_kind: str = "") -> List[Dict[str, str]]:
    """过度因果/绝对化表述"""
    issues: List[Dict[str, str]] = []
    text = text or ""
    hits: List[str] = []
    for word, reason in _OVERCLAIM.items():
        if word in text:
            hits.append(f"{word}（{reason}）")
    if hits:
        issues.append(_issue(
            "overclaim",
            "warning" if section_kind in ("discussion", "conclusion", "abstract", "") else "info",
            f"{len(hits)} 处表述可能超出数据支持范围",
            "; ".join(hits[:4]),
        ))
    return issues


_INTERNAL_JARGON_RE = re.compile(
    r"(?:/api/\w+|/sources\b|/screening\b|/studies\b|/writer\b|\bselected_lineage_complete\b"
    r"|\btableone\b|\bcategorical_auto\b|\bprediction_evaluation_extended\b"
    r"|\bmengtage-owner\b|\baria-gemini-reviewer\b|\bstudy_pmid_\w+|\bSHA256\b|\[E:[A-Za-z0-9_-]+\])"
)


def check_sci_writing_conventions(text: str, section_kind: str = "") -> List[Dict[str, str]]:
    """医学 SCI 论文写作规范检查：
    1. P 值规范：严禁写作 P = 0.000（须写作 P < 0.001）。
    2. 摘要规范：摘要不得包含文献引用编号，且应包含结构化要素（目的/方法/结果/结论）。
    3. 严禁泄露工作台内部路由、哈希或未渲染的 [E:id] 证据标签。
    """
    issues: List[Dict[str, str]] = []
    text = text or ""
    if not text.strip():
        return issues

    p_zero = re.findall(r"\b[Pp]\s*=\s*0\.000+\b", text)
    if p_zero:
        issues.append(_issue(
            "invalid_p_value_zero",
            "error",
            "医学 SCI 统计报告规范禁止将 P 值写作 P = 0.000，应报告为 P < 0.001",
            ", ".join(p_zero[:3]),
        ))

    jargon = _INTERNAL_JARGON_RE.findall(text)
    if jargon:
        issues.append(_issue(
            "internal_pipeline_jargon",
            "error",
            "正文含系统内部路由、哈希、函数名或未转换的 [E:id] 标签，不符合学术论文出版规范",
            ", ".join(dict.fromkeys(jargon))[:120],
        ))

    if section_kind == "abstract":
        if _NUMERIC_CITATION.search(text) or _AUTHOR_YEAR.search(text):
            issues.append(_issue(
                "citation_in_abstract",
                "warning",
                "按 ICMJE 与 SCI 期刊规范，摘要应独立成篇，不应包含文献引用",
                text[:80],
            ))
        lower = text.lower()
        has_struct = (
            sum(any(k in lower for k in grp) for grp in [
                ("目的", "背景", "background", "objective", "purpose"),
                ("方法", "纳入", "检索", "methods", "eligibility"),
                ("结果", "results", "findings"),
                ("结论", "conclusion", "conclusions"),
            ]) >= 3
        )
        if len(text.strip()) >= 80 and not has_struct:
            issues.append(_issue(
                "unstructured_abstract",
                "warning",
                "医学 SCI 摘要建议采用结构化四要素（背景/目的、方法、结果、结论）",
                text[:80],
            ))

    return issues


def check_guideline_completeness(text: str, guideline) -> List[Dict[str, str]]:
    """报告规范必报条目缺失检查（导出前执行）

    Args:
        text: 全文（标题 + 各章节正文）
        guideline: core.reporting_guidelines.ReportingGuideline
    """
    issues: List[Dict[str, str]] = []
    haystack = (text or "").lower()
    missing: List[str] = []
    for item, keywords in getattr(guideline, "key_items", []):
        if not any(kw.lower() in haystack for kw in keywords):
            missing.append(item)

    if missing:
        issues.append(_issue(
            "guideline_incomplete",
            "warning",
            f"{guideline.name} 有 {len(missing)} 个必报条目未在稿件中出现",
            ", ".join(missing),
        ))
    return issues


def check_cross_section_consistency(sections: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    """跨章节数字冲突：同一样本量/人数在不同章节应一致

    Args:
        sections: [{"title": ..., "section_kind": ..., "content": ...}]
    """
    issues: List[Dict[str, str]] = []
    # 只比较“n = 123”“123 例”这类样本量表述
    sample_sizes: Dict[str, List[str]] = {}
    for section in sections:
        content = section.get("content") or ""
        for match in re.finditer(r"(?:n\s*=\s*|共|纳入|随机(?:化)?)\s*(\d{1,5})\s*(?:例|人|名)?", content):
            value = match.group(1)
            sample_sizes.setdefault(value, []).append(section.get("title", ""))

    if len(sample_sizes) > 1:
        detail = "; ".join(f"{value}: {'、'.join(sorted(set(titles)))}" for value, titles in sample_sizes.items())
        issues.append(_issue(
            "sample_size_conflict",
            "warning",
            f"不同章节出现多个样本量（{len(sample_sizes)} 个取值），需确认是否为同一分析人群",
            detail,
        ))

    return issues


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

def validate_section(
    text: str,
    source_text: str = "",
    section_kind: str = "",
    has_reference_list: bool = False,
) -> List[Dict[str, str]]:
    """单章节校验（写作后立即执行，问题随章节一起返回）"""
    issues: List[Dict[str, str]] = []
    issues += check_placeholders(text)
    issues += check_citations(text, has_reference_list)
    issues += check_numbers(text, source_text, section_kind)
    issues += check_abbreviations(text)
    issues += check_overclaiming(text, section_kind)
    issues += check_sci_writing_conventions(text, section_kind)
    return sorted(issues, key=lambda i: SEVERITY_ORDER.get(i["severity"], 9))


def validate_manuscript(session, guideline=None, full_text: str = "") -> List[Dict[str, str]]:
    """整篇校验（导出前执行）"""
    issues: List[Dict[str, str]] = []
    has_refs = bool(getattr(session, "references", []))

    if full_text:
        issues += check_placeholders(full_text)
        issues += check_citations(full_text, has_refs)
        issues += check_sci_writing_conventions(full_text)

    sections: List[Dict[str, str]] = []
    if getattr(session, "outline", None):
        for node in session.iter_outline_nodes():
            if node.content_zh or node.content_en:
                sections.append({
                    "title": node.title,
                    "section_kind": infer_section_kind(node.title),
                    "content": node.content_zh or node.content_en,
                })
    else:
        for section in getattr(session, "sections", []):
            sections.append({
                "title": section.get("chapter") or section.get("title", ""),
                "section_kind": infer_section_kind(section.get("chapter") or section.get("title", "")),
                "content": section.get("content_zh") or section.get("content") or "",
            })

    issues += check_cross_section_consistency(sections)

    if guideline is not None:
        issues += check_guideline_completeness(full_text, guideline)

    return sorted(issues, key=lambda i: SEVERITY_ORDER.get(i["severity"], 9))


def summarize(issues: Iterable[Dict[str, str]]) -> Dict[str, int]:
    """统计各级别问题数量，便于在界面/导出响应中展示"""
    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        severity = issue.get("severity", "info")
        counts[severity] = counts.get(severity, 0) + 1
    counts["total"] = sum(counts.values())
    return counts


# ---------------------------------------------------------------------------
# 章节类型识别（用于选择证据来源与引用策略）
# ---------------------------------------------------------------------------

SECTION_KEYWORDS = [
    ("abstract", ("摘要", "abstract")),
    ("introduction", ("引言", "前言", "背景", "introduction", "background")),
    ("methods", ("方法", "资料与方法", "研究对象", "纳入标准", "检索策略",
                 "样本量", "统计方法", "methods", "materials")),
    ("results", ("结果", "results", "主要结局", "次要结局", "基线特征", "不良事件")),
    ("discussion", ("讨论", "discussion")),
    ("conclusion", ("结论", "conclusions")),
    ("references", ("参考文献", "references")),
]


def infer_section_kind(title: str) -> str:
    """把章节标题映射到章节类型，决定证据来源与引用策略"""
    text = (title or "").strip().lower()
    for kind, keywords in SECTION_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return kind
    return "other"
