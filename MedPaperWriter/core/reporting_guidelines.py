"""
报告规范注册表（Reporting Guideline Registry）

设计依据：MedPaperWriter 设计审查 3.4 节——报告规范不能是"除综述外一律 CONSORT"
的 if-else，也不能只是大段静态提示词，而应是**版本化、带适用范围、可核验**的规则包。

每个规则包记录：来源、版本、适用研究类型、提纲结构、必报条目。
必报条目同时被两处消费：
    1. 提纲生成（决定章节骨架）
    2. 导出前的完整性检查（core/validators.py）

注意：报告规范是"应报告什么"，不是研究质量评价工具（EQUATOR 明确区分）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ReportingGuideline:
    """一个版本化的报告规范规则包"""

    id: str
    name: str
    version: str
    source: str
    applies_to: str
    structure: str
    # 必报条目：(条目名, 检索关键词)。关键词用于导出前的存在性检查。
    key_items: List[Tuple[str, List[str]]] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "applies_to": self.applies_to,
            "key_items": [item for item, _ in self.key_items],
        }


_PRISMA_STRUCTURE = """
PRISMA 2020 系统评价标准结构：
1. 摘要
   1.1 结构化摘要（目的、方法、结果、结论）
   1.2 注册号与资助
2. 引言
   2.1 研究背景与领域重要性
   2.2 已有系统评价及其局限
   2.3 本评价的目的与研究问题（PICOS）
3. 方法
   3.1 研究方案与注册（PROSPERO 等）
   3.2 纳入与排除标准
   3.3 信息来源与检索策略（数据库、检索式、检索日期）
   3.4 研究选择流程
   3.5 数据提取与编码规则
   3.6 偏倚风险评估工具（RoB 2 / ROBINS-I / NOS）
   3.7 效应指标与数据合成方法（异质性、模型选择）
   3.8 亚组分析与敏感性分析计划
   3.9 发表偏倚评估方法
   3.10 证据确定性评价（GRADE）
4. 结果
   4.1 研究选择流程与 PRISMA 流程图
   4.2 纳入研究特征
   4.3 偏倚风险评价结果
   4.4 各结局的合成结果（效应量、95%CI、异质性 I²）
   4.5 亚组与敏感性分析
   4.6 发表偏倚
   4.7 证据确定性
5. 讨论
   5.1 主要发现总结
   5.2 与已有证据的比较
   5.3 证据的局限性与不确定性
   5.4 适用性（外推性）
   5.5 结论与意义
6. 其他信息
   6.1 注册与方案偏离说明
   6.2 资助与利益冲突
   6.3 数据与代码可用性
"""

_CONSORT_STRUCTURE = """
CONSORT 2025 随机对照试验标准结构：
1. 摘要
   1.1 结构化摘要（背景、方法、结果、结论）
   1.2 试验注册号
2. 引言
   2.1 背景与科学问题
   2.2 研究假设
3. 方法
   3.1 试验设计（平行/交叉/析因/整群）
   3.2 受试者（纳入、排除、研究中心）
   3.3 随机化（序列生成方法、分配隐藏、区组）
   3.4 盲法（对象、实施方式、盲法成功性评估）
   3.5 干预措施（各组方案、依从性管理）
   3.6 结局指标（主要结局定义与测量时点、次要结局、安全性结局）
   3.7 样本量计算（α、把握度、效应量假设、脱落率）
   3.8 统计分析计划（主要分析方法、亚组、缺失值处理）
   3.9 伦理与知情同意
4. 结果
   4.1 受试者流程（筛选、随机、随访、完成、脱落；流程图）
   4.2 招募与随访时间
   4.3 基线特征（各组人数与临床特征）
   4.4 干预依从性
   4.5 主要结局（各组结果、效应量、95%CI、P 值）
   4.6 次要结局与亚组分析
   4.7 不良事件与安全性
5. 讨论
   5.1 主要发现
   5.2 与已有证据比较
   5.3 优势与局限性（内部真实性、外部适用性）
   5.4 解释与临床意义
   5.5 结论
6. 其他信息
   6.1 试验注册与方案偏离
   6.2 资助与利益冲突
   6.3 数据可用性
"""

_STROBE_STRUCTURE = """
STROBE 观察性研究标准结构：
1. 摘要
2. 引言
   2.1 背景
   2.2 研究目的与假设
3. 方法
   3.1 研究设计（队列/病例对照/横断面）
   3.2 研究现场与时间
   3.3 研究对象（纳入排除、匹配、样本量依据）
   3.4 变量定义（暴露、结局、混杂因素）
   3.5 数据来源与测量方法
   3.6 偏倚控制
   3.7 样本量
   3.8 统计方法（含混杂调整与亚组）
4. 结果
   4.1 研究对象流程与人数
   4.2 基线特征
   4.3 结局数据
   4.4 主要结果（效应量、95%CI、调整变量）
   4.5 其他分析（亚组、敏感性）
5. 讨论
   5.1 主要结果
   5.2 局限性（偏倚、混杂、外推）
   5.3 解释
6. 其他信息（资助、数据可用性）
"""

_STARD_STRUCTURE = """
STARD 2015 诊断准确性研究标准结构：
1. 摘要
2. 引言（临床问题、目标人群、研究目的）
3. 方法
   3.1 研究设计（前瞻/回顾、单中心/多中心）
   3.2 受试者（纳入排除、疾病谱）
   3.3 待评价试验（操作、判读、阈值）
   3.4 参考标准（定义与实施）
   3.5 盲法
   3.6 样本量
   3.7 统计方法（灵敏度、特异度、似然比、ROC/AUC）
4. 结果
   4.1 受试者流程
   4.2 基线特征
   4.3 诊断准确性结果（2×2 表、灵敏度、特异度、95%CI）
   4.4 不确定结果与不良事件
5. 讨论（局限性、临床适用性）
6. 其他信息
"""

_TRIPOD_STRUCTURE = """
TRIPOD 临床预测模型标准结构：
1. 摘要
2. 引言（临床需求、已有模型、研究目的）
3. 方法
   3.1 数据来源与设计
   3.2 研究对象（纳入排除、结局定义）
   3.3 预测因子（定义、测量、可用性）
   3.4 样本量与事件数
   3.5 缺失数据处理
   3.6 模型构建（变量筛选、模型类型、内部验证）
   3.7 模型性能（区分度 C 统计量、校准、临床效用）
   3.8 公平性与亚组
4. 结果
   4.1 受试者流程与基线
   4.2 模型参数（回归系数/系数图）
   4.3 模型性能（AUC、校准曲线、DCA）
   4.4 亚组表现
5. 讨论（与已有模型比较、局限性、临床应用）
6. 其他信息（注册、数据与代码可用性）
"""

_NARRATIVE_STRUCTURE = """
叙述性综述结构（不套用 PRISMA，检索过程不作强制要求）：
1. 摘要
2. 引言
   2.1 主题背景与重要性
   2.2 综述范围与读者定位
3. 正文（按主题或时间线组织，2-5 个主题章节）
   3.1 主题一：概念界定与现状
   3.2 主题二：证据与争议
   3.3 主题三：实践启示
4. 讨论
   4.1 证据的整体解读
   4.2 争议与不确定性
   4.3 局限（非系统检索带来的选择性偏倚）
5. 结论与展望
6. 参考文献
"""

_PRISMA_SCR_STRUCTURE = """
PRISMA-ScR 范围综述（Scoping Review）标准结构（Tricco et al., Ann Intern Med 2018）：
1. 摘要（结构化摘要）
   1.1 背景与目的（Background & Objectives）
   1.2 纳入标准与信息来源（Eligibility Criteria [PCC] & Information Sources）
   1.3 证据筛选与数据绘制方法（Study Selection & Data Charting）
   1.4 结果（Results）
   1.5 结论（Conclusions）
2. 引言（Introduction）
   2.1 临床背景与证据转化张力（Rationale）
   2.2 研究目的与 PCC 框架问题（Objectives: Population, Concept, Context）
3. 方法（Methods）
   3.1 方法学框架与报告规范（Protocol & Reporting Framework: Arksey & O'Malley / JBI / PRISMA-ScR）
   3.2 纳入与排除标准（Eligibility Criteria — PCC 框架）
   3.3 信息来源与完整检索策略（Information Sources & Full Search Strategy）
   3.4 文献去重与证据筛选流程（Deduplication & Selection of Sources of Evidence）
   3.5 数据提取、报告—研究归并与证据综合方法（Data Charting Process, Study Mapping & Synthesis of Results）
4. 结果（Results）
   4.1 文献检索与筛选流程（Selection of Sources of Evidence & PRISMA Flow Diagram）
   4.2 纳入研究的总体特征与方法学基线（Characteristics of Included Studies）
   4.3 按核心临床或技术维度的证据综合（Synthesis of Results by Clinical/Technical Domain）
   4.4 方法学成熟度、外部验证与临床效用映射（Methodological Maturity, Validation & Clinical Utility）
5. 讨论（Discussion）
   5.1 主要研究发现总结（Summary of Evidence）
   5.2 关键临床与方法学机制剖析（Mechanistic & Methodological Interpretation）
   5.3 证据库与本范围综述的局限性（Strengths and Limitations）
   5.4 临床实践启示与未来研究方向（Implications for Practice and Future Research）
6. 结论（Conclusions）
7. 声明（Declarations：伦理、资助、利益冲突与数据可用性）
8. 参考文献（References — Vancouver 格式）
"""

_TRIPOD_AI_STRUCTURE = """
TRIPOD+AI 临床人工智能/机器学习预测模型标准结构（Collins et al., BMJ 2024）：
1. 结构化摘要（背景、目的、设计与数据源、建模与验证人群、预测因子与模型架构、区分度/校准/临床效用、结论）
2. 引言（临床场景与决策痛点、现有模型局限、本研究预期临床用途与目标人群）
3. 方法
   3.1 数据来源、研究设计与伦理审批
   3.2 研究人群与纳入排除标准
   3.3 结局定义、测量方式与盲法评估
   3.4 候选预测因子、信号预处理与防数据泄露（Data Leakage Prevention）
   3.5 样本量、事件数（EPV）与缺失数据处理策略
   3.6 模型架构、超参数调优与训练策略
   3.7 模型评估指标（区分度 AUROC/AUPRC、校准曲线/Brier 分数、临床效用 DCA、重分类 NRI/IDI）
   3.8 内部验证、外部/时间验证与亚组公平性审计（Algorithmic Fairness）
4. 结果
   4.1 研究队列纳入流程与基线特征（训练集 vs 验证集 Table 1）
   4.2 模型构建、特征重要性或可解释性分析（SHAP / 注意力权重）
   4.3 模型区分度、校准度与决策曲线净获益（DCA）
   4.4 亚组表现、公平性审计与敏感性分析
5. 讨论（核心发现、与既往模型对比、域偏移与校准漂移机制、局限性、临床部署路径）
6. 结论与声明（伦理、资助、利益冲突、数据与模型代码可用性）
"""


GUIDELINES: Dict[str, ReportingGuideline] = {
    "prisma_2020": ReportingGuideline(
        id="prisma_2020",
        name="PRISMA 2020",
        version="2020",
        source="https://www.prisma-statement.org/",
        applies_to="系统评价与 Meta 分析",
        structure=_PRISMA_STRUCTURE,
        aliases=[
            "prisma", "系统评价", "系统综述", "meta", "meta分析", "meta-analysis",
            "荟萃分析", "systematic review", "综述",
        ],
        key_items=[
            ("研究方案注册", ["注册", "prospero", "registration"]),
            ("纳入排除标准", ["纳入标准", "排除标准", "eligibility"]),
            ("检索策略", ["检索", "search strategy", "数据库"]),
            ("研究选择流程", ["流程图", "筛选", "flow"]),
            ("偏倚风险评估", ["偏倚", "risk of bias", "rob"]),
            ("效应量与置信区间", ["95%", "ci", "置信区间", "效应量"]),
            ("异质性", ["异质性", "i²", "i2", "heterogeneity"]),
            ("发表偏倚", ["发表偏倚", "publication bias", "漏斗图"]),
            ("证据确定性", ["grade", "证据质量", "确定性"]),
        ],
    ),
    "consort_2025": ReportingGuideline(
        id="consort_2025",
        name="CONSORT 2025",
        version="2025",
        source="https://www.consort-statement.org/",
        applies_to="随机对照试验",
        structure=_CONSORT_STRUCTURE,
        aliases=["consort", "rct", "随机对照", "随机", "临床试验", "randomized"],
        key_items=[
            ("随机序列生成", ["随机序列", "随机数字", "random sequence", "随机化"]),
            ("分配隐藏", ["分配隐藏", "allocation concealment", "密封信封", "中心随机"]),
            ("盲法", ["盲法", "blinding", "双盲", "单盲"]),
            ("样本量计算", ["样本量", "sample size", "把握度", "power"]),
            ("主要结局", ["主要结局", "primary outcome"]),
            ("受试者流程", ["流程图", "筛选", "脱落", "flow diagram"]),
            ("基线特征", ["基线", "baseline"]),
            ("不良事件", ["不良事件", "adverse event", "安全性"]),
        ],
    ),
    "strobe": ReportingGuideline(
        id="strobe",
        name="STROBE",
        version="v4 (2007)",
        source="https://www.strobe-statement.org/",
        applies_to="观察性研究（队列、病例对照、横断面）",
        structure=_STROBE_STRUCTURE,
        aliases=["strobe", "观察性", "队列", "病例对照", "横断面", "真实世界", "observational", "cohort"],
        key_items=[
            ("研究设计", ["研究设计", "队列", "病例对照", "横断面"]),
            ("研究对象", ["纳入", "排除", "受试者"]),
            ("变量定义", ["暴露", "结局", "混杂"]),
            ("偏倚控制", ["偏倚", "混杂", "bias"]),
            ("样本量", ["样本量", "sample size"]),
            ("统计方法", ["统计方法", "回归", "调整"]),
            ("效应量与置信区间", ["95%", "置信区间", "or", "hr", "rr"]),
        ],
    ),
    "stard_2015": ReportingGuideline(
        id="stard_2015",
        name="STARD 2015",
        version="2015",
        source="https://www.equator-network.org/reporting-guidelines/stard/",
        applies_to="诊断准确性研究",
        structure=_STARD_STRUCTURE,
        aliases=["stard", "诊断准确性", "诊断试验", "灵敏度", "特异度", "diagnostic"],
        key_items=[
            ("待评价试验", ["待评价试验", "index test", "判读", "阈值"]),
            ("参考标准", ["参考标准", "reference standard", "金标准"]),
            ("盲法", ["盲法", "blinding"]),
            ("灵敏度与特异度", ["灵敏度", "特异度", "sensitivity", "specificity"]),
            ("95%置信区间", ["95%", "置信区间", "ci"]),
            ("受试者流程", ["流程图", "筛选", "flow"]),
        ],
    ),
    "tripod": ReportingGuideline(
        id="tripod",
        name="TRIPOD",
        version="2015",
        source="https://www.tripod-statement.org/",
        applies_to="临床预测模型（诊断或预后）",
        structure=_TRIPOD_STRUCTURE,
        aliases=["tripod", "预测模型", "风险预测", "列线图", "nomogram", "prediction model"],
        key_items=[
            ("预测因子", ["预测因子", "predictor", "变量筛选"]),
            ("样本量与事件数", ["样本量", "事件数", "epv"]),
            ("缺失数据处理", ["缺失", "插补", "missing"]),
            ("模型构建", ["建模", "模型构建", "回归"]),
            ("区分度", ["auc", "c统计量", "c-statistic", "区分度"]),
            ("校准", ["校准", "calibration"]),
            ("临床效用", ["dca", "决策曲线", "临床效用"]),
        ],
    ),
    "narrative_review": ReportingGuideline(
        id="narrative_review",
        name="叙述性综述（自定义结构）",
        version="internal v1",
        source="内部模板（不声称符合 PRISMA）",
        applies_to="叙述性综述、专家述评",
        structure=_NARRATIVE_STRUCTURE,
        aliases=["叙述性综述", "叙述综述", "文献综述", "narrative", "literature review", "述评"],
        key_items=[
            ("综述范围", ["范围", "scope"]),
            ("主题组织", ["主题"]),
            ("局限性", ["局限", "limitation"]),
        ],
    ),
    "prisma_scr": ReportingGuideline(
        id="prisma_scr",
        name="PRISMA-ScR",
        version="2018",
        source="https://www.prisma-statement.org/scoping",
        applies_to="范围综述（Scoping Review）与证据映射",
        structure=_PRISMA_SCR_STRUCTURE,
        aliases=["prisma-scr", "prisma_scr", "范围综述", "scoping review", "scoping", "证据映射综述"],
        key_items=[
            ("研究目的与PCC框架", ["目的", "pcc", "范围", "objective", "concept", "context"]),
            ("纳入排除标准", ["纳入标准", "排除标准", "纳入与排除", "eligibility"]),
            ("信息来源与检索策略", ["检索", "pubmed", "database", "search strategy", "数据库"]),
            ("证据筛选与PRISMA流程", ["筛选", "prisma", "流程图", "flow"]),
            ("数据提取与证据绘制", ["提取", "数据", "charting", "特征", "矩阵"]),
            ("结果主题综合", ["结果", "评估", "监测", "治疗", "synthesis"]),
            ("局限性", ["局限", "limitation"]),
            ("利益冲突与资助声明", ["利益冲突", "资助", "声明", "funding", "competing", "declaration"]),
        ],
    ),
    "tripod_ai": ReportingGuideline(
        id="tripod_ai",
        name="TRIPOD+AI",
        version="2024",
        source="https://www.tripod-statement.org/",
        applies_to="临床人工智能与机器学习预测模型",
        structure=_TRIPOD_AI_STRUCTURE,
        aliases=["tripod+ai", "tripod-ai", "tripod_ai", "ai预测模型", "机器学习预测模型", "ai prediction model"],
        key_items=[
            ("研究人群与结局", ["纳入", "排除", "结局", "outcome"]),
            ("预测因子与预处理", ["预测因子", "特征", "predictor", "feature"]),
            ("样本量与事件数", ["样本量", "事件数", "epv", "阳性"]),
            ("模型架构与训练", ["模型", "训练", "超参数", "验证"]),
            ("区分度", ["auc", "auroc", "c统计量", "区分度"]),
            ("校准", ["校准", "brier", "calibration"]),
            ("临床效用", ["dca", "决策曲线", "净获益", "临床效用"]),
            ("公平性与外部验证", ["公平", "亚组", "外部验证", "时间验证", "fairness"]),
        ],
    ),
}

DEFAULT_REVIEW_GUIDELINE = "prisma_2020"
DEFAULT_TRIAL_GUIDELINE = "consort_2025"


def list_guidelines() -> List[dict]:
    """给前端/文档用的规则包清单"""
    return [g.to_dict() for g in GUIDELINES.values()]


def resolve(study_type: str, default: str = DEFAULT_REVIEW_GUIDELINE) -> Tuple[ReportingGuideline, str]:
    """把用户填写的研究类型解析到规则包。

    Returns:
        (guideline, note)。note 为空表示精确命中；非空时需要向用户说明路由依据。
    """
    raw = (study_type or "").strip()
    if not raw:
        return GUIDELINES[default], "未提供研究类型，已按默认规范生成"

    key = raw.lower()

    # 1) 直接命中 id
    if key in GUIDELINES:
        return GUIDELINES[key], ""

    # 2) 别名精确命中（先长后短，避免"综述"抢先于"叙述性综述"）
    candidates = sorted(
        ((alias, gid) for gid, g in GUIDELINES.items() for alias in g.aliases),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    for alias, gid in candidates:
        if alias.lower() == key:
            note = ""
            if gid == "prisma_2020" and raw == "综述":
                note = (
                    "研究类型仅填写“综述”，已按 PRISMA 2020（系统评价）结构生成；"
                    "若为叙述性综述，请选择“叙述性综述”以免套用不适用的检索与偏倚条目"
                )
            return GUIDELINES[gid], note

    # 3) 包含匹配
    for alias, gid in candidates:
        if alias.lower() in key:
            return GUIDELINES[gid], f"研究类型“{raw}”按关键词“{alias}”路由到 {GUIDELINES[gid].name}"

    return (
        GUIDELINES[default],
        f"无法识别研究类型“{raw}”，已回退到 {GUIDELINES[default].name}；请显式选择研究类型",
    )
