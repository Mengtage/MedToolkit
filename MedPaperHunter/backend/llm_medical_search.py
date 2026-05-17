"""
LLM-Powered Medical Search Strategy Builder
============================================

在纯模板引擎基础上，增加 LLM 自动分析层和 MeSH API 校验层，
实现端到端：自然语言问题 → 结构化检索式。

架构:
    用户输入自然语言问题
        ↓
    LLM: 拆解 PICO/PEO + 扩展同义词 + 推荐 MeSH
        ↓
    MeSH API: 校验 MeSH 词是否真实存在（可选）
        ↓
    模板引擎: 生成各数据库检索式
        ↓
    输出结果

用法示例:
    >>> from llm_medical_search import LLMedicalSearchBuilder
    >>> builder = LLMedicalSearchBuilder(
    ...     llm_api_key="sk-xxx",
    ...     llm_base_url="https://api.openai.com/v1",
    ...     llm_model="gpt-4o-mini",
    ... )
    >>> result = await builder.build_from_question(
    ...     question="二甲双胍对比GLP-1受体激动剂治疗2型糖尿病的有效性和安全性",
    ...     databases=["pubmed", "embase", "cochrane", "wos"],
    ... )
    >>> print(result["strategies"]["pubmed"])
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote

import httpx
from medical_search_strategy_builder import (
    BuildResult,
    Concept,
    Database,
    Framework,
    MedicalSearchStrategyBuilder,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM Client (OpenAI-compatible API)
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """LLM 配置。"""
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: float = 60.0


class LLMClient:
    """轻量级 OpenAI 兼容 API 客户端（纯 httpx，无 openai SDK 依赖）。"""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    async def chat(self, messages: list[dict[str, str]]) -> str:
        """发送聊天请求，返回助手回复文本。"""
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# MeSH API Client
# ---------------------------------------------------------------------------

class MeSHValidator:
    """
    通过 NCBI E-utilities 校验 MeSH 词是否真实存在。

    使用 NCBI E-utilities API (esearch + esummary) 查询 MeSH 数据库，
    返回 MeSH 词的 UID、官方名称和入口词（Entry Terms）。

    API: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
    """

    EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, timeout: float = 15.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        # 本地缓存: term -> validation result
        self._cache: dict[str, dict[str, Any]] = {}
        # 限流：串行请求，请求间间隔
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(1)  # 同一时间只允许 1 个请求
        return self._semaphore

    async def validate(self, term: str) -> dict[str, Any]:
        """
        校验单个 MeSH 词。返回:
        {
            "term": str,
            "valid": bool | None,       # True=有效, False=无效, None=API失败
            "mesh_uid": str | None,
            "mesh_name": str | None,
            "entry_terms": list[str],
            "note": str | None,
        }
        """
        term = term.strip()
        if term in self._cache:
            return self._cache[term]

        async with self._get_semaphore():
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    # Step 1: 在 MeSH 数据库中搜索（限制返回数量以避免限流）
                    descriptor_query = f'"{term}"[DescriptorName]'
                    search_url = (
                        f"{self.EUTILS_BASE}/esearch.fcgi"
                        f"?db=mesh&term={quote(descriptor_query)}"
                        f"&retmax=5&retmode=json"
                    )
                    resp = await client.get(search_url)
                    if resp.status_code == 429:
                        # 限流：等待后重试
                        await asyncio.sleep(1)
                        resp = await client.get(search_url)
                    if resp.status_code != 200:
                        result = {"term": term, "valid": None, "mesh_uid": None, "mesh_name": None, "entry_terms": [], "note": "API error"}
                        self._cache[term] = result
                        return result

                    data = resp.json()
                    id_list = data.get("esearchresult", {}).get("idlist", [])
                    count = int(data.get("esearchresult", {}).get("count", "0"))

                    if not id_list or count == 0:
                        result = {"term": term, "valid": False, "mesh_uid": None, "mesh_name": None, "entry_terms": []}
                        self._cache[term] = result
                        return result

                    # Step 2: 获取所有匹配的 MeSH 词详情，找到精确匹配
                    summary_url = (
                        f"{self.EUTILS_BASE}/esummary.fcgi"
                        f"?db=mesh&id={','.join(id_list)}&retmode=json"
                    )
                    resp2 = await client.get(summary_url)
                    if resp2.status_code == 429:
                        await asyncio.sleep(1)
                        resp2 = await client.get(summary_url)
                    if resp2.status_code != 200:
                        logger.warning(f"MeSH esummary returned {resp2.status_code} for IDs {id_list}")
                        result = {"term": term, "valid": True, "mesh_uid": id_list[0], "mesh_name": None, "entry_terms": [], "note": "found but details unavailable"}
                        self._cache[term] = result
                        return result

                    detail = resp2.json()
                    exact_match = None
                    best_match = None

                    for uid in id_list:
                        info = detail.get("result", {}).get(str(uid), {})
                        mesh_terms = info.get("ds_meshterms", [])
                        if not mesh_terms:
                            continue
                        mesh_name = mesh_terms[0]

                        if not best_match:
                            best_match = (uid, mesh_name, mesh_terms)

                        # 精确匹配检查
                        if mesh_name.lower() == term.lower():
                            exact_match = (uid, mesh_name, mesh_terms)
                            break

                        # 也检查 entry terms 中是否有精确匹配
                        for t in mesh_terms[1:]:
                            if t.lower() == term.lower():
                                exact_match = (uid, mesh_name, mesh_terms)
                                break
                        if exact_match:
                            break

                    match = exact_match or best_match
                    if not match:
                        result = {"term": term, "valid": False, "mesh_uid": None, "mesh_name": None, "entry_terms": []}
                        self._cache[term] = result
                        return result

                    uid, mesh_name, mesh_terms = match
                    entry_terms = [t for t in mesh_terms[1:] if t.lower() != term.lower()] if len(mesh_terms) > 1 else []
                    is_exact = exact_match is not None
                    note = None if is_exact else "fuzzy match, suggest verification"

                    result = {
                        "term": term,
                        "valid": True,
                        "mesh_uid": uid,
                        "mesh_name": mesh_name,
                        "entry_terms": entry_terms,
                        "note": note,
                    }
                    self._cache[term] = result
                    return result

            except Exception as e:
                logger.warning(f"MeSH validation failed for '{term}': {e}")
                result = {"term": term, "valid": None, "mesh_uid": None, "mesh_name": None, "entry_terms": [], "note": f"validation error: {e}"}
                self._cache[term] = result
                return result

    async def validate_batch(self, terms: list[str]) -> list[dict[str, Any]]:
        """并发校验多个 MeSH 词。"""
        tasks = [self.validate(t) for t in terms]
        return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# LLM Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert medical librarian specializing in systematic review search strategy development. \
Your task is to analyze a research question and decompose it into a structured format for building \
database search strategies across multiple platforms.

IMPORTANT RULES:
1. Search terms MUST be in English, even if the question is in another language.
2. Provide comprehensive synonym expansion (≥3-5 terms per concept).
3. MeSH terms should be the official NLM MeSH descriptors.
4. Include abbreviations, spelling variants (US/UK), and related terms.
5. For drug searches, include both generic and brand names.
6. Output ONLY valid JSON, no extra text.

PLATFORM-SPECIFIC SEARCH SYNTAX GUIDES:

=== PubMed (NCBI E-utilities) ===
- MeSH terms: "Term"[MeSH] or "Term"[Majr] for major topics
- Title/Abstract: "term"[Title/Abstract]
- Free text: "term" (automatically searches Title, Abstract, MeSH)
- Boolean: AND, OR, NOT (capitalized)
- Truncation: term* (finds term, terms, terminal, etc.)
- Phrase: "exact phrase" (with quotes)
- Fields: [tiab], [ti], [ab], [au], [journal], [dp] (date published)
- MeSH subheadings: "Term"[MeSH] AND "Therapy"[MeSH]
- Special: Adj# for adjacency (Adj2 = within 2 words)

Example: ("diabetes mellitus"[MeSH] OR "diabetes"[Title/Abstract]) AND ("metformin"[MeSH] OR "metformin"[Title/Abstract])

=== Web of Science ===
Field Tags (use in parentheses):
- TS: Topic (searches Title, Abstract, Keywords Plus)
- TI: Title
- AU: Author
- SO: Publication Name (Journal)
- PY: Year Published
- AB: Abstract
- AK: Author Keywords
- UT: Web of Science Core Collection Accession Number (PMID)

Operators:
- AND, OR, NOT (must be capitalized)
- NEAR/n or SAME/n: words within n words
- Phrase: "exact phrase"
- Truncation: term* (finds variations)

Example: TS=(diabetes AND metformin) AND PY=(2020-2024)

=== Scopus ===
Field Codes:
- TITLE-ABS-KEY: Title, Abstract, Keywords (most comprehensive)
- TITLE: Title only
- ABS: Abstract only
- KEY: Author Keywords
- AUTH: Author names
- SRCTITLE: Source title (Journal)
- PUBYEAR: Publication year
- DOI: Digital Object Identifier

Operators:
- AND, OR, AND NOT (precedence: OR first, then AND, then AND NOT)
- W/n: Within n words (order doesn't matter) - e.g., "journal W/2 publishing"
- PRE/n: Within n words (specific order) - e.g., "behavioral PRE/3 disturbances"
- Truncation: * (e.g., comput* finds computer, computing, computation)
- Wildcard: ? for single character (e.g., Wom?n finds Woman, Women)
- Exact phrase: {exact phrase} with braces
- Approximate phrase: "approximate phrase" with quotes

Example: TITLE-ABS-KEY(diabetes AND metformin) AND PUBYEAR > 2019

=== arXiv (Preprint Server) ===
Search Fields:
- all: All fields
- ti: Title only
- au: Author
- abs: Abstract
- co: Comments (paper metadata)
- jr: Journal Reference
- cat: Category (e.g., cs.AI, q-bio.QM)
- abs+ti: Title and Abstract combined

Operators:
- AND, OR, ANDNOT (not AND NOT)
- Truncation: * (e.g., "neural net*" finds "neural network", "neural nets")
- Phrase: "exact phrase"
- Wildcard: ? for single character
- Field-specific: ti: + au: syntax

Example: abs:"neural network" AND cat:cs.LG AND submittedDate:[20200101 TO 20241231]

Common arXiv Categories:
- cs.AI: Artificial Intelligence
- cs.LG: Machine Learning
- q-bio.QM: Quantitative Methods in Biology
- stat.ML: Machine Learning (Statistics)
- math.CO: Mathematics - Combinatorics

IMPORTANT NOTES:
- Each database has different MeSH/thesaurus mapping - adapt terms accordingly
- Use adjacency operators carefully - they behave differently across platforms
- Date filters vary: PubMed uses [dp], WoS uses PY=, Scopus uses PUBYEAR, arXiv uses submittedDate
- Truncation symbols: * works across all platforms
- For systematic reviews, prefer comprehensive search (Title/Abstract/MeSH) over title-only searches
"""

USER_PROMPT_TEMPLATE = """\
Analyze this research question and output a JSON object with the following structure:

{{
  "framework": "PICO" or "PEO",
  "research_type": "brief description of research type",
  "concepts": {{
    "P": {{
      "name": "English name of the concept",
      "mesh": ["Official MeSH descriptor 1", "Official MeSH descriptor 2"],
      "free_text": ["synonym1", "synonym2", "abbreviation1", "spelling variant1"],
      "truncated": ["root*"]
    }},
    "I": {{ ... }},
    "C": {{ ... }},
    "O": {{ ... }}
  }}
}}

For PEO framework, use "E" instead of "I".
C and O are optional — omit if not clearly specified in the question.

Research question: {question}
"""

# 中文问题需要翻译提示
TRANSLATION_PROMPT = """\
Translate the following medical research question from Chinese to English. \
Output ONLY the English translation, nothing else.

Question: {question}
"""


# ---------------------------------------------------------------------------
# LLM-Powered Builder
# ---------------------------------------------------------------------------

class LLMedicalSearchBuilder:
    """
    LLM 驱动的医学文献检索式构建器。

    实现端到端流水线：
    自然语言问题 → LLM 分析 → MeSH 校验 → 检索式生成
    """

    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str = "https://api.openai.com/v1",
        llm_model: str = "gpt-4o-mini",
        validate_mesh: bool = True,
    ) -> None:
        self.builder = MedicalSearchStrategyBuilder()
        self.llm_config = LLMConfig(
            api_key=llm_api_key,
            base_url=llm_base_url,
            model=llm_model,
        )
        self.llm = LLMClient(self.llm_config)
        self.mesh_validator = MeSHValidator() if validate_mesh else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_from_question(
        self,
        question: str,
        databases: Optional[list[str]] = None,
        validate_mesh: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        端到端：从自然语言问题生成多数据库检索式。

        Args:
            question: 研究问题（支持中文或英文）
            databases: 目标数据库列表，默认全部
            validate_mesh: 是否校验 MeSH 词（默认使用初始化设置）

        Returns:
            包含 analysis, mesh_validation, strategies, markdown 的字典
        """
        if databases is None:
            databases = [db.value for db in Database]
        do_validate = validate_mesh if validate_mesh is not None else (self.mesh_validator is not None)

        # Step 1: 语言检测 & 翻译
        language = self.builder.detect_language(question)
        english_question = question
        if language == "zh":
            english_question = await self._translate_to_english(question)

        # Step 2: LLM 分析（PICO 拆解 + 同义词扩展 + MeSH 推荐）
        analysis = await self._analyze_question(english_question)

        # Step 3: MeSH 校验（可选）
        mesh_validation = {}
        if do_validate and self.mesh_validator:
            mesh_validation = await self._validate_all_mesh(analysis["concepts"])

        # Step 4: 生成检索式
        result = self.builder.build(
            question=question,
            concepts=analysis["concepts"],
            framework=analysis["framework"],
            databases=databases,
            research_type=analysis.get("research_type"),
        )

        # Step 5: 组装输出
        markdown = self.builder.to_markdown(result)
        return {
            "question": question,
            "english_question": english_question if language == "zh" else None,
            "language": language,
            "analysis": analysis,
            "mesh_validation": mesh_validation,
            "strategies": result.strategies,
            "validation_tips": result.validation_tips,
            "markdown": markdown,
        }

    async def analyze_only(self, question: str) -> dict[str, Any]:
        """
        仅执行 LLM 分析（不生成检索式），用于预览和编辑。

        Returns:
            LLM 分析结果（PICO 拆解 + 同义词 + MeSH 推荐）
        """
        language = self.builder.detect_language(question)
        english_question = question
        if language == "zh":
            english_question = await self._translate_to_english(question)
        return await self._analyze_question(english_question)

    async def validate_mesh_terms(self, terms: list[str]) -> list[dict[str, Any]]:
        """独立调用 MeSH 校验。"""
        if not self.mesh_validator:
            raise RuntimeError("MeSH validation is disabled. Initialize with validate_mesh=True.")
        return await self.mesh_validator.validate_batch(terms)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _translate_to_english(self, question: str) -> str:
        """将中文问题翻译为英文。"""
        messages = [
            {"role": "system", "content": "You are a medical translator. Output ONLY the English translation."},
            {"role": "user", "content": TRANSLATION_PROMPT.format(question=question)},
        ]
        return (await self.llm.chat(messages)).strip()

    async def _analyze_question(self, question: str) -> dict[str, Any]:
        """调用 LLM 分析研究问题，返回结构化 JSON。"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(question=question)},
        ]
        raw = await self.llm.chat(messages)

        # 解析 JSON（兼容 markdown 代码块包裹）
        json_str = raw.strip()
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', json_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()

        try:
            analysis = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON parse failed: {e}\nRaw output:\n{raw}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

        # 规范化 concepts 字段
        concepts = analysis.get("concepts", {})
        for dim, concept in concepts.items():
            concept.setdefault("mesh", [])
            concept.setdefault("free_text", [])
            concept.setdefault("truncated", [])

            # 清理 MeSH 词中的 "(suggest verification)" 标记
            mesh_terms = concept.get("mesh", [])
            cleaned_mesh = []
            for term in mesh_terms:
                clean = term.replace("(suggest verification)", "").strip()
                if clean:
                    cleaned_mesh.append(clean)
            concept["mesh"] = cleaned_mesh

        return analysis

    async def _validate_all_mesh(
        self, concepts: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """校验所有概念中的 MeSH 词。"""
        if not self.mesh_validator:
            return {}

        all_mesh: list[str] = []
        mesh_map: dict[str, str] = {}  # mesh_term -> dimension
        for dim, concept in concepts.items():
            for m in concept.get("mesh", []):
                clean = m.replace("(suggest verification)", "").strip()
                if clean and clean not in mesh_map:
                    all_mesh.append(clean)
                    mesh_map[clean] = dim

        results = await self.mesh_validator.validate_batch(all_mesh)

        # 按维度组织
        validation: dict[str, Any] = {}
        for r in results:
            dim = mesh_map.get(r["term"], "unknown")
            if dim not in validation:
                validation[dim] = []
            validation[dim].append(r)

        return validation
