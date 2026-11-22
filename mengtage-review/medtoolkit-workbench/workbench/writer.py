"""Single-owner local manuscript versions with 6-gate medical SCI writing validation, dual-scope abbreviation checking, Vancouver citation rendering, and dual-document (Manuscript + Technical Supplement) export."""
import json
import re
import uuid
from .core import canonical, now
from .fulltext import snapshot, validate_snapshot, validate_evidence, json_hash, sha


SECTION_KINDS = [
    ('abstract', ('摘要', 'abstract', 'summary')),
    ('keywords', ('关键词', '关键字', 'keywords', 'key words')),
    ('introduction', ('引言', '前言', '背景', 'introduction', 'background')),
    ('methods', ('方法', '资料与方法', '研究方法', '检索策略', '纳入与排除', 'methods', 'materials and methods', 'methodology', 'search strategy', 'eligibility')),
    ('results', ('结果', '研究结果', 'results', 'findings')),
    ('discussion', ('讨论', 'discussion')),
    ('limitations', ('局限', '局限性', 'limitations', 'strengths and limitations')),
    ('conclusion', ('结论', '结语', 'conclusion', 'conclusions')),
    ('declarations', ('声明', '致谢', '利益冲突', '伦理', '资助', '数据可用性', '作者贡献', '缩略语', 'declarations', 'acknowledgements', 'competing interests', 'conflict of interest', 'funding', 'data availability', 'ethics', 'author contributions', 'abbreviations')),
]

NON_CITING_KINDS = {'abstract', 'keywords', 'conclusion', 'declarations'}
OPTIONAL_CITING_KINDS = {'methods', 'limitations'}

INTERNAL_JARGON_RE = re.compile(
    r'(?:/api/\w+|/sources\b|/screening\b|/studies\b|/writer\b|\bselected_lineage_complete\b|\btableone\b|\bcategorical_auto\b|\bprediction_evaluation_extended\b|\bmengtage-owner\b|\baria-gemini-reviewer\b|\bstudy_pmid_\w+)'
)

ENGINEERING_SELF_ATTESTATION_RE = re.compile(
    r'(?:SHA-256|SHA256|哈希冻结|快照冻结|哈希快照|确定性去重|工作台统计模块|工作台内置|按医学\s*SCI\s*规范|阶段门|状态机)',
    re.I,
)

AI_TEMPLATE_AND_OVERCLAIM_RE = re.compile(
    r'(?:全面赋能|生态底座|阶段门|显著赋能|完全治愈|无任何副作用|首次证明)'
)

STUDY_LAUNDRY_BULLET_RE = re.compile(
    r'^\s*[-*]\s+\*\*[^*\n]{1,60}\*\*\s*(?:[（(][^)\n]{1,120}[)）])?\s*[：:]',
    re.M,
)

UNTRANSLATED_ENGLISH_RUN_RE = re.compile(
    r'\b[A-Za-z]{2,}[A-Za-z0-9/-]*\b(?:\s+\b[A-Za-z]{2,}[A-Za-z0-9,.;:/-]*\b){7,}'
)


def infer_section_kind(title):
    t = (title or '').strip().lower()
    for kind, keywords in SECTION_KINDS:
        if any(k in t for k in keywords):
            return kind
    return 'other'


def text(value, limit=4000):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise ValueError('文本为空或超过长度限制')
    return value.strip()


def _author_name(a):
    if isinstance(a, str):
        return a.strip().rstrip('.')
    if isinstance(a, dict):
        if a.get('collective_name') or a.get('CollectiveName'):
            return str(a.get('collective_name') or a.get('CollectiveName')).strip()
        last = a.get('last_name') or a.get('LastName') or a.get('last') or ''
        init = a.get('initials') or a.get('Initials') or a.get('first') or ''
        return ' '.join(p for p in (last, init) if p).strip() or str(a.get('name', '')).strip()
    return str(a).strip()


def format_vancouver_reference(item):
    """Format an evidence item into ICMJE / NLM Vancouver bibliographic style."""
    bib = item.get('bibliographic') or {}
    title = (bib.get('title') or '').strip()
    if not title:
        src = (item.get('source') or '').strip()
        return src if src.endswith('.') else src + '.'
    raw_authors = bib.get('authors') or []
    if isinstance(raw_authors, str):
        names = [x.strip() for x in raw_authors.split(',') if x.strip()]
    elif isinstance(raw_authors, list):
        names = [x for x in (_author_name(a) for a in raw_authors) if x]
    else:
        names = []
    if len(names) > 6:
        author_part = ', '.join(names[:6]) + ', et al.'
    elif names:
        author_part = ', '.join(names) + '.'
    else:
        author_part = ''
    title_part = title if title[-1] in '.?!' else title + '.'
    journal = (bib.get('journal') or '').strip().rstrip('.')
    journal_part = (journal + '.') if journal else ''
    pub_date = str(bib.get('pub_date') or '').strip()
    m_year = re.search(r'(19|20)\d{2}', pub_date)
    year = m_year.group(0) if m_year else pub_date
    vol = str(bib.get('volume') or '').strip()
    issue = str(bib.get('issue') or '').strip()
    pages = str(bib.get('pages') or '').strip()
    loc = year
    if vol:
        loc += f';{vol}' + (f'({issue})' if issue else '') + (f':{pages}' if pages else '')
    elif pages:
        loc += f':{pages}'
    loc_part = (loc + '.') if loc else ''
    doi = (bib.get('doi') or '').strip().rstrip('.')
    doi_part = f'doi:{doi}.' if doi else ''
    pmid = str(bib.get('pmid') or '').strip()
    pmid_part = f'PMID: {pmid}.' if pmid else ''
    return ' '.join(p for p in (author_part, title_part, journal_part, loc_part, doi_part, pmid_part) if p)


def _compress_ranges(nums):
    if not nums:
        return ''
    nums = sorted(set(nums))
    ranges = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f'{start}' if start == prev else f'{start},{prev}' if prev == start + 1 else f'{start}–{prev}')
            start = prev = n
    ranges.append(f'{start}' if start == prev else f'{start},{prev}' if prev == start + 1 else f'{start}–{prev}')
    return '[' + ','.join(ranges) + ']'


def order_citations(sections, evidence_items):
    """Map bibliographic evidence IDs to sequential Vancouver numbers by first appearance in text."""
    by_id = {e['id']: e for e in evidence_items}
    bib_numbers = {}
    bib_refs = []
    stat_ids = set()
    used_ids = []
    for s in sections:
        for eid in re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]', s['body']):
            if eid not in by_id:
                continue
            if eid not in used_ids:
                used_ids.append(eid)
            item = by_id[eid]
            if item.get('origin') == 'native_statistics' or item.get('native_statistics'):
                stat_ids.add(eid)
            elif eid not in bib_numbers:
                bib_numbers[eid] = len(bib_numbers) + 1
                bib_refs.append(item)
    return bib_numbers, bib_refs, stat_ids, used_ids


CLUSTER_RE = re.compile(r'\[E:[A-Za-z0-9_-]{1,40}\](?:[\s,，;；、]*\[E:[A-Za-z0-9_-]{1,40}\])*')


def render_prisma_flow_markdown(flow_json_str):
    """Render a :::prisma-flow JSON block into a publication-grade PRISMA 2020 Figure 1 two-column flow diagram in Markdown."""
    try:
        d = json.loads(flow_json_str)
    except Exception:
        return flow_json_str
    rec_id = d.get('records_identified', 0)
    db_summary = d.get('source_summary', '多数据库联合检索')
    dup_rem = d.get('duplicates_removed', 0)
    rec_scr = d.get('records_screened', 0)
    rec_exc = d.get('records_excluded', 0)
    rep_sought = d.get('reports_sought', 0)
    rep_not_ret = d.get('reports_not_retrieved', 0)
    rep_ass = d.get('reports_assessed', 0)
    rep_exc = d.get('reports_excluded', 0)
    exc_detail = d.get('exclusion_breakdown', '不符合纳入标准')
    rep_inc = d.get('reports_included', 0)
    stu_inc = d.get('studies_included', 0)
    return (
        "**图 1  PRISMA 2020 文献检索、筛选与纳入标准流程图（Figure 1. PRISMA 2020 Flow Diagram）**\n\n"
        "```text\n"
        "┌────────────────────────────────────────────────────────┐\n"
        f"│ [阶段 1：识别 Identification]                          │      ┌──────────────────────────────────────────────────┐\n"
        f"│ 数据库与注册库检索识别原始记录 (n = {rec_id:<4})              │─────►│ 筛选前剔除重复记录 (n = {dup_rem:<4})                    │\n"
        f"│ ({db_summary[:48]:<48})   │      └──────────────────────────────────────────────────┘\n"
        "└───────────────────────────┬────────────────────────────┘\n"
        "                            ▼\n"
        "┌────────────────────────────────────────────────────────┐\n"
        f"│ [阶段 2：初筛 Screening]                               │      ┌──────────────────────────────────────────────────┐\n"
        f"│ 题名与摘要独立双盲初筛记录 (n = {rec_scr:<4})                  │─────►│ 初筛排除不符合 PICOS 记录 (n = {rec_exc:<4})             │\n"
        "└───────────────────────────┬────────────────────────────┘      └──────────────────────────────────────────────────┘\n"
        "                            ▼\n"
        "┌────────────────────────────────────────────────────────┐\n"
        f"│ [阶段 3：全文获取 Retrieval]                           │      ┌──────────────────────────────────────────────────┐\n"
        f"│ 拟获取全文进行复筛报告 (n = {rep_sought:<4})                      │─────►│ 未能获取全文报告 (n = {rep_not_ret:<4})                      │\n"
        "└───────────────────────────┬────────────────────────────┘      └──────────────────────────────────────────────────┘\n"
        "                            ▼\n"
        "┌────────────────────────────────────────────────────────┐\n"
        f"│ [阶段 4：全文评估 Eligibility]                         │      ┌──────────────────────────────────────────────────┐\n"
        f"│ 全文资格评估报告 (n = {rep_ass:<4})                            │─────►│ 全文评估排除报告 (n = {rep_exc:<4})                      │\n"
        f"│                                                        │      │ ({exc_detail[:46]:<46}) │\n"
        "└───────────────────────────┬────────────────────────────┘      └──────────────────────────────────────────────────┘\n"
        "                            ▼\n"
        "┌────────────────────────────────────────────────────────┐\n"
        f"│ [阶段 5：最终纳入 Included]                            │\n"
        f"│ 最终纳入定量与定性综合全文报告 (n = {rep_inc:<4})              │\n"
        f"│ 归属独立原始临床研究 (n = {stu_inc:<4})                        │\n"
        "└────────────────────────────────────────────────────────┘\n"
        "```"
    )


PRISMA_BLOCK_RE = re.compile(r':::prisma-flow\s*\n(.*?)\n:::', re.S)


def render_academic_text(body, bib_numbers, stat_ids, convert_prisma_block=True):
    """Replace [E:id] clusters with Vancouver numeric citations [1], [2–4] and strip statistical job tags from prose."""
    def _replace(match):
        cluster = match.group(0)
        eids = re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]', cluster)
        nums = [bib_numbers[eid] for eid in eids if eid in bib_numbers and eid not in stat_ids]
        if not nums:
            return ''
        return _compress_ranges(nums)
    out = CLUSTER_RE.sub(_replace, body)
    out = re.sub(r'[ \t]+([，。；：！？,.;:!?])', r'\1', out)
    out = re.sub(r'[ \t]{2,}', ' ', out)
    if convert_prisma_block:
        out = PRISMA_BLOCK_RE.sub(lambda m: render_prisma_flow_markdown(m.group(1)), out)
    return out


SELF_DISCOURSE_RE = re.compile(
    r'(?:本研究|本范围综述|本综述|本文|表\s*[1-9]|图\s*[1-9]|Table\s*[1-9]|Figure\s*[1-9]|研究问题|未来研究|检索共识别|初筛阶段|全文复筛|探索了|致力于|涵盖了|方向：|如下：)'
)


def _is_non_prose_block(p_strip):
    if p_strip.startswith(('#', '### ', '#### ', '|', '表', '图', '**表', '**图', '*注', '注：', 'Note:', '*Note:', '- ', '* ', '1. ', '2. ', '3. ', '4. ', ':::', '```')):
        return True
    if SELF_DISCOURSE_RE.search(p_strip):
        return True
    lines = [ln.strip() for ln in p_strip.splitlines() if ln.strip()]
    if lines and all(ln.startswith('|') and ln.endswith('|') for ln in lines):
        return True
    return False


def _strip_allowed_english_definitions(text):
    """Remove parenthetical English full-name definitions like （Large Language Model, LLM） and figure blocks before checking for untranslated English sentences."""
    s = PRISMA_BLOCK_RE.sub('', text)
    s = re.sub(r'```.*?```', '', s, flags=re.S)
    s = re.sub(r'\[E:[A-Za-z0-9_-]{1,40}\]', '', s)
    # Remove parenthetical English definitions: （English Words, ABBR） or (English Words, ABBR)
    s = re.sub(r'[（(][A-Za-z0-9\s,/+&-]{3,160}[）)]', ' ', s)
    s = re.sub(r'\[[A-Za-z0-9\s,/+&-]{3,160}\]', ' ', s)
    return s


def citation_check(sections, evidence):
    """Execute 6-gate medical SCI academic quality validation + evidence citation grounding checks."""
    known = {e['id'] for e in evidence}
    stat_known = {e['id'] for e in evidence if e.get('origin') == 'native_statistics' or e.get('native_statistics')}
    blockers = []
    warnings = []
    all_ids = [eid for s in sections for eid in re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]', s['body'])]
    multi_section = len(sections) > 1

    # Gate 4: Dual-scope first-use abbreviation full-name check (Abstract independent from Main Body)
    from .abbreviation import find_undefined_first_abbreviations
    for sec_title, undef_abbrs in find_undefined_first_abbreviations(sections):
        blockers.append(f"{sec_title}：首次出现的缩略语未提供全称定义（{', '.join(undef_abbrs)}）")

    for section in sections:
        body = section['body']
        title = section['title']
        kind = infer_section_kind(title)
        ids = re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]', body)
        unknown = sorted(set(ids) - known)
        if unknown:
            blockers.append(title + '：未知证据 ' + ', '.join(unknown))
        if not ids:
            if not multi_section or (kind not in NON_CITING_KINDS and kind not in OPTIONAL_CITING_KINDS):
                if not all_ids or kind not in (NON_CITING_KINDS | OPTIONAL_CITING_KINDS):
                    blockers.append(title + '：尚无证据引用')
        if kind in ('abstract', 'keywords') and ids:
            warnings.append(title + '：按医学SCI规范，摘要与关键词不应包含文献引用')
        if '[E:' in re.sub(r'\[E:[A-Za-z0-9_-]{1,40}\]', '', body):
            blockers.append(title + '：引用格式错误')
        if '[待补证据]' in body or '[待引用' in body or '[待补数据提取]' in body:
            blockers.append(title + '：存在待补证据')
        if re.search(r'\b[Pp]\s*=\s*0\.000+\b', body):
            warnings.append(title + '：统计P值不应写作P=0.000，按医学SCI规范应写为P<0.001')
        if INTERNAL_JARGON_RE.search(body):
            warnings.append(title + '：正文疑似包含工作台内部路由或变量标识符，请改为规范学术表述')
        if AI_TEMPLATE_AND_OVERCLAIM_RE.search(body):
            warnings.append(title + '：正文包含AI模板腔或过度因果/绝对化表述，请按证据强度降级表述')

        # Gate 1: Broad uninformative citation dumping (> 6 bibliographic references in a single cluster or numeric range [1–37])
        for cluster_match in CLUSTER_RE.finditer(body):
            cluster_eids = [eid for eid in re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]', cluster_match.group(0)) if eid not in stat_known]
            if len(set(cluster_eids)) > 6:
                blockers.append(f"{title}：存在单处引用簇包含 {len(set(cluster_eids))} 篇文献的宽泛无效堆砌（单处最多允许6篇直接支撑文献）")
                break
        for rng_match in re.finditer(r'\[(\d{1,3})\s*[–\-]\s*(\d{1,3})\]', body):
            start_n, end_n = int(rng_match.group(1)), int(rng_match.group(2))
            if end_n - start_n + 1 > 6:
                blockers.append(f"{title}：存在宽泛无效范围引用 [{start_n}–{end_n}]（跨度超过6篇文献）")
                break

        # Gate 2: Study-by-study bullet lists in Results / Discussion
        if kind in ('results', 'discussion'):
            if STUDY_LAUNDRY_BULLET_RE.search(body):
                blockers.append(f"{title}：结果或讨论章节严禁使用无序列表（- **作者**）逐篇罗列研究，须按主题横向综合为连贯学术散文段落")
            elif multi_section and len(re.findall(r'^\s*[-*]\s+\S', body, re.M)) >= 3:
                blockers.append(f"{title}：结果或讨论章节严禁使用连续无序列表提纲代替连贯学术段落")

        # Gate 3: Untranslated English sentences (>= 8 consecutive English words), ellipsis truncation (...), or '详见正文' placeholder in Chinese Results/Discussion
        if kind in ('results', 'discussion') and re.search(r'[\u4e00-\u9fff]', body):
            stripped_for_en = _strip_allowed_english_definitions(body)
            en_match = UNTRANSLATED_ENGLISH_RUN_RE.search(stripped_for_en)
            if en_match:
                blockers.append(f"{title}：中文正文或表格中残留未翻译的连续英文原句（“{en_match.group(0)[:60]}”），须转化为规范中文学术表述")
            if '详见正文' in body:
                blockers.append(f"{title}：表格或正文严禁使用“详见正文”敷衍占位符，须填入具体定量指标或结构化特征")
            if re.search(r'(?:[A-Za-z\u4e00-\u9fff]\.\.\.|…)\s*(?:\[E:|\||$)', body, re.M):
                blockers.append(f"{title}：存在英文摘要残句省略号截断（...），须完整提炼核心机制与结论")

        # Gate 5: Software engineering & self-attestation jargon leakage in academic manuscript sections
        eng_m = ENGINEERING_SELF_ATTESTATION_RE.search(body)
        if eng_m:
            blockers.append(f"{title}：学术主稿严禁包含软件工程哈希、去重算法或排版规则自述词汇（“{eng_m.group(0)}”），请剥离至《技术补充说明》")

        # Gate 6: PICO + MCID + PRISMA Figure 1 completeness check on full multi-section review Results
        if multi_section and len(sections) >= 6 and kind == 'results' and re.search(r'[\u4e00-\u9fff]', body) and len(body) > 400:
            missing_pico = []
            if not re.search(r'(?:样本量|\bN\s*=|\d+\s*例)', body):
                missing_pico.append('样本量(N)')
            if not re.search(r'(?:AUROC|AUC|aOR|OR|均值差|中位数|效应量|相关系数)', body):
                missing_pico.append('定量效应量')
            if not re.search(r'(?:MCID|最小临床重要差异)', body):
                missing_pico.append('MCID判定')
            if not re.search(r'(?:图\s*1|Figure\s*1|:::prisma-flow)', body):
                missing_pico.append('图1 PRISMA 2020流程图')
            if missing_pico:
                blockers.append(f"{title}：综述结果章节缺少核心循证要素（{', '.join(missing_pico)}）")

        if kind not in NON_CITING_KINDS and kind not in OPTIONAL_CITING_KINDS:
            for paragraph in PRISMA_BLOCK_RE.sub('', body).split('\n\n'):
                p_strip = paragraph.strip()
                if p_strip and not _is_non_prose_block(p_strip) and not re.search(r'\[E:[A-Za-z0-9_-]{1,40}\]', p_strip):
                    warnings.append(title + '：无引用段落，请人工核对' + ('（含数字）' if re.search(r'\d', p_strip) else ''))
    if not all_ids and not any('尚无证据引用' in b for b in blockers):
        blockers.append(sections[0]['title'] + '：尚无证据引用')
    return {
        'blockers': blockers,
        'warnings': warnings,
        'semantic_support': 'requires_human_review',
        'rule_version': 'writer-citations-sci-v3-6gates',
    }


def build_technical_supplement_markdown(store, project, view, bib_numbers, bib_refs):
    """Build a standalone Technical Supplement markdown document separating software engineering & audit proofs from the academic manuscript."""
    m = view['manuscript']
    refs = view['evidence']['items']
    label = '已获作者批准' if view['status'] == 'approved' else '未批准草稿'
    lines = [
        f"# {m['title']} — 技术补充说明与可复现性审计附录 (Technical Supplement)",
        "",
        f"**文档状态**：{label} · **主稿版本 ID**：`{m['id']}` · **证据包 SHA-256**：`{m['evidence_sha256']}`",
        "",
        "## S1. 多数据库检索策略语法转换与全量翻页完整性核验",
        "",
        "本补充材料记录文献检索底层的游标/偏移量自动翻页完整性验证、跨数据库检索式语法转换对照表及原始题录快照 SHA-256 指纹（上述软件工程防篡改细节均已从学术主稿正文中剥离，以确保主稿符合医学 SCI 期刊叙事规范）。",
        "",
    ]
    # Add multi-database query translations if source runs exist
    try:
        from .sources import SourceService
        from .query_translator import translate_query
        src_list = SourceService(store).list(project)
        runs = src_list.get('runs') or []
        if runs:
            lines.append("### S1.1 已冻结检索/导入来源快照清单")
            lines.append("")
            lines.append("| 来源快照 ID | 数据库/注册库 | 类型 | 检索/导入记录数 | 总命中数 | 翻页/导入完整性 | 快照 SHA-256 指纹 |")
            lines.append("| :--- | :--- | :--- | ---: | ---: | :--- | :--- |")
            first_query = None
            for r in runs:
                meta = r.get('metadata') or {}
                if not first_query and meta.get('query'):
                    first_query = meta['query']
                comp_str = '100% 完整 (Complete)' if r.get('complete') else '局部集 (Partial)'
                lines.append(f"| `{r['id'][:12]}` | {meta.get('database', '—')} | {meta.get('kind', 'database')} | {r.get('retrieved', 0)} | {r.get('total_hits', '—')} | {comp_str} | `{r['sha256'][:16]}...` |")
            lines.append("")
            if first_query:
                trans = translate_query(first_query, target='all', date_from='2022', date_to='2026')
                lines.append("### S1.2 五大生物医学数据库布尔检索式双轨转换表")
                lines.append("")
                lines.append("| 目标数据库 | 获取通道模式 | 转换后原生检索语法 | 合规获取与离线导入说明 |")
                lines.append("| :--- | :--- | :--- | :--- |")
                for _, tinfo in trans['translations'].items():
                    q_esc = tinfo['translated_query'].replace('|', '\\|')
                    lines.append(f"| {tinfo['database']} | `{tinfo['acquisition_mode']}` | `{q_esc}` | {tinfo['import_guide']} |")
                lines.append("")
    except Exception:
        pass

    lines.extend([
        "## S2. 跨库题录确定性去重状态机与双盲独立筛选哈希链",
        "",
        "1. **确定性去重规则**：原始题录导入后依次按规范化 PubMed ID（PMID）、数字对象唯一标识符（DOI，小写并剥离 URL 前缀）及归一化题名（剔除标点与大小写差异）执行确定性等价类归并；对存在字段冲突的候选对生成独立复核事件并记录裁决哈希。",
        "2. **双盲独立筛选与裁决锁定**：题名摘要初筛与全文资格评估均采用双评审员独立令牌盲筛；在双方均完成提交前，服务端拒绝揭盲或返回对方理由。裁决者揭盲后逐条记录结构化排除原因代码，全文纳入报告强制校验原文页码定位（Locator）与逐字摘录（Verbatim Quote）。",
        "3. **同源临床试验与队列实体映射（Report-to-Study Mapping）**：通过正则提取全文中的临床试验注册号（NCT / ChiCTR / KCT / ISRCTN）及（第一作者 + 第二作者 + 样本量特征）队列签名，将同一独立临床试验的系列发表报告归并映射至同一 `study_id`。",
        "",
        "## S3. 统计计算引擎运行环境与极小 P 值防零截断规范",
        "",
        "定量汇总、基线特征表（TableOne）、分类变量关联检验（Pearson $\\chi^2$ / Yates 校正 / Fisher 精确检验）、连续变量组间比较（Welch $t$ 检验 / Mann–Whitney $U$ 检验）及预测模型校准与决策曲线分析（ROC / Brier 评分 / Hosmer–Lemeshow 检验 / DCA / NRI / IDI）均在本地确定性统计引擎（Python `pandas`, `scipy`, `statsmodels`, `scikit-learn`）中执行。每次统计任务的输入载荷与输出产物均计算 SHA-256 哈希，且对双侧检验 $P < 0.001$ 的极小概率值实施防下溢零截断保护（严禁输出 `P = 0.000`，统一格式化为 `P < 0.001`）。",
        "",
        "## S4. 纳入证据逐条原文定位、原件 SHA-256 与作者审核记录",
        "",
    ])
    for e in refs:
        v_num = f" → 对应主稿参考文献 [{bib_numbers[e['id']]}]" if e['id'] in bib_numbers else ''
        lines.append(f"- **证据标识 `[E:{e['id']}]`{v_num}**：来源 `{e['source']}`；定位 `{e['locator']}`；原件 SHA-256 `{e['file_sha256']}`")
        lines.append(f"  - 原文核验摘录：{e['excerpt']}")
        if e.get('native_statistics'):
            b = e['native_statistics']
            lines.append(f"  - 原生统计任务绑定：Job `{b['job_id']}`；输入 SHA-256 `{b['payload_sha256']}`；结果产物 SHA-256 `{b['artifact_sha256']}`")
        if e.get('native_hunter'):
            b = e['native_hunter']
            lines.append(f"  - 全文筛选与研究映射绑定：报告 `{b['report_id']}`；归属研究 `{', '.join(b['study_ids'])}`（批次 `{b['review_id']}`）；全文裁决哈希 `{b['screening_event_hash']}`；研究映射哈希 `{b['mapping_event_hash']}`")
    lines.append("")
    return '\n'.join(lines)


class WriterService:
    def __init__(self,store):
        self.store=store
        with store.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS writer_objects(project TEXT,id TEXT,kind TEXT,artifact TEXT,digest TEXT,created TEXT,PRIMARY KEY(project,id));
            CREATE TABLE IF NOT EXISTS writer_heads(project TEXT,id TEXT,version TEXT,PRIMARY KEY(project,id));
            CREATE TABLE IF NOT EXISTS writer_reviews(project TEXT,version TEXT,sequence INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT);''')

    def load(self,project,id,kind=None):
        self.store.project(project)
        with self.store.db() as db:row=db.execute('SELECT kind,artifact,digest FROM writer_objects WHERE project=? AND id=?',(project,id)).fetchone()
        if not row or (kind and row[0]!=kind):raise ValueError('对象不属于此项目或类型错误')
        obj=json.loads(self.store.artifact(project,row[1]).read_text())
        if json_hash(obj)!=row[2]:raise ValueError('写作快照哈希不匹配')
        return obj

    def persist(self,project,kind,data,db=None):
        id=uuid.uuid4().hex; obj={**data,'id':id,'kind':kind,'project':project,'created':now(),'actor':'local_owner','identity_assurance':'single_owner_access_token'}
        name='writer-'+id+'.json';self.store.save(project,name,obj)
        args=(project,id,kind,name,json_hash(obj),obj['created'])
        if db is not None:db.execute('INSERT INTO writer_objects VALUES(?,?,?,?,?,?)',args)
        else:
            with self.store.db() as conn:conn.execute('INSERT INTO writer_objects VALUES(?,?,?,?,?,?)',args)
        return obj

    def document(self,project,filename,content_base64,source,classification,confirmed):
        self.store.project(project)
        if classification not in ('public','synthetic') or confirmed is not True:raise ValueError('仅接收确认可本地使用的公开/合成材料')
        source=text(source,2000)
        doc=snapshot(self.store,project,filename,content_base64)
        return self.persist(project,'document',{'source':source,'classification':classification,'snapshot':doc,'origin':'manual_upload','screening_inclusion':'not_asserted'})

    def verify_document(self,project,id):
        obj=self.load(project,id,'document');doc=obj['snapshot'];validate_snapshot(doc)
        if sha(self.store.artifact(project,doc['blob']).read_bytes())!=doc['file_sha256']:raise ValueError('原文文件已变化')
        if obj.get('origin')=='native_statistics':
            from .writer_statistics import verify
            verify(self.store,project,obj)
        if obj.get('origin')=='native_hunter':
            from .writer_hunter import verify
            verify(self.store,project,obj)
        return obj

    def evidence(self,project,label,items,parent_id=None):
        self.store.project(project);label=text(label,200)
        if parent_id:self.load(project,parent_id,'evidence')
        if not isinstance(items,list) or not 1<=len(items)<=200:raise ValueError('每包须有1至200项证据')
        seen=set();frozen=[]
        for item in items:
            if not isinstance(item,dict) or set(item)!={'id','document_id','locator','excerpt','support_note','verified_by','report_id','study_ids'}:raise ValueError('证据字段不完整')
            eid=item['id']
            if not isinstance(eid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',eid) or eid in seen:raise ValueError('证据ID无效或重复')
            seen.add(eid);doc=self.verify_document(project,item['document_id'])
            validate_evidence({'fulltext':doc['snapshot']},item['locator'],item['excerpt'])
            for field in ('support_note','verified_by'):text(item[field],2000)
            if not isinstance(item['report_id'],str) or len(item['report_id'])>200:raise ValueError('报告ID无效')
            if not isinstance(item['study_ids'],list) or len(item['study_ids'])>20 or any(not isinstance(s,str) or not 1<=len(s)<=200 for s in item['study_ids']):raise ValueError('研究ID无效')
            frozen.append({**item,'origin':doc.get('origin','manual_upload'),'document_sha256':json_hash(doc),'file_sha256':doc['snapshot']['file_sha256'],'text_sha256':doc['snapshot']['text_sha256'],'source':doc['source'],'classification':doc['classification'],'support_assurance':'human_declared','lineage_assurance':'manual_ids_not_linked_to_hunter'})
            if doc.get('bibliographic'):frozen[-1]['bibliographic']=doc['bibliographic']
            if doc.get('origin')=='native_statistics':frozen[-1]['native_statistics']=doc['native_statistics']
            if doc.get('origin')=='native_hunter':
                b=doc['native_hunter']
                if item['report_id'] not in ('',b['report_id']) or item['study_ids'] not in ([],b['study_ids']):raise ValueError('手工报告/研究ID与Hunter原生映射冲突')
                frozen[-1].update(native_hunter=b,report_id=b['report_id'],study_ids=b['study_ids'],lineage_assurance='native_hunter_selected_version',captured_by=doc['captured_by'])
        if len(canonical(frozen))>500000:raise ValueError('证据包超过500000字符')
        return self.persist(project,'evidence',{'label':label,'items':frozen,'parent_id':parent_id})

    def verify_package(self,project,id):
        package=self.load(project,id,'evidence')
        for e in package['items']:
            doc=self.verify_document(project,e['document_id'])
            if json_hash(doc)!=e['document_sha256']:raise ValueError('原文版本不一致')
            validate_evidence({'fulltext':doc['snapshot']},e['locator'],e['excerpt'])
        return package

    def save(self,project,title,sections,evidence_id,manuscript_id=None,expected_version=None):
        title=text(title,300);package=self.verify_package(project,evidence_id)
        if not isinstance(sections,list) or not 1<=len(sections)<=30:raise ValueError('须有1至30个章节')
        clean=[]
        for s in sections:
            if not isinstance(s,dict) or set(s)!={'title','body'}:raise ValueError('章节须包含标题和正文')
            clean.append({'title':text(s['title'],300),'body':text(s['body'],120000)})
        if len(canonical(clean))>800000:raise ValueError('稿件超过800000字符')
        checks=citation_check(clean,package['items'])
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if manuscript_id:
                row=db.execute('SELECT version FROM writer_heads WHERE project=? AND id=?',(project,manuscript_id)).fetchone()
                if not row or row[0]!=expected_version:raise ValueError('稿件已更新或不属于此项目，请刷新后合并')
                self.load(project,expected_version,'manuscript')
            else:
                if expected_version is not None:raise ValueError('新稿不能指定旧版本')
                manuscript_id=uuid.uuid4().hex
            obj=self.persist(project,'manuscript',{'manuscript_id':manuscript_id,'parent_version':expected_version,'title':title,'sections':clean,'evidence_id':evidence_id,'evidence_sha256':json_hash(package),'checks':checks,'llm_calls':0,'origin':'manual_draft'},db)
            db.execute('INSERT OR REPLACE INTO writer_heads VALUES(?,?,?)',(project,manuscript_id,obj['id']))
        return obj

    def reviews(self,project,version):
        with self.store.db() as db:rows=db.execute('SELECT event FROM writer_reviews WHERE project=? AND version=? ORDER BY sequence',(project,version)).fetchall()
        events=[];previous=''
        for row in rows:
            event=json.loads(row[0]);body={k:v for k,v in event.items() if k!='hash'}
            if event['previous_hash']!=previous or json_hash(body)!=event['hash']:raise ValueError('审核记录已变化')
            events.append(event);previous=event['hash']
        return events

    def inspect(self,project,version):
        obj=self.load(project,version,'manuscript');package=self.verify_package(project,obj['evidence_id'])
        if json_hash(package)!=obj['evidence_sha256']:raise ValueError('证据包版本不一致')
        events=self.reviews(project,version)
        with self.store.db() as db:head=db.execute('SELECT version FROM writer_heads WHERE project=? AND id=?',(project,obj['manuscript_id'])).fetchone()[0]
        return {'manuscript':obj,'evidence':package,'reviews':events,'status':events[-1]['decision'] if events else 'needs_human_review','is_current':head==version}

    def review(self,project,version,decision,author,note,confirmed):
        if decision not in ('approved','changes_requested') or confirmed is not True:raise ValueError('请明确确认本版的作者审核')
        author=text(author,200);note=text(note,4000)
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');view=self.inspect(project,version)
            if not view['is_current']:raise ValueError('仅可审核当前版本')
            if decision=='approved' and view['manuscript']['checks']['blockers']:raise ValueError('先修复引用阻断项，再批准')
            events=view['reviews'];event={'version':version,'manuscript_sha256':json_hash(view['manuscript']),'decision':decision,'author':author,'note':note,'timestamp':now(),'actor':'local_owner','author_assurance':'owner_declared_name','support_confirmed':confirmed,'previous_hash':events[-1]['hash'] if events else ''}
            event['hash']=json_hash(event);db.execute('INSERT INTO writer_reviews(project,version,event) VALUES(?,?,?)',(project,version,canonical(event)))
        return event

    def export(self,project,version):
        view=self.inspect(project,version);m=view['manuscript']
        bib_numbers,bib_refs,stat_ids,used_ids=order_citations(m['sections'],view['evidence']['items'])
        used=set(used_ids)
        refs=[e for e in view['evidence']['items'] if e['id'] in used]
        label='已获作者批准' if view['status']=='approved' else '未批准草稿'
        academic_md=f"# {m['title']}\n\n"
        for s in m['sections']:
            rendered_body=render_academic_text(s['body'],bib_numbers,stat_ids,convert_prisma_block=True)
            academic_md+=f"## {s['title']}\n\n{rendered_body}\n\n"
        if bib_refs:
            academic_md+='## 参考文献 (References)\n\n'
            for idx,e in enumerate(bib_refs,1):
                academic_md+=f"{idx}. {format_vancouver_reference(e)}\n"
            academic_md+='\n'
        audit_md=f"---\n\n## 附录：工作台证据溯源与作者审核记录\n\n{label} · 版本 {version}\n\n"
        for e in refs:
            v_num=f" → [{bib_numbers[e['id']]}]" if e['id'] in bib_numbers else ''
            audit_md+=f"- [E:{e['id']}]{v_num} {e['source']}；{e['locator']}；原件 SHA256 {e['file_sha256']}\n  摘录：{e['excerpt']}\n"
        for e in refs:
            if e.get('native_statistics'):
                b=e['native_statistics'];audit_md+=f"\n统计证据 [E:{e['id']}]：任务 {b['job_id']}；输入 SHA256 {b['payload_sha256']}；结果 SHA256 {b['artifact_sha256']}；仅合成数据。\n"
        for e in refs:
            if e.get('native_hunter'):
                b=e['native_hunter'];audit_md+=f"\nHunter证据 [E:{e['id']}]：报告 {b['report_id']}；研究 {', '.join(b['study_ids'])}（限批次 {b['review_id']}）；裁决版本 {b['screening_event_hash']}；映射版本 {b['mapping_event_hash']}。\n"
        md=academic_md+audit_md
        tech_supp_md=build_technical_supplement_markdown(self.store,project,view,bib_numbers,bib_refs)
        bundle={**view,'exported_at':now(),'markdown':md,'academic_markdown':academic_md.strip()+'\n','technical_supplement_markdown':tech_supp_md,'references':refs,'vancouver_references':[{'number':i,'evidence_id':e['id'],'citation':format_vancouver_reference(e)} for i,e in enumerate(bib_refs,1)],'llm_calls':0,'format':'local_markdown_and_audit_json_no_translation'}
        obj=self.persist(project,'export',bundle)
        return obj

    def export_word(self,project,version):
        import base64
        from .writer_docx import render, render_technical_supplement
        bundle=self.export(project,version)
        try:
            raw=render(bundle,include_audit_appendix=True)
            academic_raw=render(bundle,include_audit_appendix=False)
            tech_supp_raw=render_technical_supplement(bundle)
        except ValueError:raise ValueError('正文含Word不支持的控制字符，请修订后导出')
        filename='manuscript-'+version+'-'+bundle['id']+'.docx'
        tech_filename='technical-supplement-'+version+'-'+bundle['id']+'.docx'
        target=self.store.artifact(project,filename)
        with target.open('xb') as f:f.write(raw)
        target.chmod(0o600)
        tech_target=self.store.artifact(project,tech_filename)
        with tech_target.open('xb') as f:f.write(tech_supp_raw)
        tech_target.chmod(0o600)
        digest=sha(raw)
        manifest=self.persist(project,'word_export',{'version':version,'audit_export_id':bundle['id'],'audit_sha256':json_hash(bundle),'filename':filename,'technical_supplement_filename':tech_filename,'file_sha256':digest,'academic_file_sha256':sha(academic_raw),'technical_supplement_file_sha256':sha(tech_supp_raw),'status':bundle['status'],'llm_calls':0,'translation':'none_saved_text_only'})
        return {'filename':filename,'technical_supplement_filename':tech_filename,'content_base64':base64.b64encode(raw).decode(),'academic_content_base64':base64.b64encode(academic_raw).decode(),'technical_supplement_content_base64':base64.b64encode(tech_supp_raw).decode(),'file_sha256':digest,'manifest':manifest,'audit':bundle}

    def capture_statistics(self,project,job_id,confirmed):
        from .writer_statistics import capture
        return capture(self,project,job_id,confirmed)

    def auto_draft(self,project,evidence_id,guideline='PRISMA-ScR',title='',review=None,save_manuscript=False):
        package=self.verify_package(project,evidence_id)
        prisma_report=None
        charting_rows=None
        target_review=review
        if not target_review:
            for item in package['items']:
                nh=item.get('native_hunter')
                if nh and nh.get('review_id'):
                    target_review=nh['review_id']
                    break
        if target_review:
            try:
                from .screening_http import ScreeningService
                s=ScreeningService(self.store)
                with self.store.db() as db:ev=s.ledger._events(db,target_review)
                adj=ev[0]['data']['protocol']['adjudicator']
                prisma_report=s.prisma.preview(target_review,adj)
                try:
                    cst=s.charting.state(target_review,adj)
                    if cst.get('charting_valid') and cst.get('charting'):
                        charting_rows=cst['charting']
                    else:
                        charting_rows=s.charting.extract(target_review,adj,mode='auto',save=True)['charting']
                except Exception:
                    charting_rows=None
            except Exception:
                prisma_report=None
        from .writer_autopilot import build_sci_manuscript_sections
        draft=build_sci_manuscript_sections(self.store,project,package,prisma_report=prisma_report,guideline=guideline or 'PRISMA-ScR',custom_title=title,charting_rows=charting_rows)
        if save_manuscript is True:
            saved=self.save(project,draft['title'],draft['sections'],evidence_id)
            return {'draft':draft,'manuscript':saved}
        return {'draft':draft}

    def list(self,project):
        self.store.project(project)
        with self.store.db() as db:
            rows=db.execute('SELECT id,kind,created,artifact FROM writer_objects WHERE project=? ORDER BY created',(project,)).fetchall()
            heads=dict(db.execute('SELECT id,version FROM writer_heads WHERE project=?',(project,)))
            reviews={}
            for v,ev in db.execute('SELECT version,event FROM writer_reviews WHERE project=? ORDER BY sequence',(project,)):
                try:reviews[v]=json.loads(ev).get('decision')
                except Exception:pass
        objects=[]
        for oid,kind,created,artifact in rows:
            item={'id':oid,'kind':kind,'created':created}
            try:
                data=json.loads(self.store.artifact(project,artifact).read_text())
                if kind=='document':
                    fname=data.get('snapshot',{}).get('filename','')
                    src=data.get('source','')
                    item['label']=f"{fname+' · ' if fname else ''}{src} · {oid[:8]}"
                elif kind=='evidence':
                    item['label']=f"{data.get('label','')}（{len(data.get('items',[]))}项） · {oid[:8]}"
                elif kind=='manuscript':
                    status={'approved':'已批准','changes_requested':'需修改'}.get(reviews.get(oid),'待审核')
                    head='当前' if heads.get(data.get('manuscript_id'))==oid else '历史'
                    item['label']=f"{data.get('title','')} · {status} · {head} · {oid[:8]}"
            except Exception:
                pass
            objects.append(item)
        return {'objects':objects,'heads':heads}

    def dispatch(self,operation,body):
        fields={'capture_statistics':{'project','job_id','confirmed'},'document':{'project','filename','content_base64','source','classification','confirmed'},'evidence':{'project','label','items','parent_id'},'save':{'project','title','sections','evidence_id','manuscript_id','expected_version'},'inspect':{'project','version'},'review':{'project','version','decision','author','note','confirmed'},'export':{'project','version'},'export_word':{'project','version'},'load':{'project','id'},'auto_draft':{'project','evidence_id'}}
        optional={'guideline','title','review','save_manuscript'} if operation=='auto_draft' else set()
        if operation not in fields or (set(body)-optional)!=fields[operation]:raise ValueError('写作请求字段不完整或包含未知字段')
        return getattr(self,operation)(**body)
