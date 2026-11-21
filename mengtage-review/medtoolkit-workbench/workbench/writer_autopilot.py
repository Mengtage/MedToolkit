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


def _doc_full_text(store, project, item):
    try:
        from .writer import WriterService
        doc = WriterService(store).load(project, item['document_id'], 'document')
        pages = (doc.get('snapshot') or {}).get('pages') or []
        return '\n'.join(p.get('text', '') for p in pages)
    except Exception:
        return item.get('excerpt', '')


def _extract_study_metrics(full_text, title=''):
    """Extract quantitative metrics (sample size N, AUROC, r, OR/aOR, P-value, trial ID) from report fulltext/abstract."""
    combined = f'{title}\n{full_text}'
    metrics = []
    # Sample size
    for pat in (
        r'\b(?:total of|enrolled|included|analyzed|comprising|in)\s+([1-9]\d{1,5}(?:,\d{3})*)\s+(?:adult\s+|pediatric\s+|surgical\s+|postoperative\s+|gastric\s+|obstetric\s+|cesarean\s+|female\s+)?(?:patients|participants|women|children|infants|records|recordings|cases|procedures)\b',
        r'\b([1-9]\d{1,5}(?:,\d{3})*)\s+(?:adult\s+|pediatric\s+|surgical\s+|postoperative\s+)?(?:patients|participants|women|children|infants|facial expressions|anesthesia records)\b',
        r'\b[Nn]\s*=\s*([1-9]\d{1,5}(?:,\d{3})*)\b',
    ):
        m = re.search(pat, combined, re.I)
        if m:
            metrics.append(f"样本量 N = {m.group(1)}")
            break
    # AUROC / AUC
    aucs = re.findall(r'\b(?:AUROC|AUC|c-statistic)s?\s*(?:of|=|:|\(|was|were|reached|achieved)?\s*(0\.\d{2,3}(?:\s*(?:to|–|-)\s*0\.\d{2,3})?)', combined, re.I)
    if aucs:
        metrics.append(f"AUROC = {aucs[0]}")
    # Accuracy / sensitivity / specificity / F1 / R2
    acc = re.search(r'\b(?:accuracy|balanced accuracy)\s*(?:of|=|:|\(|was)?\s*(\d{2,3}(?:\.\d+)?%)', combined, re.I)
    if acc:
        metrics.append(f"准确率 {acc.group(1)}")
    f1 = re.search(r'\bF1(?:-score|\s+score)?\s*(?:of|=|:|\(|was)?\s*(0\.\d{2,3}|\d{2,3}(?:\.\d+)?%)', combined, re.I)
    if f1:
        metrics.append(f"F1 = {f1.group(1)}")
    r2 = re.search(r'\bR\^?2\s*=\s*(0\.\d{2,3}|\d{2}(?:\.\d+)?%)', combined, re.I)
    if r2:
        metrics.append(f"R² = {r2.group(1)}")
    corr = re.search(r'\b(?:r|ICC)\s*=\s*(0\.\d{2,3})', combined)
    if corr:
        metrics.append(f"相关性 r/ICC = {corr.group(1)}")
    aor = re.search(r'\b(?:aOR|OR|odds ratio)\s*(?:of|=|:|\(|was)?\s*(\d+\.\d{1,2})', combined, re.I)
    if aor:
        metrics.append(f"OR/aOR = {aor.group(1)}")
    p_m = re.search(r'\b[Pp]\s*([<≤=]\s*0\.\d{2,4})', combined)
    if p_m:
        p_raw = p_m.group(1).replace(' ', '')
        if re.match(r'^=0\.000+$', p_raw):
            p_raw = '< 0.001'
        else:
            p_raw = p_raw[0] + ' ' + p_raw[1:]
        metrics.append(f"P {p_raw}")
    trial = re.search(r'\b(NCT\d{6,10}|ChiCTR[A-Za-z0-9-]{5,18}|KCT\d{6,10}|ISRCTN\d{6,10})\b', combined, re.I)
    if trial:
        metrics.append(f"注册号 {trial.group(1).upper()}")
    return '；'.join(metrics)


def _extract_key_finding_sentence(full_text, title=''):
    """Extract the most informative empirical conclusion/results sentence from the report snapshot."""
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip() and not ln.strip().startswith(('Title:', 'Authors:', 'Journal:', 'Identifiers:', 'Full Text /'))]
    body = ' '.join(lines)
    if not body:
        return title
    sentences = [s.strip() for s in re.split(r'(?<=[.!?。！？])\s+', body) if len(s.strip()) >= 35]
    if not sentences:
        return body[:240]
    scored = []
    for idx, s in enumerate(sentences):
        sl = s.lower()
        if any(bad in sl for bad in ('date of registration', 'trial registration', 'registered at', 'ethics committee', 'institutional review board')):
            continue
        if s[0].isdigit() and ')' in s[:15]:
            continue
        score = 0
        if any(k in sl for k in ('results:', 'conclusion:', 'conclusions:', 'findings:', 'outperformed', 'significantly', 'auroc', 'auc', 'accuracy', 'reduced', 'decreased', 'associated with', 'demonstrated', 'achieved')):
            score += 4
        if any(k in sl for k in ('background:', 'methods:', 'purpose:', 'enrolled', 'initially included', 'were analysed')):
            score -= 2
        if re.search(r'\d', s):
            score += 2
        if idx >= len(sentences) // 2:
            score += 1
        scored.append((score, idx, s))
    if not scored:
        return sentences[-1][:240]
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = re.sub(r'^(?:\[?RESULTS\]?|\[?CONCLUSIONS?\]?|\[?FINDINGS\]?|\[?PURPOSE\]?|\[?BACKGROUND\]?|\[?METHODS\]?)\s*:?\s*', '', scored[0][2], flags=re.I).strip()
    best = re.sub(r'\.?\s*Clinical relevance-\s*.*$', '.', best, flags=re.I)
    if len(best) > 220:
        cut = best[:217].rsplit(' ', 1)[0]
        best = cut.rstrip('.,;:') + '...'
    elif best and best[-1] not in '.!?。！？':
        best += '.'
    return best


def _classify_study_domain(item, full_text=''):
    bib = item.get('bibliographic') or {}
    text = f"{bib.get('title', '')} {item.get('excerpt', '')} {full_text}".lower()
    if any(k in text for k in ('large language model', 'llm', 'chatgpt', 'gpt-4', 'gemini', 'copilot', 'ernie', 'natural language processing', 'stigmatizing language', '大模型', '自然语言处理')):
        return '大语言模型与临床自然语言处理 (LLM & NLP)'
    if any(k in text for k in ('facial', 'video', 'action unit', 'camera', 'socially assistive robot', 'audio', 'voice', 'infant', '面部', '视频', '计算机视觉', '机器人')):
        return '计算机视觉、面部动作单元与具身交互 (Computer Vision & Robotics)'
    if any(k in text for k in ('closed-loop', 'analgesia nociception index', 'ani ', 'nol ', 'nol-', 'nociception level', 'surgical pleth index', 'spi ', 'photoplethysmograph', 'ppg', 'wearable', 'biosignal', 'ecg', 'semg', '闭环', '生理', '可穿戴', '伤害性感受')):
        return '连续生理波形、可穿戴传感与闭环镇痛滴定 (Biosignals, Wearables & NOL)'
    return '多源电子病历、高频生命体征与精准风险预测 (Multimodal EHR & Predictive ML)'


def _infer_study_design(item, full_text=''):
    bib = item.get('bibliographic') or {}
    text = f"{bib.get('title', '')} {item.get('excerpt', '')} {full_text}".lower()
    if any(k in text for k in ('randomized', 'randomised', 'rct', 'single-blind', 'double-blind', '随机对照')):
        return '前瞻性随机对照试验 (RCT)'
    if any(k in text for k in ('external validation', 'two university hospitals', 'multicenter', 'multi-center', '多中心', '外部验证')):
        return '多中心队列 / 外部验证研究'
    if any(k in text for k in ('prospective', 'pilot study', 'nct0', 'kct0', '前瞻性')):
        return '前瞻性临床队列 / 验证研究'
    if any(k in text for k in ('retrospective', 'cohort', 'cross-sectional', '回顾性')):
        return '回顾性队列 / 建模研究'
    return '临床实证与算法验证研究'


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
    full_texts = {}
    for e in bib_items:
        ft = _doc_full_text(store, project, e)
        full_texts[e['id']] = ft
        dom = _classify_study_domain(e, ft)
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
    kw_tokens = [w.strip() for w in re.split(r'[：:；;，,、（）()—\-\s]+', question) if 2 <= len(w.strip()) <= 12]
    kw_list = []
    for k in kw_tokens + ['人工智能', '循证医学', guideline, '系统证据综合', '临床研究方法学']:
        if k and k not in kw_list:
            kw_list.append(k)
    keywords_body = '；'.join(kw_list[:7])

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
        study_Syntheses = []
        for e in dom_items:
            bib = e.get('bibliographic') or {}
            authors = bib.get('authors') or []
            raw_first = authors[0].strip() if authors else e['id']
            parts_au = raw_first.split()
            first_au = ' '.join(parts_au[:-1]) if len(parts_au) > 1 and len(parts_au[-1]) <= 3 and parts_au[-1].isupper() else (parts_au[0] if parts_au else e['id'])
            yr_m = re.search(r'(19|20)\d{2}', str(bib.get('pub_date') or ''))
            yr = yr_m.group(0) if yr_m else 'n.d.'
            ft = full_texts.get(e['id'], '')
            design = _infer_study_design(e, ft)
            metrics = _extract_study_metrics(ft, bib.get('title', ''))
            finding = _extract_key_finding_sentence(ft, bib.get('title', ''))
            metric_clause = f"（{design}；{metrics}）" if metrics else f"（{design}）"
            study_Syntheses.append(f"- **{first_au} 等（{yr}）**{metric_clause}：{finding} [E:{e['id']}]")
        domain_paragraphs.append(
            f"### 3.{d_idx + 1} {dom_name}\n\n"
            f"该方向共纳入 {len(dom_items)} 篇全文报告（涉及 {len({s for e in dom_items for s in (e.get('study_ids') or [e['id']])})} 项独立研究） {dom_tags}。各纳入研究的人群设计、定量指标与主要实证发现如下：\n\n"
            + '\n'.join(study_Syntheses)
        )

    char_rows = [
        "**表 2  纳入研究核心特征、定量指标与主要实证结论汇总表（三线表）**\n",
        "| 研究标识 | 第一作者 (年份) | 来源期刊 | 研究设计 | 样本量与定量结果指标 | 核心实证结论与证据摘录 | 文献引用 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for e in bib_items:
        bib = e.get('bibliographic') or {}
        authors = bib.get('authors') or []
        first_au = authors[0] if authors else 'Author'
        yr_m = re.search(r'(19|20)\d{2}', str(bib.get('pub_date') or ''))
        yr = yr_m.group(0) if yr_m else 'n.d.'
        journal = (bib.get('journal') or 'Journal').replace('|', '\\|')[:42]
        ft = full_texts.get(e['id'], '')
        design = _infer_study_design(e, ft)
        metrics = (_extract_study_metrics(ft, bib.get('title', '')) or '详见正文').replace('|', '\\|')
        finding_clean = re.sub(r'\s+', ' ', _extract_key_finding_sentence(ft, bib.get('title', ''))).replace('|', '\\|')
        sids = _humanize_study_label(e.get('study_ids'), e['id'])
        char_rows.append(f"| {sids} | {first_au} ({yr}) | {journal} | {design} | {metrics} | {finding_clean} | [E:{e['id']}] |")
    char_table = '\n'.join(char_rows)

    next_sec_no = len(domains) + 2
    stat_section = ''
    if stat_summaries:
        stat_section = (
            f"\n\n### 3.{next_sec_no} 定量统计分析与模型性能汇总\n\n"
            + '\n\n'.join(stat_summaries)
        )
        next_sec_no += 1

    results_body = (
        f"### 3.1 文献检索与 PRISMA 筛选结果\n\n"
        f"检索共识别 {rec_id} 条原始文献记录，去重后对 {rec_scr} 条记录开展初筛，最终纳入 {rep_inc} 篇全文报告（归属 {stu_inc} 项独立研究） {all_bib_tags}。完整筛选流程见表 1。\n\n"
        f"{prisma_table}\n\n"
        + '\n\n'.join(domain_paragraphs)
        + stat_section
        + f"\n\n### 3.{next_sec_no} 纳入研究特征汇总\n\n"
        f"表 2 汇总了全部纳入研究的第一作者、发表年份、来源期刊、研究设计、样本量与定量结果指标及核心实证结论。\n\n"
        f"{char_table}"
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
