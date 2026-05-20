"""
医学文献检索式构建器
=====================

本模块负责将结构化的PICO/PEO概念转化为各数据库的检索式。

核心功能:
    1. PICO/PEO框架支持：干预性研究用PICO，观察性研究用PEO
    2. 多数据库支持：PubMed、Embase、Cochrane Library、Web of Science、arXiv
    3. 检索式生成：根据各数据库语法规则生成检索式
    4. 常用MeSH词速查表：内置常用医学主题词

PICO框架说明:
    - P (Population): 研究人群/患者群体
    - I (Intervention): 干预措施（如药物、治疗方法）
    - C (Comparison): 对照措施（如安慰剂、常规治疗）
    - O (Outcome): 研究结局（如疗效、安全性指标）

PEO框架说明:
    - P (Population): 研究人群
    - E (Exposure): 暴露因素（如风险因素、环境因素）
    - O (Outcome): 研究结局

检索式结构:
    每个概念维度（P/I/C/O/E）生成一个检索组，组内用OR连接所有术语，
    组间用AND连接。

使用示例:
    >>> from medical_search_strategy_builder import MedicalSearchStrategyBuilder
    >>> builder = MedicalSearchStrategyBuilder()
    >>> result = builder.build(
    ...     question="二甲双胍对比GLP-1受体激动剂治疗2型糖尿病的有效性",
    ...     concepts={
    ...         "P": {"name": "Type 2 Diabetes", "mesh": ["Diabetes Mellitus, Type 2"],
    ...               "free_text": ["type 2 diabetes", "T2DM"]},
    ...         "I": {"name": "GLP-1 Receptor Agonists", "mesh": ["Glucagon-Like Peptide-1"],
    ...               "free_text": ["GLP-1", "liraglutide", "semaglutide"]},
    ...         "C": {"name": "Metformin", "mesh": ["Metformin"],
    ...               "free_text": ["metformin"]},
    ...     },
    ...     framework="PICO",
    ...     databases=["pubmed", "wos"],
    ... )
    >>> print(result.strategies["pubmed"])

支持的数据库:
    - pubmed: NCBI PubMed，使用MeSH主题词和自由词
    - embase: Embase数据库，使用Emtree主题词
    - cochrane: Cochrane Library，使用Review Manager格式
    - wos: Web of Science，使用TS字段检索
    - arxiv: arXiv预印本服务器
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 常量与参考数据
# ---------------------------------------------------------------------------

class Framework(str, Enum):
    """分析框架枚举。
    
    PICO: 用于干预性/治疗性研究
    PEO: 用于观察性/病因学研究
    """
    PICO = "PICO"
    PEO = "PEO"


class Database(str, Enum):
    """支持的数据库枚举。
    
    每个数据库有不同的检索语法和特性：
        - pubmed: 使用MeSH主题词和自由词
        - embase: 使用Emtree主题词
        - cochrane: Cochrane Review Manager格式
        - wos: Web of Science核心合集
        - arxiv: 预印本服务器
    """
    PUBMED = "pubmed"
    EMBASE = "embase"
    COCHRANE = "cochrane"
    WOS = "wos"
    ARXIV = "arxiv"


# 常用 MeSH 词速查表
# 提供中文术语到英文MeSH主题词的映射，便于快速查找
COMMON_MESH_TERMS: dict[str, list[str]] = {
    "糖尿病": ["Diabetes Mellitus"],
    "2型糖尿病": ["Diabetes Mellitus, Type 2"],
    "1型糖尿病": ["Diabetes Mellitus, Type 1"],
    "高血压": ["Hypertension"],
    "心力衰竭": ["Heart Failure"],
    "心肌梗死": ["Myocardial Infarction"],
    "肿瘤": ["Neoplasms"],
    "癌症": ["Neoplasms"],
    "随机对照试验": ["Randomized Controlled Trial as Topic"],
    "系统评价": ["Systematic Review as Topic"],
    "荟萃分析": ["Meta-Analysis as Topic"],
    "预后": ["Prognosis"],
    "风险因素": ["Risk Factors"],
    "老年人": ["Aged"],
    "儿童": ["Child"],
    "肥胖": ["Obesity"],
    "哮喘": ["Asthma"],
    "抑郁症": ["Depressive Disorder"],
    "冠心病": ["Coronary Disease"],
    "脑卒中": ["Stroke"],
    "慢性肾病": ["Chronic Kidney Disease"],
    "COVID-19": ["COVID-19"],
    "心房颤动": ["Atrial Fibrillation"],
    "肺炎": ["Pneumonia"],
    "败血症": ["Sepsis"],
}

# 数据库适配提示
# Simplified validation tips (keep concise for better UX)
DATABASE_TIPS: dict[str, list[str]] = {
    "pubmed": [],
    "embase": [],
    "cochrane": [],
    "wos": [],
    "arxiv": [],
}


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class Concept:
    """代表 PICO/PEO 框架中的一个核心概念。
    
    每个概念包含多种类型的检索词：
        - MeSH主题词：规范化的医学主题词，提高检索准确性
        - 自由词：普通文本词汇，提高检索召回率
        - 截词变体：使用*通配符匹配词形变化
    
    Attributes:
        dimension: 概念维度，如 P/I/C/O/E
        name: 概念名称（英文）
        mesh: MeSH/Emtree主题词列表
        free_text: 自由词列表
        truncated: 截词变体列表
    """
    dimension: str              # P / I / C / O / E
    name: str                   # 概念名称 (英文)
    mesh: list[str] = field(default_factory=list)       # MeSH/Emtree 主题词
    free_text: list[str] = field(default_factory=list)  # 自由词
    truncated: list[str] = field(default_factory=list)  # 截词变体

    def all_terms(self) -> list[str]:
        """返回所有检索词（去重并保持顺序）。
        
        Returns:
            合并去重后的所有检索词列表
        """
        seen: set[str] = set()
        result: list[str] = []
        for t in self.mesh + self.free_text + self.truncated:
            low = t.lower()
            if low not in seen:
                seen.add(low)
                result.append(t)
        return result

    def is_valid(self) -> tuple[bool, list[str]]:
        """验证概念是否有效。
        
        检查条件:
            1. 概念名称不能为空
            2. 至少有一个检索词（mesh、free_text 或 truncated）
            3. 检索词数量建议不少于3个（提高召回率）
        
        Returns:
            (是否有效, 错误信息列表)
        """
        errors: list[str] = []
        if not self.name:
            errors.append(f"概念 {self.dimension} 缺少名称")
        if not self.mesh and not self.free_text and not self.truncated:
            errors.append(f"概念 {self.name or self.dimension} 缺少检索词")
        if len(self.mesh) + len(self.free_text) + len(self.truncated) < 3:
            errors.append(f"概念 {self.name or self.dimension} 检索词少于 3 个，可能影响召回率")
        return (len(errors) == 0, errors)

    def normalize(self) -> None:
        """规范化概念数据。
        
        执行以下操作:
            - 去除每个术语的首尾空格
            - 去重并保持原有顺序
            - 过滤空字符串
        """
        self.mesh = list(dict.fromkeys(t.strip() for t in self.mesh if t.strip()))
        self.free_text = list(dict.fromkeys(t.strip() for t in self.free_text if t.strip()))
        self.truncated = list(dict.fromkeys(t.strip() for t in self.truncated if t.strip()))

    def add_mesh(self, term: str) -> None:
        """添加 MeSH 主题词（自动去重）。
        
        Args:
            term: MeSH主题词
        """
        term = term.strip()
        if term and term not in self.mesh:
            self.mesh.append(term)

    def add_free_text(self, term: str) -> None:
        """添加自由词（自动去重）。
        
        Args:
            term: 自由词
        """
        term = term.strip()
        if term and term not in self.free_text:
            self.free_text.append(term)

    def add_truncated(self, term: str) -> None:
        """添加截词变体（自动去重，确保末尾有*）。
        
        Args:
            term: 截词形式的检索词
        """
        term = term.strip().rstrip("*") + "*" if term.strip() else ""
        if term and term not in self.truncated:
            self.truncated.append(term)


@dataclass
class PICOAnalysis:
    """LLM 分析结果的数据模型。"""
    framework: Framework
    research_type: str
    concepts: list[Concept]
    language: str = "en"
    english_question: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典。"""
        return {
            "framework": self.framework.value,
            "research_type": self.research_type,
            "concepts": [
                {
                    "dimension": c.dimension,
                    "name": c.name,
                    "mesh": c.mesh,
                    "free_text": c.free_text,
                    "truncated": c.truncated,
                    "all_terms": c.all_terms(),
                }
                for c in self.concepts
            ],
            "language": self.language,
            "english_question": self.english_question,
        }


@dataclass
class BuildResult:
    """build() 方法的返回值。"""
    question: str
    framework: str
    research_type: str
    concepts: list[dict[str, Any]]
    strategies: dict[str, str]
    validation_tips: list[str]
    language: str = "en"


# ---------------------------------------------------------------------------
# Core Builder
# ---------------------------------------------------------------------------

class MedicalSearchStrategyBuilder:
    """医学文献检索式构建器。
    
    将结构化的PICO/PEO概念转化为各数据库的检索式。
    
    核心功能:
        - 语言检测：自动识别中文/英文输入
        - 框架建议：根据问题类型建议PICO或PEO框架
        - 检索式生成：支持5种数据库的检索式生成
        - MeSH词查找：内置常用MeSH词速查表
        - 结果格式化：生成Markdown报告
    
    Example:
        >>> builder = MedicalSearchStrategyBuilder()
        >>> result = builder.build(
        ...     question="研究问题",
        ...     concepts={"P": {...}, "I": {...}},
        ...     framework="PICO",
        ...     databases=["pubmed", "wos"],
        ... )
    """

    def __init__(self) -> None:
        """初始化检索式构建器。"""
        self._mesh_lookup = COMMON_MESH_TERMS  # 常用MeSH词速查表
        self._synonym_db: dict[str, list[str]] = {}  # 同义词数据库（待扩展）

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_language(self, text: str) -> str:
        """检测输入文本的语言。返回 'zh', 'en', 或 'other'。"""
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if zh_chars > len(text) * 0.1:
            return "zh"
        return "en"

    def suggest_framework(self, question: str) -> Framework:
        """
        根据研究问题建议使用 PICO 还是 PEO 框架。
        干预性/治疗性问题 → PICO；观察性/病因学问题 → PEO。
        """
        q = question.lower()
        observational_keywords = [
            "risk", "association", "incidence", "prevalence",
            "cause", "etiology", "aetiology", "cohort", "case-control",
            "prognostic", "prognosis", "mortality", "morbidity",
            "exposure", "observational",
            "风险", "关联", "发病率", "患病率", "病因", "队列", "病例对照",
            "预后", "暴露", "观察性",
        ]
        interventional_keywords = [
            "efficacy", "effectiveness", "treatment", "therapy",
            "intervention", "randomized", "trial", "drug", "surgery",
            "comparison", "versus", "vs", "placebo",
            "疗效", "有效性", "治疗", "干预", "随机", "试验", "药物",
            "手术", "对比", "对照", "安慰剂",
        ]
        obs_score = sum(1 for kw in observational_keywords if kw in q)
        int_score = sum(1 for kw in interventional_keywords if kw in q)
        if obs_score > int_score:
            return Framework.PEO
        return Framework.PICO

    def build(
        self,
        question: str,
        concepts: dict[str, dict[str, Any]],
        framework: str = "PICO",
        databases: Optional[list[str]] = None,
        research_type: Optional[str] = None,
    ) -> BuildResult:
        """核心方法：生成多数据库检索式。
        
        根据研究问题和PICO/PEO概念定义，为每个指定数据库生成检索式。
        
        处理流程:
            1. 检测输入语言
            2. 确定研究类型（干预性/观察性）
            3. 将概念字典转换为 Concept 对象列表
            4. 对每个概念进行规范化处理
            5. 调用各数据库的检索式生成器
            6. 生成验证提示
            7. 返回 BuildResult 对象
        
        Args:
            question: 研究问题（自然语言，支持中文/英文）
            concepts: 概念字典，key为维度标识(P/I/C/O/E)，value包含:
                - name: 概念名称（英文）
                - mesh: MeSH/Emtree主题词列表
                - free_text: 自由词列表
                - truncated: 截词变体列表（可选）
            framework: 分析框架，"PICO"或"PEO"，默认为"PICO"
            databases: 目标数据库列表，默认所有支持的数据库
            research_type: 研究类型描述（可选）
        
        Returns:
            BuildResult: 包含检索式、概念信息和验证提示的结果对象
        """
        language = self.detect_language(question)

        if databases is None:
            databases = [db.value for db in Database]

        if research_type is None:
            fw = Framework(framework)
            research_type = (
                "interventional / therapeutic" if fw == Framework.PICO
                else "observational / etiological"
            )

        concept_objs: list[Concept] = []
        for dim, data in concepts.items():
            concept_obj = Concept(
                dimension=dim,
                name=data.get("name", ""),
                mesh=data.get("mesh", []),
                free_text=data.get("free_text", []),
                truncated=data.get("truncated", []),
            )
            concept_obj.normalize()
            concept_objs.append(concept_obj)

        strategies: dict[str, str] = {}
        for db in databases:
            generator = _DATABASE_GENERATORS.get(db)
            if generator:
                strategies[db] = generator(concept_objs)

        tips = self._generate_validation_tips(concept_objs, databases)

        concepts_serialized = [
            {
                "dimension": c.dimension,
                "name": c.name,
                "mesh": c.mesh,
                "free_text": c.free_text,
                "truncated": c.truncated,
                "all_terms": c.all_terms(),
            }
            for c in concept_objs
        ]

        return BuildResult(
            question=question,
            framework=framework,
            research_type=research_type,
            concepts=concepts_serialized,
            strategies=strategies,
            validation_tips=tips,
            language=language,
        )

    def build_from_concept_names(
        self,
        question: str,
        concept_names: dict[str, str],
        framework: str = "PICO",
        databases: Optional[list[str]] = None,
    ) -> BuildResult:
        """
        简化版 build：仅提供概念名称，自动查找 MeSH 词。
        适合快速生成或 AI 辅助场景。

        Args:
            question: 研究问题
            concept_names: {"P": "Type 2 Diabetes", "I": "Metformin", ...}
            framework: "PICO" 或 "PEO"
            databases: 数据库列表
        """
        concepts: dict[str, dict[str, Any]] = {}
        for dim, name in concept_names.items():
            mesh = self.lookup_mesh(name)
            concepts[dim] = {
                "name": name,
                "mesh": mesh,
                "free_text": [name],
            }
        return self.build(question, concepts, framework, databases)

    def lookup_mesh(self, term: str) -> list[str]:
        """在常用 MeSH 词表中查找匹配项。"""
        results: list[str] = []
        term_lower = term.lower()
        for cn_term, mesh_list in self._mesh_lookup.items():
            if term_lower in cn_term.lower() or cn_term.lower() in term_lower:
                results.extend(mesh_list)
        return list(dict.fromkeys(results))

    def expand_synonyms(self, term: str) -> list[str]:
        """扩展同义词。"""
        synonyms: list[str] = [term]
        term_lower = term.lower()

        if term_lower in self._synonym_db:
            synonyms.extend(self._synonym_db[term_lower])

        for known_term, syns in self._synonym_db.items():
            if term_lower in known_term or known_term in term_lower:
                synonyms.extend(syns)

        return list(dict.fromkeys(synonyms))

    def validate_concepts(self, concepts: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """验证所有概念的有效性。"""
        results: dict[str, Any] = {"valid": True, "errors": [], "warnings": []}

        for dim, data in concepts.items():
            concept = Concept(
                dimension=dim,
                name=data.get("name", ""),
                mesh=data.get("mesh", []),
                free_text=data.get("free_text", []),
                truncated=data.get("truncated", []),
            )
            is_valid, errors = concept.is_valid()
            if not is_valid:
                results["valid"] = False
                results["errors"].extend(errors)

        return results

    def generate_single_strategy(
        self,
        concept: dict[str, Any],
        database: str,
    ) -> str:
        """为单个概念生成指定数据库的检索式。"""
        concept_obj = Concept(
            dimension=concept.get("dimension", "X"),
            name=concept.get("name", ""),
            mesh=concept.get("mesh", []),
            free_text=concept.get("free_text", []),
            truncated=concept.get("truncated", []),
        )
        generator = _DATABASE_GENERATORS.get(database)
        if generator:
            return generator([concept_obj])
        return ""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _generate_validation_tips(
        self,
        concepts: list[Concept],
        databases: list[str],
    ) -> list[str]:
        return []

    # ------------------------------------------------------------------
    # Output Formatting
    # ------------------------------------------------------------------

    def to_markdown(self, result: BuildResult) -> str:
        """将 BuildResult 格式化为 Markdown 报告。"""
        lines: list[str] = []

        lines.append("## Research Question Analysis\n")
        lines.append(f"**Original question**: {result.question}")
        lines.append(f"**Research type**: {result.research_type}")
        lines.append(f"**Framework**: {result.framework}\n")

        lines.append("### PICO/PEO Breakdown\n")
        lines.append("| Dimension | Content |")
        lines.append("|-----------|---------|")
        dim_labels = {
            "P": "P (Population)", "I": "I (Intervention)",
            "C": "C (Comparison)", "O": "O (Outcome)", "E": "E (Exposure)",
        }
        for c in result.concepts:
            label = dim_labels.get(c["dimension"], c["dimension"])
            terms_str = ", ".join(c["mesh"][:3]) + " ..." if c["mesh"] else ", ".join(c["free_text"][:3])
            lines.append(f"| {label} | {c['name']}: {terms_str} |")
        lines.append("")

        lines.append("---\n")
        lines.append("## Search Term Table\n")
        for c in result.concepts:
            lines.append(f"### Concept {c['dimension']}: {c['name']}\n")
            lines.append("| Type | Terms |")
            lines.append("|------|-------|")
            if c["mesh"]:
                lines.append(f"| MeSH/Subject heading | {' OR '.join(c['mesh'])} |")
            if c["free_text"]:
                lines.append(f"| Free text | {' OR '.join(c['free_text'])} |")
            if c["truncated"]:
                lines.append(f"| Truncated | {' OR '.join(c['truncated'])} |")
            lines.append("")

        lines.append("---\n")
        lines.append("## Search Strategies\n")
        db_display_names = {
            "pubmed": "PubMed", "embase": "Embase",
            "cochrane": "Cochrane Library", "wos": "Web of Science", "arxiv": "arXiv",
        }
        for db_key, strategy in result.strategies.items():
            db_name = db_display_names.get(db_key, db_key)
            lines.append(f"### {db_name}\n")
            lines.append(f"```{db_key}")
            lines.append(strategy)
            lines.append("```\n")

        lines.append("---\n")
        lines.append("## Validation & Optimization Tips\n")
        for i, tip in enumerate(result.validation_tips, 1):
            lines.append(f"{i}. {tip}")

        return "\n".join(lines)

    def to_dict(self, result: BuildResult) -> dict[str, Any]:
        """将 BuildResult 转为普通字典（便于 JSON 序列化）。"""
        from dataclasses import asdict
        return asdict(result)


# ---------------------------------------------------------------------------
# Database-specific strategy generators
# ---------------------------------------------------------------------------

def _generate_pubmed(concepts: list[Concept]) -> str:
    """生成 PubMed 检索式。"""
    lines: list[str] = []
    line_num = 0

    for concept in concepts:
        line_num += 1
        parts: list[str] = []

        # MeSH 主题词（不添加引号，处理带斜杠的复合词如 Spine/surgery）
        for mesh in concept.mesh:
            # 移除已存在的 [MeSH] 后缀，避免重复
            mesh_clean = mesh.rstrip("]").rsplit("[", 1)[0] if "[" in mesh else mesh
            if "/" in mesh_clean:
                # 复合 MeSH 词如 Spine/surgery
                parts.append(f"{mesh_clean}[MeSH]")
            else:
                parts.append(f'"{mesh_clean}"[MeSH]')

        # 自由词 + 截词
        free_parts: list[str] = []
        for ft in concept.free_text:
            if " " in ft:
                # 短语加引号
                free_parts.append(f'"{ft}"[Title/Abstract]')
            else:
                free_parts.append(f'{ft}[Title/Abstract]')
        for tr in concept.truncated:
            free_parts.append(f'{tr}[Title/Abstract]')

        if free_parts:
            parts.append(" OR ".join(free_parts))

        if parts:
            combined = " OR ".join(parts)
            lines.append(f"({combined})")

    # 最终组合（不使用行号引用，直接 AND 连接）
    if lines:
        final = " AND ".join(lines)
        return final

    return ""


def _generate_embase(concepts: list[Concept]) -> str:
    """生成 Embase 检索式。"""
    lines: list[str] = []
    line_num = 0

    def clean_term(term: str) -> str:
        """清理术语，移除 [MeSH] 后缀。"""
        if "[" in term:
            term = term.rstrip("]").rsplit("[", 1)[0]
        return term.replace("'", "").strip()

    for concept in concepts:
        line_num += 1
        parts: list[str] = []

        # Emtree 主题词
        for mesh in concept.mesh:
            clean = clean_term(mesh)
            parts.append(f"'{clean}'/exp")

        # 自由词 + 截词
        free_parts: list[str] = []
        for ft in concept.free_text:
            clean = clean_term(ft)
            free_parts.append(f"'{clean}':ti,ab")
        for tr in concept.truncated:
            clean = clean_term(tr)
            free_parts.append(f"{clean}:ti,ab")

        if free_parts:
            parts.append(" OR ".join(free_parts))

        if parts:
            combined = " OR ".join(parts)
            lines.append(f"#{line_num} {concept.dimension}: ({combined})")

    if lines:
        refs = " AND ".join(f"#{i+1}" for i in range(len(lines)))
        lines.append(f"\n#Final: {refs}")

    return "\n".join(lines)


def _generate_cochrane(concepts: list[Concept]) -> str:
    """生成 Cochrane Library 检索式（Search Manager 格式）。"""
    lines: list[str] = []
    line_num = 0

    def clean_term(term: str) -> str:
        """清理术语，移除 [MeSH] 后缀。"""
        if "[" in term:
            term = term.rstrip("]").rsplit("[", 1)[0]
        return term.replace('"', '').strip()

    for concept in concepts:
        start_num = line_num + 1

        # MeSH 行
        for mesh in concept.mesh:
            clean = clean_term(mesh)
            line_num += 1
            lines.append(f"#{line_num} MeSH descriptor: [{clean}] explode all trees")

        # 自由词行
        free_parts: list[str] = []
        for ft in concept.free_text:
            clean = clean_term(ft)
            free_parts.append(f'"{clean}"')
        for tr in concept.truncated:
            clean = clean_term(tr)
            free_parts.append(clean)

        if free_parts:
            line_num += 1
            free_str = " OR ".join(free_parts)
            lines.append(f"#{line_num} ({free_str}):ti,ab,kw")

        # 组合该概念
        if line_num >= start_num:
            line_num += 1
            refs = " OR ".join(f"#{i}" for i in range(start_num, line_num))
            lines.append(f"#{line_num} {refs}")

    # 最终组合（只组合每个概念的最后一行）
    if line_num > 0:
        # 找到每个概念的组合行
        final_refs = []
        current = line_num
        # 简化：取每个概念块的最后一行
        concept_end_nums = []
        for concept in concepts:
            mesh_count = len(concept.mesh)
            has_free = bool(concept.free_text or concept.truncated)
            if mesh_count + has_free > 1:
                # 有组合行
                concept_end_nums.append(start_num + mesh_count + has_free)
            elif mesh_count == 1 and not has_free:
                concept_end_nums.append(start_num)
            elif has_free and not mesh_count:
                concept_end_nums.append(start_num)
            start_num = concept_end_nums[-1] + 1 if concept_end_nums else start_num

        # 更简洁的方式：重新计算
        concept_final_lines = []
        num = 0
        for concept in concepts:
            block_start = num + 1
            num += len(concept.mesh)
            if concept.free_text or concept.truncated:
                num += 1
            if num > block_start:
                num += 1  # combination line
                concept_final_lines.append(num)
            else:
                concept_final_lines.append(block_start)

        if concept_final_lines:
            refs = " AND ".join(f"#{n}" for n in concept_final_lines)
            lines.append(f"\n#{num + 1} {refs}")

    return "\n".join(lines)


def _generate_wos(concepts: list[Concept]) -> str:
    """生成 Web of Science 检索式。"""
    parts: list[str] = []

    def clean_term(term: str) -> str:
        """清理术语，移除 [MeSH] 后缀。"""
        if "[" in term:
            term = term.rstrip("]").rsplit("[", 1)[0]
        return term.replace('"', '').strip()

    for concept in concepts:
        terms: list[str] = []
        for mesh in concept.mesh:
            clean = clean_term(mesh)
            terms.append(f'"{clean}"')
        for ft in concept.free_text:
            clean = clean_term(ft)
            terms.append(f'"{clean}"')
        for tr in concept.truncated:
            clean = clean_term(tr)
            terms.append(clean)

        if terms:
            ts_content = " OR ".join(terms)
            parts.append(f"TS=({ts_content})")

    return " AND ".join(parts)


def _generate_arxiv(concepts: list[Concept]) -> str:
    """生成 arXiv 检索式。
    
    arXiv 检索规则：
    - 支持的字段：ti (title), au (author), abs(abstract), cat (subject category), all (all fields)
    - 短语匹配使用双引号：ti:"deep learning"
    - 通配符使用 *：all:learn*
    - 布尔操作符：AND, OR, ANDNOT（必须大写）
    - 不支持 MeSH 格式，需清理 [MeSH] 后缀
    """
    parts: list[str] = []

    def clean_term(term: str) -> str:
        """清理术语，移除 [MeSH] 后缀和引号。"""
        # 移除已存在的 [MeSH] 或其他字段后缀
        if "[" in term:
            term = term.rstrip("]").rsplit("[", 1)[0]
        # 移除术语中的引号，避免嵌套
        return term.replace('"', '').strip()

    for concept in concepts:
        terms: list[str] = []
        
        # MeSH 术语（arXiv 不支持 MeSH，作为普通文本处理）
        for mesh in concept.mesh:
            clean = clean_term(mesh)
            if clean:
                terms.append(f'ti:"{clean}"')
                terms.append(f'abs:"{clean}"')
        
        # 自由词
        for ft in concept.free_text:
            clean = clean_term(ft)
            if clean:
                terms.append(f'ti:"{clean}"')
                terms.append(f'abs:"{clean}"')
        
        # 截词变体（使用 all 字段）
        for tr in concept.truncated:
            clean = clean_term(tr)
            if clean:
                terms.append(f"all:{clean}")

        if terms:
            combined = " OR ".join(dict.fromkeys(terms))  # 去重保序
            parts.append(f"({combined})")

    return " AND ".join(parts)


# 数据库生成器注册表
_DATABASE_GENERATORS: dict[str, Any] = {
    "pubmed": _generate_pubmed,
    "embase": _generate_embase,
    "cochrane": _generate_cochrane,
    "wos": _generate_wos,
    "arxiv": _generate_arxiv,
}
