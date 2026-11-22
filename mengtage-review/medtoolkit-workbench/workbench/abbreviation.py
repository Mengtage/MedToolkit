"""Dual-scope (Abstract + Main Body) medical, AI, and statistical abbreviation normalizer and validator."""
import re


# Order matters when matching: longer / hyphenated abbreviations first (e.g. PRISMA-ScR before PRISMA, AUC-PRC before AUC)
ABBREVIATION_REGISTRY = [
    ('PRISMA-ScR', '系统综述与Meta分析优先报告条目范围综述扩展版', 'Preferred Reporting Items for Systematic Reviews and Meta-Analyses Extension for Scoping Reviews'),
    ('TRIPOD+AI', '个体预后或诊断多变量预测模型透明报告人工智能扩展指南', 'Transparent Reporting of a Multivariable Prediction Model for Individual Prognosis or Diagnosis-Artificial Intelligence'),
    ('PRISMA', '系统综述与Meta分析优先报告条目', 'Preferred Reporting Items for Systematic Reviews and Meta-Analyses'),
    ('CONSORT', '临床试验报告统一标准', 'Consolidated Standards of Reporting Trials'),
    ('STROBE', '观察性流行病学研究报告规范', 'Strengthening the Reporting of Observational Studies in Epidemiology'),
    ('AUC-PRC', '精确率-召回率曲线下面积', 'Area Under the Precision-Recall Curve'),
    ('AUPRC', '精确率-召回率曲线下面积', 'Area Under the Precision-Recall Curve'),
    ('AUROC', '受试者工作特征曲线下面积', 'Area Under the Receiver Operating Characteristic Curve'),
    ('XGBoost', '极端梯度提升', 'eXtreme Gradient Boosting'),
    ('IV-PCA', '静脉患者自控镇痛', 'Intravenous Patient-Controlled Analgesia'),
    ('FLACC', '面部、腿部、活动、哭闹与可安慰性量表', 'Face, Legs, Activity, Cry, and Consolability'),
    ('LASSO', '最小绝对收缩和选择算子', 'Least Absolute Shrinkage and Selection Operator'),
    ('UVATS', '单孔电视辅助胸腔镜手术', 'Uniportal Video-Assisted Thoracoscopic Surgery'),
    ('VATS', '电视辅助胸腔镜手术', 'Video-Assisted Thoracoscopic Surgery'),
    ('ESPB', '竖脊肌平面阻滞', 'Erector Spinae Plane Block'),
    ('EOIP', '腹外斜肌肋间平面阻滞', 'External Oblique Intercostal Plane'),
    ('TAPP', '经腹腹膜前腹腔镜腹股沟疝修补术', 'Transabdominal Preperitoneal'),
    ('CPSP', '慢性术后疼痛', 'Chronic Postsurgical Pain'),
    ('MCID', '最小临床重要差异', 'Minimal Clinically Important Difference'),
    ('PACU', '麻醉后监测治疗室', 'Post-Anesthesia Care Unit'),
    ('NICU', '新生儿重症监护室', 'Neonatal Intensive Care Unit'),
    ('ERAS', '加速康复外科', 'Enhanced Recovery After Surgery'),
    ('PCIA', '患者自控静脉镇痛', 'Patient-Controlled Intravenous Analgesia'),
    ('VNPS', '口头数字疼痛评分', 'Verbal Numerical Pain Score'),
    ('STAI', '状态-特质焦虑量表', 'State-Trait Anxiety Inventory'),
    ('FKGL', '弗莱什-金凯德年级可读性指数', 'Flesch-Kincaid Grade Level'),
    ('LSTM', '长短期记忆网络', 'Long Short-Term Memory'),
    ('SHAP', '沙普利加性解释', 'SHapley Additive exPlanations'),
    ('sEMG', '表面肌电图', 'Surface Electromyography'),
    ('LLM', '大语言模型', 'Large Language Model'),
    ('NLP', '自然语言处理', 'Natural Language Processing'),
    ('XAI', '可解释人工智能', 'Explainable Artificial Intelligence'),
    ('CNN', '卷积神经网络', 'Convolutional Neural Network'),
    ('GAT', '图注意力网络', 'Graph Attention Network'),
    ('GTN', '图Transformer网络', 'Graph Transformer Network'),
    ('SVM', '支持向量机', 'Support Vector Machine'),
    ('AUC', '曲线下面积', 'Area Under the Curve'),
    ('ROC', '受试者工作特征曲线', 'Receiver Operating Characteristic'),
    ('PPV', '阳性预测值', 'Positive Predictive Value'),
    ('NPV', '阴性预测值', 'Negative Predictive Value'),
    ('DCA', '决策曲线分析', 'Decision Curve Analysis'),
    ('NRI', '净重新分类指数', 'Net Reclassification Improvement'),
    ('IDI', '综合判别改善指数', 'Integrated Discrimination Improvement'),
    ('ICC', '组内相关系数', 'Intraclass Correlation Coefficient'),
    ('RCT', '随机对照试验', 'Randomized Controlled Trial'),
    ('aOR', '校正比值比', 'Adjusted Odds Ratio'),
    ('IQR', '四分位数间距', 'Interquartile Range'),
    ('NRS', '数字评定量表', 'Numerical Rating Scale'),
    ('VAS', '视觉模拟量表', 'Visual Analog Scale'),
    ('ICU', '重症监护室', 'Intensive Care Unit'),
    ('PCA', '患者自控镇痛', 'Patient-Controlled Analgesia'),
    ('MMA', '多模式镇痛', 'Multimodal Analgesia'),
    ('OFA', '无阿片类药物麻醉', 'Opioid-Free Anesthesia'),
    ('NOL', '伤害性感受水平指数', 'Nociception Level Index'),
    ('SPI', '外科容积脉搏波指数', 'Surgical Pleth Index'),
    ('ANI', '镇痛伤害性感受指数', 'Analgesia Nociception Index'),
    ('PPI', '瞳孔疼痛指数', 'Pupillary Pain Index'),
    ('BIS', '脑电双频指数', 'Bispectral Index'),
    ('PPG', '光电容积脉搏波描记法', 'Photoplethysmography'),
    ('ECG', '心电图', 'Electrocardiography'),
    ('EMG', '肌电图', 'Electromyography'),
    ('EDA', '皮肤电活动', 'Electrodermal Activity'),
    ('HRV', '心率变异性', 'Heart Rate Variability'),
    ('EHR', '电子健康病历', 'Electronic Health Record'),
    ('SAR', '社交辅助机器人', 'Socially Assistive Robot'),
    ('TKA', '全膝关节置换术', 'Total Knee Arthroplasty'),
    ('PVB', '椎旁神经阻滞', 'Paravertebral Block'),
    ('TTP', '胸横肌平面', 'Transverse Thoracic Plane'),
    ('ASA', '美国麻醉医师协会', 'American Society of Anesthesiologists'),
    ('SNP', '单核苷酸多态性', 'Single Nucleotide Polymorphism'),
    ('IoU', '交并比', 'Intersection over Union'),
    ('AI', '人工智能', 'Artificial Intelligence'),
    ('ML', '机器学习', 'Machine Learning'),
    ('DL', '深度学习', 'Deep Learning'),
    ('CV', '计算机视觉', 'Computer Vision'),
    ('RF', '随机森林', 'Random Forest'),
    ('OR', '比值比', 'Odds Ratio'),
    ('CI', '置信区间', 'Confidence Interval'),
    ('SD', '标准差', 'Standard Deviation'),
    ('SE', '标准误', 'Standard Error'),
    ('MD', '均值差', 'Mean Difference'),
    ('AU', '面部动作单元', 'Facial Action Unit'),
    ('LC', '腹腔镜胆囊切除术', 'Laparoscopic Cholecystectomy'),
]

ABBREVIATION_MAP = {abbr: (zh, en) for abbr, zh, en in ABBREVIATION_REGISTRY}

# Core abbreviations enforced by Gate 4 when appearing in Chinese academic prose
ENFORCED_ABBREVIATIONS = {
    'PRISMA-ScR', 'TRIPOD+AI', 'CONSORT', 'STROBE',
    'LLM', 'NLP', 'ML', 'DL', 'XAI', 'CNN', 'LSTM', 'XGBoost',
    'AUROC', 'AUC-PRC', 'AUPRC', 'PPV', 'NPV', 'DCA', 'NRI', 'IDI', 'ICC',
    'RCT', 'aOR', 'IQR', 'MCID',
    'NRS', 'VAS', 'VNPS', 'FLACC', 'STAI', 'FKGL',
    'PACU', 'ICU', 'NICU', 'ERAS', 'PCA', 'IV-PCA', 'PCIA', 'MMA', 'OFA',
    'NOL', 'SPI', 'ANI', 'PPI', 'BIS', 'PPG', 'ECG', 'EMG', 'sEMG', 'EDA', 'HRV', 'EHR',
    'SAR', 'VATS', 'UVATS', 'TKA', 'PVB', 'ESPB', 'EOIP', 'CPSP',
}


def _compile_abbr_pattern(abbr):
    escaped = re.escape(abbr)
    # Match standalone token (allow plural 's' like LLMs or AUs only when Checking, not breaking identifiers)
    return re.compile(r'(?<![A-Za-z0-9_/-])' + escaped + r'(?![A-Za-z0-9_/-])')


ABBR_PATTERNS = [(abbr, zh, en, _compile_abbr_pattern(abbr)) for abbr, zh, en in ABBREVIATION_REGISTRY]


def is_defined_near(text, match_start, match_end, abbr, zh, en):
    """Check whether an abbreviation occurrence at [match_start, match_end] already has a full-name definition nearby."""
    left_window = text[max(0, match_start - 220):match_start]
    right_window = text[match_end:min(len(text), match_end + 220)]
    around = left_window + text[match_start:match_end] + right_window
    if zh and zh in around:
        return True
    if en and en.lower() in around.lower():
        return True
    # Also accept any parenthetical definition immediately preceding or following: e.g., 中文名称（..., ABBR） or ABBR（中文名称）
    if re.search(r'[（(][^）)\n]{2,180}(?<![A-Za-z0-9])' + re.escape(abbr) + r's?(?![A-Za-z0-9])[^）)\n]*[）)]', around):
        return True
    if re.match(r'^\s*[（(][^）)\n]{2,180}[）)]', right_window):
        return True
    if re.search(r'[\u4e00-\u9fff]{2,30}\s*[（(]\s*$', left_window) and re.match(r'^\s*[）)]', right_window):
        return True
    return False


def _normalize_line_in_scope(line, defined_set):
    stripped = line.strip()
    if not stripped:
        return line
    # Do not expand inside Markdown table divider rows or figure blocks
    if stripped.startswith('|') and re.fullmatch(r'[\s|:-]+', stripped):
        return line
    if stripped.startswith(':::') or stripped.startswith('```'):
        return line
    # Skip heading lines so section headers stay concise
    if stripped.startswith('#'):
        return line

    # Temporarily mask [E:...] tags so we never touch evidence IDs
    placeholders = []
    def _mask(m):
        placeholders.append(m.group(0))
        return f'\x00EID{len(placeholders)-1}\x00'

    working = re.sub(r'\[E:[A-Za-z0-9_-]{1,40}\]', _mask, line)

    for abbr, zh, en, pat in ABBR_PATTERNS:
        m = pat.search(working)
        if not m:
            continue
        if abbr in defined_set:
            continue
        start, end = m.start(), m.end()
        if is_defined_near(working, start, end, abbr, zh, en):
            defined_set.add(abbr)
            continue
        # Check if inside parentheses like (LLM & NLP) or （LLM）
        # Replace first occurrence with 中文全称（English Full Name, ABBR）
        full_expansion = f'{zh}（{en}, {abbr}）'
        # If it is already inside full-width or half-width parentheses, e.g. （LLM）, avoid nested double parens
        before = working[:start]
        after = working[end:]
        open_p = max(before.rfind('（'), before.rfind('('))
        close_p_before = max(before.rfind('）'), before.rfind(')'))
        if open_p > close_p_before:
            full_expansion = f'{zh} [{en}, {abbr}]'
        working = before + full_expansion + after
        defined_set.add(abbr)

    for idx, tok in enumerate(placeholders):
        working = working.replace(f'\x00EID{idx}\x00', tok)
    return working


def normalize_manuscript_abbreviations(sections):
    """Expand first-appearance abbreviations independently in Abstract scope and Main Body scope."""
    from .writer import infer_section_kind
    abstract_defined = set()
    body_defined = set()
    normalized = []
    for sec in sections:
        title = sec['title']
        body = sec['body']
        kind = infer_section_kind(title)
        if kind == 'keywords' or kind == 'declarations':
            normalized.append({'title': title, 'body': body})
            continue
        scope_set = abstract_defined if kind == 'abstract' else body_defined
        out_lines = []
        in_code = False
        for line in body.splitlines():
            if line.strip().startswith(('```', ':::')):
                in_code = not in_code
                out_lines.append(line)
                continue
            if in_code:
                out_lines.append(line)
                continue
            out_lines.append(_normalize_line_in_scope(line, scope_set))
        normalized.append({'title': title, 'body': '\n'.join(out_lines)})
    return normalized


def find_undefined_first_abbreviations(sections):
    """Return a list of (section_title, abbr) for abbreviations that appear for the first time in Abstract or Body without a full-name definition."""
    from .writer import infer_section_kind
    abstract_defined = set()
    body_defined = set()
    violations = []
    for sec in sections:
        title = sec['title']
        body = sec['body']
        kind = infer_section_kind(title)
        if kind in ('keywords', 'declarations'):
            continue
        # Only enforce on Chinese academic sections
        if not re.search(r'[\u4e00-\u9fff]', body):
            continue
        scope_set = abstract_defined if kind == 'abstract' else body_defined
        # Strip [E:...] tags and headings before scanning
        cleaned_lines = []
        in_block = False
        for ln in body.splitlines():
            s = ln.strip()
            if s.startswith(('```', ':::')):
                in_block = not in_block
                continue
            if in_block or s.startswith('#'):
                continue
            cleaned_lines.append(re.sub(r'\[E:[A-Za-z0-9_-]{1,40}\]', '', ln))
        cleaned = '\n'.join(cleaned_lines)
        sec_undef = []
        for abbr, zh, en, pat in ABBR_PATTERNS:
            if abbr not in ENFORCED_ABBREVIATIONS:
                continue
            if abbr in scope_set:
                continue
            m = pat.search(cleaned)
            if not m:
                continue
            if is_defined_near(cleaned, m.start(), m.end(), abbr, zh, en):
                scope_set.add(abbr)
            else:
                scope_set.add(abbr)
                sec_undef.append(abbr)
        if sec_undef:
            violations.append((title, sec_undef))
    return violations
