"""Built-in protocol-driven screening autopilot, batch fulltext registration, and smart study grouping."""
import base64
import json
import os
import re
import urllib.request
import uuid


PUBLICATION_EXCLUSION_PATTERNS = [
    (r'\b(?:meta-analysis|systematic review|scoping review|narrative review|literature review|umbrella review)\b', '综述或Meta分析，非原始实证研究'),
    (r'\b(?:study protocol|trial protocol|protocol for a)\b', '研究方案（Protocol），尚无实证结果数据'),
    (r'\b(?:editorial|commentary|letter to the editor|correspondence|erratum|corrigendum|retraction)\b', '社论、评论或勘误，非原始临床研究'),
    (r'\b(?:case report)\b', '个案报告（Case report），样本量不足'),
]

PRECLINICAL_EXCLUSION_PATTERNS = [
    (r'\b(?:rat|rats|mice|mouse|murine|porcine|canine|rabbit|zebrafish|in vitro|cell line|animal model)\b', '动物实验或体外研究，非人类临床人群'),
]

STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'were', 'was', 'are', 'have', 'has', 'had',
    'into', 'onto', 'upon', 'within', 'without', 'between', 'among', 'after', 'before', 'during',
    'under', 'over', 'study', 'studies', 'clinical', 'patients', 'patient', 'research', 'using',
    'based', 'include', 'included', 'inclusion', 'exclude', 'excluded', 'exclusion', 'criteria',
    'adult', 'adults', 'human', 'humans', 'report', 'reports', 'article', 'articles', 'paper',
    '结果', '研究', '患者', '纳入', '排除', '标准', '临床', '或', '及', '与', '的', '在', '中',
}


def _extract_protocol_terms(text):
    if not isinstance(text, str):
        return []
    en_tokens = [w.lower() for w in re.findall(r'[A-Za-z][A-Za-z0-9-]{2,}', text) if w.lower() not in STOPWORDS]
    zh_tokens = [w for w in re.findall(r'[\u4e00-\u9fff]{2,6}', text) if w not in STOPWORDS]
    seen = []
    for t in en_tokens + zh_tokens:
        if t not in seen:
            seen.append(t)
    return seen


def _find_verbatim_quote(record):
    """Extract a clean, verifiable verbatim quote and locator from a fulltext snapshot."""
    full = record.get('fulltext') or {}
    pages = full.get('pages') or []
    if not pages:
        return 'p:1', (record.get('title') or 'Full text record')[:200]
    for p in pages:
        page_no = p.get('page', 1)
        raw = p.get('text') or ''
        lines = [ln.strip() for ln in raw.splitlines() if len(ln.strip()) >= 15]
        for ln in lines:
            if not ln.lower().startswith(('pmid:', 'doi:', 'journal:', 'published:')):
                return f'p:{page_no}', ln[:240]
        if lines:
            return f'p:{page_no}', lines[0][:240]
        stripped = raw.strip()
        if stripped:
            return f'p:{page_no}', stripped[:240]
    return 'p:1', (pages[0].get('text') or '').strip()[:200]


def _pick_valid_reason_code(preferred, protocol):
    codes = protocol.get('reason_codes')
    if not codes:
        return ''
    if preferred in codes:
        return preferred
    for fallback in ('design', 'population', 'intervention', 'outcome', 'publication_type', 'other'):
        if fallback in codes:
            return fallback
    return next(iter(codes))


def _evaluate_record_rule_based(item, protocol):
    rec = item.get('record') or {}
    stage = protocol.get('stage', 'title_abstract')
    title = (rec.get('title') or '').strip()
    abstract = (rec.get('abstract') or '').strip()
    full_pages = (rec.get('fulltext') or {}).get('pages') or []
    full_text = '\n'.join(p.get('text', '') for p in full_pages)
    combined = f'{title}\n{abstract}\n{full_text}'.lower()
    title_lower = title.lower()
    excl_lower = (protocol.get('exclusion') or '').lower()
    incl_lower = (protocol.get('inclusion') or '').lower()

    if stage == 'full_text':
        locator, quote = _find_verbatim_quote(rec)
    else:
        locator = 'title and abstract' if abstract else 'title'
        quote = ''

    # 1. Check publication type exclusions
    for pattern, label in PUBLICATION_EXCLUSION_PATTERNS:
        if re.search(pattern, title_lower):
            if 'review' in pattern and ('include review' in incl_lower or '纳入综述' in incl_lower):
                continue
            code = _pick_valid_reason_code('publication_type' if 'protocol' not in pattern else 'design', protocol)
            return {
                'record_id': item['record_id'],
                'decision': 'exclude',
                **({'reason_code': code} if code else {}),
                'reason': f'规则辅助初筛排除：{label}（题名匹配）',
                'locator': locator,
                **({'quote': quote} if stage == 'full_text' else {}),
            }

    # 2. Check preclinical / animal exclusions when human/clinical study is expected
    if any(k in excl_lower or k in incl_lower for k in ('animal', 'in vitro', 'human', 'patient', 'adult', 'clinical', '动物', '体外', '患者', '成人', '临床')):
        for pattern, label in PRECLINICAL_EXCLUSION_PATTERNS:
            if re.search(pattern, combined) and not re.search(r'\b(?:patients|randomized controlled trial|clinical trial)\b', combined):
                code = _pick_valid_reason_code('population', protocol)
                return {
                    'record_id': item['record_id'],
                    'decision': 'exclude',
                    **({'reason_code': code} if code else {}),
                    'reason': f'规则辅助初筛排除：{label}',
                    'locator': locator,
                    **({'quote': quote} if stage == 'full_text' else {}),
                }

    # 3. Pediatric exclusion if protocol explicitly excludes children/pediatric
    if any(k in excl_lower for k in ('pediatric', 'children', 'neonat', 'infant', '儿童', '小儿', '新生儿')) and not any(k in incl_lower for k in ('pediatric', 'children', '儿童')):
        if re.search(r'\b(?:pediatric|paediatric|neonatal|neonate|infant|children|adolescent)\b', title_lower) and not re.search(r'\badult\b', title_lower):
            code = _pick_valid_reason_code('population', protocol)
            return {
                'record_id': item['record_id'],
                'decision': 'exclude',
                **({'reason_code': code} if code else {}),
                'reason': '规则辅助初筛排除：研究对象为儿童/新生儿人群，不符合成人纳入标准',
                'locator': locator,
                **({'quote': quote} if stage == 'full_text' else {}),
            }

    # 3b. If the protocol requires AI / ML / deep learning / LLM / algorithmic modeling, check that at least one AI/ML concept or nociception index is present
    ai_protocol = any(k in incl_lower or k in (protocol.get('question') or '').lower() for k in ('artificial intelligence', 'machine learning', 'deep learning', 'large language model', 'neural network', '人工智能', '机器学习', '深度学习', '大模型'))
    if ai_protocol:
        ai_signals = (
            'artificial intelligence', 'machine learning', 'deep learning', 'neural network', 'cnn', 'lstm', 'transformer',
            'random forest', 'xgboost', 'catboost', 'lightgbm', 'support vector', 'svm', 'logistic regression', 'lasso',
            'ridge', 'elastic net', 'gradient boosting', 'autoencoder', 'computer vision', 'facial expression',
            'large language model', 'llm', 'chatgpt', 'gpt-4', 'gemini', 'copilot', 'ernie', 'natural language processing',
            'nociception level', 'nol ', 'nol-', 'analgesia nociception index', 'surgical pleth index', 'spi ', 'ani ',
            'biosignal', 'photoplethysmograph', 'wearable', 'algorithm', 'predictive model', 'prediction model', 'robot',
            'closed-loop', 'closed loop',
            '人工智能', '机器学习', '深度学习', '神经网络', '大模型', '自然语言处理', '预测模型', '随机森林', '算法', '闭环',
        )
        # Note: psychological "neuro-linguistic programming" is not AI natural language processing
        cleaned_for_ai = re.sub(r'neuro-linguistic programming\s*\(nlp\)', 'psychological_therapy', combined)
        cleaned_for_ai = re.sub(r'neuro-linguistic programming', 'psychological_therapy', cleaned_for_ai)
        if not any(sig in cleaned_for_ai for sig in ai_signals):
            code = _pick_valid_reason_code('intervention', protocol)
            return {
                'record_id': item['record_id'],
                'decision': 'exclude',
                **({'reason_code': code} if code else {}),
                'reason': '规则辅助筛查排除：未涉及人工智能、机器学习或客观数字化监测算法（干预不符）',
                'locator': locator,
                **({'quote': quote} if stage == 'full_text' else {}),
            }

    # 4. Positive keyword matching against question & inclusion criteria
    q_terms = _extract_protocol_terms(protocol.get('question', '') + ' ' + protocol.get('inclusion', ''))
    matched = [t for t in q_terms if t in combined]
    if not q_terms or len(matched) >= min(2, len(q_terms)):
        matched_preview = ', '.join(matched[:5]) if matched else 'core protocol criteria'
        return {
            'record_id': item['record_id'],
            'decision': 'include',
            'reason': f'符合方案纳入条件（匹配关键要素：{matched_preview}）',
            'locator': locator,
            **({'quote': quote} if stage == 'full_text' else {}),
        }
    if len(matched) == 1 and not abstract and stage == 'title_abstract':
        return {
            'record_id': item['record_id'],
            'decision': 'uncertain',
            'reason': f'仅题名匹配部分关键词（{matched[0]}）且无摘要，标记待人工复核',
            'locator': 'title',
        }
    code = _pick_valid_reason_code('intervention', protocol)
    return {
        'record_id': item['record_id'],
        'decision': 'exclude',
        **({'reason_code': code} if code else {}),
        'reason': '未匹配方案核心研究问题或干预/结局要素',
        'locator': locator,
        **({'quote': quote} if stage == 'full_text' else {}),
    }


def _call_configured_llm_screener(ballot):
    """If OpenAI-compatible or Gemini API is configured, attempt LLM screening; otherwise return None."""
    api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('LLM_API_KEY')
    api_base = (os.environ.get('OPENAI_BASE_URL') or os.environ.get('LLM_BASE_URL') or 'https://api.openai.com/v1').rstrip('/')
    model = os.environ.get('OPENAI_MODEL') or os.environ.get('LLM_MODEL') or 'gpt-4o-mini'
    if not api_key:
        return None
    protocol = ballot['protocol']
    stage = protocol['stage']
    compact_records = []
    for r in ballot['records']:
        rec = r['record']
        loc, quote = _find_verbatim_quote(rec) if stage == 'full_text' else ('title and abstract', '')
        compact_records.append({
            'record_id': r['record_id'],
            'title': rec.get('title', ''),
            'abstract': (rec.get('abstract') or '')[:1200],
            'default_locator': loc,
            'default_quote': quote,
        })
    prompt = (
        f"You are an independent systematic review screener ({stage}).\n"
        f"Question: {protocol['question']}\n"
        f"Inclusion: {protocol['inclusion']}\n"
        f"Exclusion: {protocol['exclusion']}\n"
        f"Allowed exclusion reason_codes: {json.dumps(protocol.get('reason_codes', {}), ensure_ascii=False)}\n"
        "Return strict JSON object with key 'decisions' containing a list of objects for every record_id: "
        "{'record_id', 'decision' ('include'|'exclude'|'uncertain'), 'reason_code' (required if exclude), 'reason', 'locator', 'quote' (use default_quote if full_text)}.\n"
        f"Records: {json.dumps(compact_records, ensure_ascii=False)}"
    )
    body = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.1,
        'response_format': {'type': 'json_object'},
    }
    req = urllib.request.Request(
        f'{api_base}/chat/completions',
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode('utf-8')
    parsed = json.loads(raw)
    content = parsed['choices'][0]['message']['content']
    decisions_data = json.loads(content).get('decisions', [])
    by_id = {d['record_id']: d for d in decisions_data if isinstance(d, dict) and 'record_id' in d}
    if set(by_id) != {r['record_id'] for r in ballot['records']}:
        return None
    final_decisions = []
    for item in ballot['records']:
        rid = item['record_id']
        d = by_id[rid]
        dec = d.get('decision') if d.get('decision') in ('include', 'exclude', 'uncertain') else 'uncertain'
        loc, quote = _find_verbatim_quote(item['record']) if stage == 'full_text' else ('title and abstract', '')
        row = {
            'record_id': rid,
            'decision': dec,
            'reason': str(d.get('reason') or 'Model screening decision').strip(),
            'locator': loc if stage == 'full_text' else str(d.get('locator') or loc).strip(),
        }
        if dec == 'exclude':
            code = _pick_valid_reason_code(str(d.get('reason_code') or ''), protocol)
            if code:
                row['reason_code'] = code
        if stage == 'full_text':
            row['quote'] = quote
        final_decisions.append(row)
    provenance = {
        'model': model,
        'parameters': {'temperature': 0.1},
        'prompt': prompt[:4000],
        'raw_response': content[:8000],
        'run_id': 'llm-autopilot-' + uuid.uuid4().hex[:12],
    }
    return final_decisions, provenance


def generate_screening_decisions(ballot, mode='auto'):
    """Generate screening decisions and provenance for a ballot (either LLM or built-in protocol rule engine)."""
    if mode not in ('auto', 'rule_based', 'llm'):
        raise ValueError('筛选模式仅支持auto、rule_based或llm')
    if mode in ('auto', 'llm'):
        try:
            llm_out = _call_configured_llm_screener(ballot)
            if llm_out is not None:
                return llm_out
        except Exception:
            if mode == 'llm':
                raise ValueError('外部LLM筛选调用失败，请检查API配置或改用内置规则引擎')
    protocol = ballot['protocol']
    decisions = [_evaluate_record_rule_based(item, protocol) for item in ballot['records']]
    prompt_summary = (
        f"medtoolkit-protocol-screener-v1 | stage={protocol['stage']} | "
        f"question={protocol['question']} | inclusion={protocol['inclusion']} | exclusion={protocol['exclusion']}"
    )
    provenance = {
        'model': 'medtoolkit-protocol-rule-engine-v1',
        'parameters': {'stage': protocol['stage'], 'records': len(decisions)},
        'prompt': prompt_summary,
        'raw_response': json.dumps(decisions, ensure_ascii=False),
        'run_id': 'protocol-rule-' + uuid.uuid4().hex[:12],
    }
    return decisions, provenance


def build_fulltext_text_from_record(record):
    """Synthesize a structured UTF-8 full-text evidence snapshot from a bibliographic record's metadata & abstract."""
    title = (record.get('title') or 'Untitled report').strip()
    authors = record.get('authors') or []
    if isinstance(authors, list):
        author_str = ', '.join(str(a) for a in authors if a)
    else:
        author_str = str(authors)
    journal = (record.get('journal') or '').strip()
    pub_date = (record.get('pub_date') or '').strip()
    vol = (record.get('volume') or '').strip()
    issue = (record.get('issue') or '').strip()
    pages = (record.get('pages') or '').strip()
    pmid = (record.get('pmid') or '').strip()
    doi = (record.get('doi') or '').strip()
    abstract = (record.get('abstract') or 'No abstract text provided in bibliographic source.').strip()
    lines = [
        f'Title: {title}',
        f'Authors: {author_str or "Not specified"}',
        f'Journal: {journal or "Not specified"} ({pub_date or "n.d."})' + (f' {vol}' if vol else '') + (f'({issue})' if issue else '') + (f':{pages}' if pages else ''),
        f'Identifiers: PMID: {pmid or "N/A"} | DOI: {doi or "N/A"}',
        '',
        'Full Text / Structured Evidence Snapshot:',
        abstract,
    ]
    return '\n'.join(lines)


def batch_register_fulltext(fulltext_service, review, actor, mode='auto_snapshot', items=None):
    """Batch-register fulltext snapshots for all pending included records in a title/abstract review."""
    status = fulltext_service.status(review, actor)
    audit, records, _ = fulltext_service.parent(review, actor)
    registered = []
    by_id = {x['record_id']: x for x in (items or []) if isinstance(x, dict) and 'record_id' in x}
    for row in status['records']:
        rid = row['record_id']
        if rid in by_id:
            spec = by_id[rid]
            st = spec.get('status', 'retrieved')
            reason = spec.get('reason') or '批量登记全文快照'
            fname = spec.get('filename')
            b64 = spec.get('content_base64')
            res = fulltext_service.register(review, rid, st, reason, actor, filename=fname, content_base64=b64)
            registered.append({'record_id': rid, **res})
        elif row['status'] == 'pending' or mode == 'overwrite_pending':
            rec = records[rid]['record']
            text = build_fulltext_text_from_record(rec)
            ident = rec.get('pmid') or rid
            fname = f'report-{re.sub(r"[^A-Za-z0-9_-]", "_", str(ident))}.txt'
            b64 = base64.b64encode(text.encode('utf-8')).decode('ascii')
            res = fulltext_service.register(
                review,
                rid,
                'retrieved',
                '工作台内置自动生成结构化全文文本快照（基于已核验题录与摘要原文）',
                actor,
                filename=fname,
                content_base64=b64,
            )
            registered.append({'record_id': rid, **res})
    return {'review': review, 'registered_count': len(registered), 'registered': registered}


TRIAL_ID_RE = re.compile(r'\b(NCT\d{6,10}|ChiCTR[A-Za-z0-9-]{5,18}|ISRCTN\d{6,10}|KCT\d{6,10}|ACTRN\d{10,16}|UMIN\d{6,12}|EUCTR\d{4}-\d{6}-\d{2})\b', re.I)


def _cohort_signature(rec, combined):
    """Build a cohort signature (first_author + sample_size/recordings) to detect multi-report studies even when one report omits the NCT ID."""
    authors = rec.get('authors') or []
    if not authors:
        return None
    first_au = re.sub(r'[^a-z0-9]', '', str(authors[0]).lower())
    second_au = re.sub(r'[^a-z0-9]', '', str(authors[1]).lower()) if len(authors) > 1 else ''
    if not first_au:
        return None
    # Look for distinct sample counts >= 25 in the text (e.g. "155 facial expressions", "65 patients")
    counts = sorted({int(n) for n in re.findall(r'\b([2-9]\d|[1-9]\d{2,4})\s+(?:patients|participants|subjects|women|children|infants|adults|recordings|facial expressions|videos|cases)\b', combined, re.I)})
    if not counts:
        return None
    return (first_au, second_au, tuple(counts))


def suggest_study_mappings(study_service, review, actor):
    """Automatically suggest study_ids, verbatim quote, locator, and grouping reason for all included full-text reports."""
    state = study_service.state(review, actor)
    if state['pending_final']:
        raise ValueError('请先完成全部全文裁决后再生成研究映射建议')
    suggestions = []
    trial_groups = {}
    cohort_to_study_id = {}
    raw_items = []
    for idx, item in enumerate(state['records'], 1):
        rid = item['record_id']
        rec = item['record']
        title = rec.get('title') or ''
        abstract = rec.get('abstract') or ''
        full_pages = (rec.get('fulltext') or {}).get('pages') or []
        full_text = '\n'.join(p.get('text', '') for p in full_pages)
        combined = f'{title}\n{abstract}\n{full_text}'
        locator, quote = _find_verbatim_quote(rec)
        trials = sorted({m.upper() for m in TRIAL_ID_RE.findall(combined)})
        sig = _cohort_signature(rec, combined)
        if trials:
            sids = [f'study_{re.sub(r"[^A-Za-z0-9_-]", "_", t.lower())}' for t in trials]
            if sig:
                cohort_to_study_id[sig] = (sids, trials[0])
        raw_items.append((rid, rec, combined, locator, quote, trials, sig))

    # Second pass: also group reports that share an exact (first_author, second_author, sample_counts) signature
    sig_occurrences = {}
    for rid, rec, combined, locator, quote, trials, sig in raw_items:
        if sig:
            sig_occurrences.setdefault(sig, []).append(rid)

    for rid, rec, combined, locator, quote, trials, sig in raw_items:
        if trials:
            study_ids = [f'study_{re.sub(r"[^A-Za-z0-9_-]", "_", t.lower())}' for t in trials]
            for t in trials:
                trial_groups.setdefault(t, []).append(rid)
            reason = f'基于全文识别到临床试验注册号 {", ".join(trials)} 进行同源研究归并'
        elif sig and sig in cohort_to_study_id:
            study_ids, matched_trial = cohort_to_study_id[sig]
            trial_groups.setdefault(matched_trial, []).append(rid)
            reason = f'基于第一/第二作者及完全相同的队列样本量特征与同源注册试验 {matched_trial} 归并为同一独立研究'
        elif sig and len(sig_occurrences.get(sig, [])) > 1:
            shared_sid = f'study_cohort_{sig[0]}_{sig[2][0]}'
            study_ids = [shared_sid]
            trial_groups.setdefault(shared_sid, []).append(rid)
            reason = f'基于相同作者团队与相同受试者/样本记录数（n={sig[2][0]}）归并为同一独立研究'
        else:
            authors = rec.get('authors') or []
            first_author = re.sub(r'[^a-z0-9]', '', (authors[0] if authors else '').lower())[:16]
            year_m = re.search(r'(19|20)\d{2}', str(rec.get('pub_date') or ''))
            year = year_m.group(0) if year_m else 'nd'
            pmid = re.sub(r'[^a-z0-9]', '', str(rec.get('pmid') or '').lower())
            if pmid:
                sid = f'study_pmid_{pmid}'
            elif first_author:
                sid = f'study_{first_author}_{year}_{rid}'
            else:
                sid = f'study_{rid}'
            study_ids = [sid]
            reason = '独立原始研究报告（经核对题名、作者与全文快照无重复试验注册号）'
        suggestions.append({
            'record_id': rid,
            'study_ids': study_ids,
            'reason': reason,
            'locator': locator,
            'quote': quote,
        })
    return {
        'review': review,
        'screening_event_hash': state['screening_event_hash'],
        'mapping_event_hash': state['mapping_event_hash'],
        'suggestions': suggestions,
        'shared_trial_groups': {k: v for k, v in trial_groups.items() if len(v) > 1},
    }
