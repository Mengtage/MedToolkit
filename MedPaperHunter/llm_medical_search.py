"""
LLM驱动的医学检索式构建器
===========================

本模块是 MedPaperHunter 系统的核心AI分析引擎，负责将自然语言研究问题转化为结构化的医学文献检索式。

核心架构:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    用户输入自然语言问题                        │
    └───────────────────────────┬───────────────────────────────────┘
                                ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │  LLM (大语言模型): 拆解 PICO/PEO + 扩展同义词 + 推荐 MeSH 词    │
    └───────────────────────────┬───────────────────────────────────┘
                                ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │  MeSH API: 校验 MeSH 词是否真实存在（可选功能）                 │
    └───────────────────────────┬───────────────────────────────────┘
                                ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │  模板引擎: 根据各数据库语法生成检索式                          │
    └───────────────────────────┬───────────────────────────────────┘
                                ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │                    输出多数据库检索式                          │
    └─────────────────────────────────────────────────────────────────┘

主要组件:
    1. LLMClient: 轻量级OpenAI兼容API客户端
    2. MeSHValidator: MeSH主题词校验器（通过NCBI E-utilities API）
    3. LLMedicalSearchBuilder: 端到端检索式构建器

使用示例:
    >>> from llm_medical_search import LLMedicalSearchBuilder
    >>> builder = LLMedicalSearchBuilder(
    ...     llm_api_key="sk-xxx",
    ...     llm_base_url="https://api.deepseek.com/v1",
    ...     llm_model="deepseek-chat",
    ... )
    >>> result = await builder.build_from_question(
    ...     question="二甲双胍对比GLP-1受体激动剂治疗2型糖尿病的有效性和安全性",
    ...     databases=["pubmed", "embase", "cochrane", "wos"],
    ... )
    >>> print(result["strategies"]["pubmed"])

支持的数据库:
    - PubMed: 使用MeSH主题词和自由词检索
    - Embase: 使用Emtree主题词
    - Cochrane Library: Cochrane Review Manager格式
    - Web of Science: 使用TS字段检索
    - arXiv: 预印本服务器检索
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
# LLM 客户端（OpenAI兼容API）
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """LLM模型配置类。
    
    用于配置大语言模型的连接参数。
    
    Attributes:
        api_key: API密钥，用于身份验证
        base_url: API服务的基础URL
        model: 模型名称，如 deepseek-chat、gpt-4o-mini 等
        temperature: 温度参数，控制输出的随机性（0-1，越低越确定）
        max_tokens: 最大返回token数
        timeout: 请求超时时间（秒）
    """
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: float = 60.0


class LLMClient:
    """轻量级 OpenAI 兼容 API 客户端。
    
    使用 httpx 实现，无需依赖官方 OpenAI SDK，更加轻量灵活。
    
    支持的API格式:
        - OpenAI API 格式
        - DeepSeek API 格式
        - 其他兼容 OpenAI API 的服务
    
    Example:
        >>> config = LLMConfig(api_key="sk-xxx", base_url="https://api.deepseek.com/v1")
        >>> client = LLMClient(config)
        >>> response = await client.chat([{"role": "user", "content": "Hello"}])
    """

    def __init__(self, config: LLMConfig) -> None:
        """初始化LLM客户端。
        
        Args:
            config: LLM配置对象
        """
        self.config = config

    async def chat(self, messages: list[dict[str, str]]) -> str:
        """发送聊天请求，返回AI助手的回复文本。
        
        Args:
            messages: 消息列表，每个消息包含 role（system/user/assistant）和 content
        
        Returns:
            AI助手的回复文本
        
        Raises:
            httpx.HTTPStatusError: 如果API请求失败
        """
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
# MeSH API 客户端
# ---------------------------------------------------------------------------

class MeSHValidator:
    """MeSH主题词校验器。
    
    通过 NCBI E-utilities API 校验 MeSH 词是否真实存在于医学主题词表中。
    
    MeSH (Medical Subject Headings) 是美国国立医学图书馆(NLM)编制的医学主题词表，
    用于PubMed等数据库的规范化检索。
    
    工作原理:
        1. 使用 esearch API 在 MeSH 数据库中搜索术语
        2. 如果找到匹配，使用 esummary API 获取详细信息
        3. 返回术语的官方名称、UID和入口词
    
    API基础地址: https://eutils.ncbi.nlm.nih.gov/entrez/eutils
    
    特性:
        - 本地缓存机制，避免重复请求
        - 限流控制，遵守NCBI API使用规范
        - 支持批量校验
    
    Example:
        >>> validator = MeSHValidator()
        >>> result = await validator.validate("Diabetes Mellitus")
        >>> print(result["valid"])  # True
    """

    EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, timeout: float = 15.0, max_retries: int = 3) -> None:
        """初始化MeSH校验器。
        
        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        # 本地缓存: term -> validation result（避免重复请求）
        self._cache: dict[str, dict[str, Any]] = {}
        # 限流信号量：确保同一时间只发送1个请求，遵守NCBI API限制
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        """获取限流信号量。
        
        Returns:
            Semaphore实例，限制并发请求数为1
        """
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(1)  # 同一时间只允许1个请求
        return self._semaphore

    async def validate(self, term: str) -> dict[str, Any]:
        """校验单个 MeSH 词是否有效。
        
        Args:
            term: 需要校验的MeSH术语
            
        Returns:
            校验结果字典，包含以下字段:
                - term: 原始术语
                - valid: True=有效, False=无效, None=API请求失败
                - mesh_uid: MeSH唯一标识符
                - mesh_name: 官方MeSH名称
                - entry_terms: 入口词列表（同义词）
                - note: 备注信息（如模糊匹配提示）
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
        """并发校验多个 MeSH 词。
        
        使用 asyncio.gather 并发执行多个校验请求，提高效率。
        
        Args:
            terms: 需要校验的术语列表
            
        Returns:
            校验结果列表，顺序与输入列表一致
        """
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
# LLM驱动的检索式构建器
# ---------------------------------------------------------------------------

class LLMedicalSearchBuilder:
    """LLM驱动的医学文献检索式构建器。
    
    实现端到端的检索式生成流水线：
        自然语言问题 → LLM分析 → MeSH校验 → 检索式生成
    
    核心功能:
        1. 语言检测与翻译：自动检测中文并翻译为英文
        2. PICO/PEO分析：使用LLM分解研究问题
        3. MeSH校验：验证推荐的MeSH词是否有效
        4. 检索式生成：生成多数据库检索式
    
    Example:
        >>> builder = LLMedicalSearchBuilder(
        ...     llm_api_key="sk-xxx",
        ...     llm_base_url="https://api.deepseek.com/v1",
        ...     llm_model="deepseek-chat",
        ... )
        >>> result = await builder.build_from_question(
        ...     question="二甲双胍治疗2型糖尿病的疗效",
        ...     databases=["pubmed", "wos"],
        ... )
    """

    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str = "https://api.openai.com/v1",
        llm_model: str = "gpt-4o-mini",
        validate_mesh: bool = True,
    ) -> None:
        """初始化检索式构建器。
        
        Args:
            llm_api_key: LLM API密钥
            llm_base_url: LLM API基础URL
            llm_model: LLM模型名称
            validate_mesh: 是否启用MeSH词校验（默认启用）
        """
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
        """端到端生成检索式。
        
        从自然语言研究问题出发，经过AI分析、MeSH校验，最终生成多数据库检索式。
        
        处理流程:
            1. 语言检测：判断输入是中文还是英文
            2. 翻译（如需要）：中文问题自动翻译为英文
            3. LLM分析：使用AI分解问题为PICO/PEO结构
            4. MeSH校验（可选）：验证推荐的MeSH词是否有效
            5. 检索式生成：根据各数据库语法生成检索式
            6. 输出格式化：生成Markdown报告
        
        Args:
            question: 研究问题（支持中文或英文）
            databases: 目标数据库列表，默认所有支持的数据库
            validate_mesh: 是否校验MeSH词（默认使用初始化时的设置）
        
        Returns:
            包含以下字段的字典:
                - question: 原始问题
                - english_question: 翻译后的英文问题（如适用）
                - language: 输入语言
                - analysis: LLM分析结果（PICO/PEO结构）
                - mesh_validation: MeSH校验结果
                - strategies: 各数据库检索式
                - validation_tips: 验证提示
                - markdown: 格式化的Markdown报告
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

    def _fix_mesh_json_format(self, json_str: str) -> str:
        """修复 LLM 返回的 JSON 中 MeSH 术语格式错误。
        
        LLM 可能返回格式错误的 MeSH 术语，如:
        "mesh": ["Anesthesia"[MeSH], ...]
        
        需要修复为正确的 JSON 格式:
        "mesh": ["Anesthesia[MeSH]", ...]
        
        Args:
            json_str: 原始 JSON 字符串
            
        Returns:
            修复后的 JSON 字符串
        """
        # 匹配 "term"[suffix] 格式并修复为 "term[suffix]"
        # 正则表达式解释:
        # "([^"]+)" - 匹配双引号内的内容
        # \[([^\]]+)\] - 匹配方括号内的内容（如 [MeSH]）
        pattern = r'"([^"]+)"\[([^\]]+)\]'
        replacement = r'"\1[\2]"'
        return re.sub(pattern, replacement, json_str)

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

        # 修复 LLM 返回的 JSON 中 MeSH 术语格式错误
        # 将 "term"[MeSH] 格式修复为 "term[MeSH]"
        json_str = self._fix_mesh_json_format(json_str)

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
