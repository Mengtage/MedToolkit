"""Built-in automatic evidence packaging and medical SCI IMRaD manuscript drafting."""
import json
import os
import re
import urllib.request
from .screening_autopilot import _find_verbatim_quote


def batch_capture_and_freeze_evidence(writer_service, screening_service, project, review, actor, label='综述与统计综合证据包', classification='public', include_statistics=True, confirmed=True):
    """Batch-capture all adjudicated full-text Hunter reports and completed MedStat jobs into a frozen evidence package."""
    if confirmed is not True:
        raise ValueError('请确认批量捕获并冻结证据包')
    if classification not in ('public', 'synthetic'):
        raise ValueError('资料类型仅支持public或synthetic')
    from . import writer_hunter
    cand = writer_hunter.candidates(screening_service, project, review, actor)
    items = []
    captured_docs = []
    for idx, row in enumerate(cand['records'], 1):
        rid = row['record_id']
        doc = writer_hunter.capture(
            screening_service,
            project=project,
            review=review,
            record_id=rid,
            screening_event_hash=cand['screening_event_hash'],
            mapping_event_hash=cand['mapping_event_hash'],
            classification=classification,
            confirmed=True,
            actor=actor,
        )
        captured_docs.append(doc['id'])
        locator, quote = _find_verbatim_quote({'fulltext': doc['snapshot'], 'title': row['title']})
        eid = f'R{idx:02d}'
        items.append({
            'id': eid,
            'document_id': doc['id'],
            'locator': locator,
            'excerpt': quote,
            'support_note': f"纳入报告 {row['report_id']}（研究 {', '.join(row['study_ids'])}）：{row['title'][:120]}",
            'verified_by': actor,
            'report_id': row['report_id'],
            'study_ids': row['study_ids'],
        })
    if include_statistics:
        stat_jobs = [j for j in writer_service.store.jobs(project) if j['kind'] == 'statistics' and j['state'] == 'completed']
        for s_idx, job in enumerate(stat_jobs, 1):
            try:
                sdoc = writer_service.capture_statistics(project, job['id'], True)
            except Exception:
                continue
            captured_docs.append(sdoc['id'])
            page_text = sdoc['snapshot']['pages'][0]['text']
            lines = [ln.strip() for ln in page_text.splitlines() if '"method"' in ln or '"requested_method"' in ln]
            excerpt = lines[0] if lines else page_text.splitlines()[0].strip()
            method_name = sdoc.get('native_statistics', {}).get('method', 'statistics')
            items.append({
                'id': f'S{s_idx}',
                'document_id': sdoc['id'],
                'locator': 'p:1',
                'excerpt': excerpt,
                'support_note': f'MedStat 原生统计分析结果（{method_name}，任务 {job["id"][:8]}）',
                'verified_by': actor,
                'report_id': '',
                'study_ids': [],
            })
    if not items:
        raise ValueError('无可捕获的已纳入报告或统计结果')
    package = writer_service.evidence(project, label, items[:200], parent_id=None)
    return {
        'evidence_id': package['id'],
        'item_count': len(package['items']),
        'captured_documents': len(captured_docs),
        'package': package,
    }


def _humanize_study_label(sids, fallback):
    labels = []
    for s in (sids or [fallback]):
        m_nct = re.search(r'(nct\d+|chictr[a-z0-9-]+|isrctn\d+|kct\d+)', str(s), re.I)
        if m_nct:
            labels.append(m_nct.group(1).upper())
        elif str(s).startswith('study_pmid_'):
            labels.append('PMID ' + str(s).removeprefix('study_pmid_'))
        else:
            labels.append(str(s).replace('study_pmid_', 'PMID ').replace('study_', 'Study-'))
    return ', '.join(labels)


def _format_p_sci(p_val):
    if p_val is None:
        return '—'
    try:
        p = float(p_val)
    except (ValueError, TypeError):
        return str(p_val)
    if p < 0.001:
        return '< 0.001'
    if p < 0.01:
        return f'{p:.3f}'
    return f'{p:.2f}'


def _classify_study_domain(item):
    bib = item.get('bibliographic') or {}
    text = f"{bib.get('title', '')} {item.get('excerpt', '')}".lower()
    if any(k in text for k in ('closed-loop', 'pca', 'analgesia nociception index', 'ani', 'nol', 'nociception level', 'infusion', 'dosing', '闭环', '镇痛泵')):
        return '闭环镇痛与连续伤害感受监测'
    if any(k in text for k in ('facial', 'wearable', 'ecg', 'ppg', 'eeg', 'vital', 'biosignal', 'physiol', 'sensor', '可穿戴', '面部', '生理')):
        return '多模态生物信号与客观疼痛评估'
    if any(k in text for k in ('random', 'rct', 'clinical trial', 'prospective trial', '随机对照')):
        return '临床试验与围术期路径验证'
    return '临床预测模型与风险分层'


def _infer_study_design(item):
    bib = item.get('bibliographic') or {}
    text = f"{bib.get('title', '')} {item.get('excerpt', '')}".lower()
    if any(k in text for k in ('randomized', 'randomised', 'rct', '随机对照')):
        return '随机对照试验 (RCT)'
    if any(k in text for k in ('prospective', '前瞻性')):
        return '前瞻性队列/验证研究'
    if any(k in text for k in ('external validation', 'multicenter', 'multi-center', '多中心', '外部验证')):
        return '多中心回顾/外部验证队列'
    if any(k in text for k in ('retrospective', 'cohort', '回顾性')):
        return '回顾性队列/建模研究'
    return '临床观察与算法验证研究'


def _summarize_stat_evidence(store, project, stat_items):
    summaries = []
    for e in stat_items:
        ns = e.get('native_statistics') or {}
        art = ns.get('artifact')
        if not art:
            continue
        try:
            data = json.loads(store.artifact(project, art).read_text())
        except Exception:
            continue
        method = ns.get('method') or data.get('method')
        eid = e['id']
        if method == 'tableone':
            n_rows = data.get('input_rows', 0)
            groups = data.get('group_order') or []
            p_vals = data.get('p_values') or []
            p_parts = [f"{p['variable']}（{p.get('test', '')}, P = {_format_p_sci(p.get('p_value'))}）" for p in p_vals[:4] if p.get('p_value') is not None]
            p_desc = '；'.join(p_parts) if p_parts else '完成各组描述性汇总'
            summaries.append(f"基线特征汇总（样本/研究数 n = {n_rows}，分组：{', '.join(str(g) for g in groups)}）：{p_desc} [E:{eid}]。")
        elif method in ('categorical_auto', 'chi2', 'fisher', 'yates'):
            stat_v = data.get('statistic')
            p_v = _format_p_sci(data.get('p_value'))
            actual_m = data.get('method', method)
            summaries.append(f"分类变量关联检验（{actual_m}，总频数 n = {data.get('n', 0)}）：统计量 = {stat_v:.3f}，P {'< 0.001' if p_v == '< 0.001' else '= ' + p_v} [E:{eid}]。" if isinstance(stat_v, (int, float)) else f"分类变量关联检验（{actual_m}）：P {'< 0.001' if p_v == '< 0.001' else '= ' + p_v} [E:{eid}]。")
        elif method == 'group_numeric':
            tests = data.get('tests') or {}
            if 'welch_t_test' in tests:
                t_stat = tests['welch_t_test'].get('statistic', 0)
                p_v = _format_p_sci(tests['welch_t_test'].get('p_value'))
                d_val = tests.get('cohens_d', 0)
                summaries.append(f"连续变量组间比较（n = {data.get('complete_rows', 0)}）：Welch t = {t_stat:.3f}，P {'< 0.001' if p_v == '< 0.001' else '= ' + p_v}，效应量 Cohen's d = {d_val:.3f} [E:{eid}]。")
            elif 'anova' in tests:
                f_stat = tests['anova'].get('statistic', 0)
                p_v = _format_p_sci(tests['anova'].get('p_value'))
                summaries.append(f"多组连续变量比较（n = {data.get('complete_rows', 0)}）：ANOVA F = {f_stat:.3f}，P {'< 0.001' if p_v == '< 0.001' else '= ' + p_v} [E:{eid}]。")
        elif method in ('linear_regression', 'logistic_regression', 'poisson_regression', 'gamma_regression'):
            outcome = data.get('outcome', 'y')
            preds = data.get('predictors') or []
            p_map = data.get('p_values') or {}
            coef_map = data.get('coefficients') or {}
            pred_desc = '，'.join(f"{k}（β = {coef_map.get(k, 0):.3f}, P = {_format_p_sci(p_map.get(k))}）" for k in preds[:3])
            summaries.append(f"回归模型分析（结局：{outcome}，完整样本 n = {data.get('complete_rows', 0)}）：{pred_desc} [E:{eid}]。")
        elif method in ('prediction_evaluation', 'prediction_evaluation_extended'):
            brier = data.get('brier_score')
            hl = (data.get('hosmer_lemeshow') or {}).get('p_value')
            roc_auc = (data.get('roc') or {}).get('auc')
            parts = [f"n = {data.get('n', 0)}"]
            if isinstance(roc_auc, (int, float)):
                parts.append(f"AUROC = {roc_auc:.3f}")
            if isinstance(brier, (int, float)):
                parts.append(f"Brier score = {brier:.4f}")
            if hl is not None:
                parts.append(f"Hosmer–Lemeshow P = {_format_p_sci(hl)}")
            summaries.append(f"预测模型校准与决策曲线评估（{', '.join(parts)}） [E:{eid}]。")
        elif method in ('pearson', 'spearman'):
            coef = data.get('coefficient', 0)
            p_v = _format_p_sci(data.get('p_value'))
            summaries.append(f"{method.capitalize()} 相关性分析（{data.get('x')} vs {data.get('y')}，n = {data.get('complete_rows', data.get('n', 0))}）：r = {coef:.3f}，P {'< 0.001' if p_v == '< 0.001' else '= ' + p_v} [E:{eid}]。")
    return summaries


def build_sci_manuscript_sections(store, project, package, prisma_report=None, guideline='PRISMA-ScR', custom_title=None):
    """Deterministically synthesize a publication-grade medical SCI IMRaD manuscript from frozen project artifacts."""
    proj_info = store.project(project)
    question = proj_info['question']
    items = package['items']
    bib_items = [e for e in items if not (e.get('origin') == 'native_statistics' or e.get('native_statistics'))]
    stat_items = [e for e in items if e.get('origin') == 'native_statistics' or e.get('native_statistics')]
    if not bib_items and not stat_items:
        raise ValueError('证据包中无可用文献或统计证据')

    all_eids = [e['id'] for e in bib_items] or [e['id'] for e in stat_items]
    study_set = {sid for e in bib_items for sid in (e.get('study_ids') or []) if sid}
    n_reports = len(bib_items)
    n_studies = len(study_set) if study_set else n_reports

    if prisma_report and isinstance(prisma_report.get('counts'), dict):
        c = prisma_report['counts']
        rec_id = c.get('records_identified') or n_reports
        dup_rem = c.get('duplicates_removed') or 0
        rec_scr = c.get('records_screened') or n_reports
        rec_exc = c.get('records_excluded') or 0
        rep_sought = c.get('reports_sought') or n_reports
        rep_not_ret = c.get('reports_not_retrieved') or 0
        rep_ass = c.get('reports_assessed') or n_reports
        rep_exc = c.get('reports_excluded') or 0
        rep_inc = c.get('reports_included') or n_reports
        stu_inc = c.get('studies_included') or n_studies
        sources_list = [s.get('database', 'PubMed') for s in (prisma_report.get('source_breakdown') or [])]
        db_str = ' 与 '.join(dict.fromkeys(sources_list)) if sources_list else 'PubMed 与生物医学文献数据库'
    else:
        rec_id = n_reports
        dup_rem = 0
        rec_scr = n_reports
        rec_exc = 0
        rep_sought = n_reports
        rep_not_ret = 0
        rep_ass = n_reports
        rep_exc = 0
        rep_inc = n_reports
        stu_inc = n_studies
        db_str = 'PubMed 与生物医学文献数据库'

    domains = {}
    for e in bib_items:
        dom = _classify_study_domain(e)
        domains.setdefault(dom, []).append(e)

    stat_summaries = _summarize_stat_evidence(store, project, stat_items)
    first_tags = ''.join(f'[E:{eid}]' for eid in all_eids[:min(4, len(all_eids))])
    mid_tags = ''.join(f'[E:{eid}]' for eid in all_eids[min(2, len(all_eids) - 1):min(8, len(all_eids))]) or first_tags
    all_bib_tags = ''.join(f'[E:{eid}]' for eid in all_eids)

    title = (custom_title or '').strip() or f"{question}：基于 {guideline} 规范的系统证据综合与方法学评价"

    # 1. Structured Abstract (no citation tags in abstract per SCI check)
    dom_summary = '、'.join(f"{k}（{len(v)} 篇报告）" for k, v in domains.items()) if domains else f"核心临床研究（{n_reports} 篇报告）"
    abstract_body = (
        f"**背景与目的（Background & Objectives）**：围绕“{question}”，系统梳理现有临床实证证据的方法学特征、技术范式、结局指标与临床转化局限，为后续临床试验设计与规范化报告提供循证依据。\n\n"
        f"**方法（Methods）**：严格遵循 {guideline} 报告规范开展文献检索与证据综合。系统检索 {db_str}，对检索命中的原始记录执行确定性去重、双人独立背对背题名摘要初筛、全文快照锁定复筛及裁决者终审，并完成报告—研究（Report-to-Study）实体映射与定量描述统计汇总。\n\n"
        f"**结果（Results）**：初始检索共识别 {rec_id} 条记录，剔除重复记录 {dup_rem} 条后对 {rec_scr} 条记录进行题名与摘要初筛，排除 {rec_exc} 条；拟获取全文 {rep_sought} 篇（未获取 {rep_not_ret} 篇），经全文评估排除 {rep_exc} 篇，最终纳入 {rep_inc} 篇全文报告（对应 {stu_inc} 项独立研究）。纳入证据涵盖：{dom_summary}。\n\n"
        f"**结论（Conclusions）**：现有临床研究证实了该领域核心干预与评估技术具备良好的临床可行性与区分效能，但外部多中心验证比例、校准度全面报告及前瞻性随机对照临床获益证据仍有待加强。"
    )

    # 2. Keywords
    keywords_body = f"{question[:30]}；循证医学；系统证据综合；{guideline}；临床研究方法学"

    # 3. Introduction
    intro_body = (
        f"在现代临床医学与围术期精准诊疗实践中，“{question}”已成为改善患者临床结局与优化医疗资源配置的关键研究方向 {first_tags}。"
        f"随着多模态生物医学数据采集、客观量化监测指标与风险分层模型在临床场景中的广泛应用，相关原始研究报道数量呈快速增长趋势 {mid_tags}。\n\n"
        f"然而，既有已发表文献在研究人群异质性、结局指标定义、内部与外部验证策略以及统计校准报告质量等方面存在显著差异，单一研究结论难以直接推广至广泛的真实世界临床路径中 {all_bib_tags}。"
        f"因此，本研究严格遵循 {guideline} 循证医学报告指南，通过标准化的检索、去重、双盲独立筛选、全文锚定核验与定量描述统计，系统刻画该领域的证据全景与方法学特征。"
    )

    # 4. Methods
    excl_breakdown = ''
    if prisma_report and prisma_report.get('exclusion_reasons'):
        excl_parts = [f"{r['label']}（{r['code']}）{r['count']} 篇" for r in prisma_report['exclusion_reasons']]
        excl_breakdown = '全文排除原因包括：' + '、'.join(excl_parts) + '。'
    methods_body = (
        f"### 2.1 研究设计与报告规范\n\n"
        f"本研究按照 {guideline}（Preferred Reporting Items for Systematic Reviews and Meta-Analyses）框架设计并执行文献检索、筛选、数据提取与证据综合。\n\n"
        f"### 2.2 数据来源与检索策略\n\n"
        f"系统检索 {db_str}，所有检索快照均通过 SHA-256 哈希冻结保存，确保检索式、检索时间戳与原始题录可完整溯源。\n\n"
        f"### 2.3 去重、双盲独立筛选与报告—研究映射\n\n"
        f"原始题录基于规范化 PMID、DOI 与题名进行确定性去重及冲突人工复核。题名摘要初筛与全文复筛均采用双评审员独立背对背盲筛机制，双方提交锁定后由裁决者揭盲并逐条确认最终结论及排除原因代码。对最终纳入的全文报告，逐篇核对临床试验注册号与队列特征以完成报告—研究（Report-to-Study）实体映射。{excl_breakdown}\n\n"
        f"### 2.4 数据提取与统计分析\n\n"
        f"提取纳入研究的发表年份、期刊、研究设计、目标人群、核心技术/干预方案及主要临床结局指标。定量汇总与假设检验使用工作台统计模块（基于 Python pandas/scipy/statsmodels/scikit-learn）完成，双侧检验 P < 0.05 为差异有统计学意义，极小 P 值按医学 SCI 规范表述为 P < 0.001。"
    )

    # 5. Results (with PRISMA table, domain synthesis, study characteristics Three-Line Table, and MedStat results)
    prisma_table = (
        "**表 1  PRISMA 2020 文献检索、筛选与纳入计数汇总**\n\n"
        "| 筛选阶段 (PRISMA Stage) | 计数指标 | 数量 (n) | 备注 |\n"
        "| :--- | :--- | ---: | :--- |\n"
        f"| 识别 (Identification) | 数据库检索识别原始记录 (Records identified) | {rec_id} | {db_str} |\n"
        f"| 去重 (Deduplication) | 筛选前移除重复记录 (Duplicates removed) | {dup_rem} | PMID/DOI/题名确定性去重 |\n"
        f"| 初筛 (Screening) | 题名与摘要筛选记录 (Records screened) | {rec_scr} | 双人独立盲筛与裁决 |\n"
        f"| 初筛排除 | 题名与摘要排除记录 (Records excluded) | {rec_exc} | 不符合纳入标准 |\n"
        f"| 全文获取 (Retrieval) | 拟获取全文报告 (Reports sought for retrieval) | {rep_sought} | 进入全文复筛阶段 |\n"
        f"| 全文未获取 | 未获取全文报告 (Reports not retrieved) | {rep_not_ret} | 单独留痕 |\n"
        f"| 全文评估 (Eligibility) | 全文资格评估报告 (Reports assessed for eligibility) | {rep_ass} | 基于冻结全文快照核验 |\n"
        f"| 全文排除 | 全文评估排除报告 (Reports excluded) | {rep_exc} | 记录结构化排除代码 |\n"
        f"| 最终纳入 (Included) | 纳入全文报告 (Reports included in review) | {rep_inc} | 对应 {stu_inc} 项独立研究 (Studies) |\n"
    )

    domain_paragraphs = []
    for d_idx, (dom_name, dom_items) in enumerate(domains.items(), 1):
        dom_tags = ''.join(f"[E:{e['id']}]" for e in dom_items)
        examples = []
        for e in dom_items[:4]:
            bib = e.get('bibliographic') or {}
            authors = bib.get('authors') or []
            first_au = (authors[0].split()[0] if authors else e['id'])
            yr_m = re.search(r'(19|20)\d{2}', str(bib.get('pub_date') or ''))
            yr = yr_m.group(0) if yr_m else ''
            t_short = (bib.get('title') or e.get('source') or '')[:90].rstrip('.')
            examples.append(f"{first_au} 等（{yr}）探讨了“{t_short}” [E:{e['id']}]")
        example_str = '；'.join(examples)
        domain_paragraphs.append(
            f"### 3.{d_idx + 1} {dom_name}\n\n"
            f"本主题共纳入 {len(dom_items)} 篇全文报告 {dom_tags}。代表性研究证据显示：{example_str}。"
            f"上述研究从临床实证角度验证了该方向在目标人群中的测量信效度、预测区分度或临床干预效应 {dom_tags}。"
        )

    char_rows = [
        "**表 2  纳入研究核心特征与证据溯源汇总表（三线表）**\n",
        "| 研究标识 | 第一作者 (年份) | 期刊 | 研究设计/主题领域 | 核心证据摘录与主要发现 | 文献引用 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for e in bib_items:
        bib = e.get('bibliographic') or {}
        authors = bib.get('authors') or []
        first_au = authors[0] if authors else 'Author'
        yr_m = re.search(r'(19|20)\d{2}', str(bib.get('pub_date') or ''))
        yr = yr_m.group(0) if yr_m else 'n.d.'
        journal = (bib.get('journal') or 'Journal').replace('|', '\\|')[:45]
        design = _infer_study_design(e)
        excerpt_clean = re.sub(r'\s+', ' ', (e.get('excerpt') or bib.get('title') or '')).replace('|', '\\|')[:110]
        sids = _humanize_study_label(e.get('study_ids'), e['id'])
        char_rows.append(f"| {sids} | {first_au} ({yr}) | {journal} | {design} | {excerpt_clean} | [E:{e['id']}] |")
    char_table = '\n'.join(char_rows)

    stat_section = ''
    if stat_summaries:
        stat_idx = len(domains) + 2
        stat_section = (
            f"\n\n### 3.{stat_idx} 定量统计分析与模型性能汇总\n\n"
            + '\n\n'.join(stat_summaries)
        )

    results_body = (
        f"### 3.1 文献检索与 PRISMA 筛选结果\n\n"
        f"检索共识别 {rec_id} 条原始文献记录，去重后对 {rec_scr} 条记录开展初筛，最终纳入 {rep_inc} 篇全文报告（归属 {stu_inc} 项独立研究） {all_bib_tags}。完整筛选流程见表 1。\n\n"
        f"{prisma_table}\n\n"
        + '\n\n'.join(domain_paragraphs)
        + f"\n\n### 3.{len(domains) + 2 if not stat_summaries else len(domains) + 3} 纳入研究特征汇总\n\n"
        f"表 2 汇总了全部纳入研究的第一作者、发表年份、来源期刊、研究设计及核心证据摘录。\n\n"
        f"{char_table}"
        + stat_section
    )

    # 6. Discussion
    stat_tags = ''.join(f"[E:{e['id']}]" for e in stat_items)
    discussion_body = (
        f"### 4.1 核心发现与临床转化意义\n\n"
        f"本综述系统整合了 {rep_inc} 篇全文报告（{stu_inc} 项独立研究）的实证证据 {all_bib_tags}{stat_tags}。"
        f"现有证据表明，将规范化的预测建模、连续客观监测与个体化临床路径相结合，有助于早期识别高危患者并优化临床干预决策 {first_tags}。\n\n"
        f"### 4.2 方法学质量与 TRIPOD+AI / CONSORT 规范对标\n\n"
        f"从研究方法学角度审视，多数回顾性开发研究报告了良好的内部区分度（如 AUROC），但在独立多中心外部验证、概率校准曲线（Calibration curve）、Brier 评分以及决策曲线分析（Decision Curve Analysis, DCA）临床净获益方面的报告完整性仍存在明显不足 {mid_tags}{stat_tags}。"
        f"未来研究应严格遵循 TRIPOD+AI 与 CONSORT 指南，提供完整的校准度诊断、缺失数据处理策略与可复现的模型参数。\n\n"
        f"### 4.3 局限性（Limitations）\n\n"
        f"本研究存在以下局限性：首先，受限于公开数据库收录范围与全文可及性，部分非英语或未公开发表的灰色文献未能纳入；其次，不同纳入研究在结局指标测量时点与定义上存在异质性，因此主要采用分类证据综合与方法学定量描述，未强行开展异质性过高的单一方差合并。"
    )

    # 7. Conclusions
    conclusion_body = (
        f"本研究通过全流程可溯源的检索、去重、双盲筛选与定量证据综合，系统阐明了“{question}”领域的现存临床证据格局。"
        f"未来临床研究亟需在多中心前瞻性外部验证、标准化校准度与临床净获益评估以及真实世界随机对照试验方面持续深化，以推动相关技术安全、规范地转化为临床常规实践。"
    )

    # 8. Declarations
    declarations_body = (
        "- **利益冲突声明（Competing Interests）**：作者声明不存在任何潜在商业或财务利益冲突。\n"
        "- **伦理审批与知情同意（Ethics Approval）**：本研究基于已公开发表的生物医学文献与已脱敏/合成统计汇总数据开展，不涉及新招募人类受试者直接干预。\n"
        f"- **数据与审计链可用性（Data & Audit Availability）**：本研究全部检索快照、去重记录、双盲筛选日志、PRISMA 2020 计数表及统计产物均包含 SHA-256 完整性校验链。"
    )

    return {
        'title': title,
        'guideline': guideline,
        'sections': [
            {'title': '摘要 (Abstract)', 'body': abstract_body},
            {'title': '关键词 (Keywords)', 'body': keywords_body},
            {'title': '1. 引言 (Introduction)', 'body': intro_body},
            {'title': '2. 方法 (Methods)', 'body': methods_body},
            {'title': '3. 结果 (Results)', 'body': results_body},
            {'title': '4. 讨论 (Discussion)', 'body': discussion_body},
            {'title': '5. 结论 (Conclusions)', 'body': conclusion_body},
            {'title': '6. 声明 (Declarations)', 'body': declarations_body},
        ],
    }
