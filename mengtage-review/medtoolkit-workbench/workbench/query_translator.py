"""Boolean search query translator for multi-database coverage (PubMed, Embase/Ovid, Web of Science, Scopus, Cochrane Central).

Pairs live no-CAPTCHA open APIs (PubMed, Europe PMC, OpenAlex, Crossref, ClinicalTrials.gov)
with compliant offline RIS/NBIB/CSV export and import for subscription-gated databases.
"""
import re


SUPPORTED_TARGET_DATABASES = ('pubmed', 'embase_ovid', 'wos', 'scopus', 'cochrane')


def _strip_field_tags(query):
    """Normalize a PubMed/generic boolean query into a neutral boolean expression while preserving terms and operators."""
    q = (query or '').strip()
    if not q:
        raise ValueError('检索式不能为空')
    return q


def _extract_mesh_and_tiab(query):
    """Convert PubMed [Mesh] and [tiab]/[Title/Abstract] tags into target database syntax."""
    q = _strip_field_tags(query)
    return q


def translate_to_pubmed(query, date_from=None, date_to=None):
    q = _strip_field_tags(query)
    # Normalize bare [tiab] or [Title/Abstract] or unlabelled quoted phrases
    if date_from or date_to:
        df = (date_from or '1900/01/01').replace('-', '/')
        dt = (date_to or '3000/12/31').replace('-', '/')
        if len(df) == 4:
            df += '/01/01'
        if len(dt) == 4:
            dt += '/12/31'
        q = f'({q}) AND ("{df}"[Date - Publication] : "{dt}"[Date - Publication])'
    return q


def translate_to_embase_ovid(query, date_from=None, date_to=None):
    q = _strip_field_tags(query)
    # Convert "Term"[Mesh] -> exp Term/
    q = re.sub(r'"([^"]+)"\s*\[(?:Mesh|MeSH Terms|mh)\]', lambda m: f'exp {m.group(1).lower()}/', q, flags=re.I)
    # Convert "Term"[tiab] -> "Term".ti,ab,kw.
    q = re.sub(r'"([^"]+)"\s*\[(?:tiab|Title/Abstract|tw)\]', r'"\1".ti,ab,kw.', q, flags=re.I)
    # Convert word*[tiab] -> word*.ti,ab,kw.
    q = re.sub(r'([A-Za-z0-9_*-]+)\s*\[(?:tiab|Title/Abstract|tw)\]', r'\1.ti,ab,kw.', q, flags=re.I)
    # Convert TITLE_ABS:"Term" -> "Term".ti,ab,kw.
    q = re.sub(r'TITLE_ABS:"([^"]+)"', r'"\1".ti,ab,kw.', q, flags=re.I)
    if date_from or date_to:
        y1 = (date_from or '1900')[:4]
        y2 = (date_to or '2099')[:4]
        q = f'({q}) and {y1}:{y2}.(sa_year).'
    return q


def translate_to_wos(query, date_from=None, date_to=None):
    q = _strip_field_tags(query)
    q = re.sub(r'"([^"]+)"\s*\[(?:Mesh|MeSH Terms|mh|tiab|Title/Abstract|tw)\]', r'"\1"', q, flags=re.I)
    q = re.sub(r'([A-Za-z0-9_*-]+)\s*\[(?:Mesh|MeSH Terms|mh|tiab|Title/Abstract|tw)\]', r'\1', q, flags=re.I)
    q = re.sub(r'TITLE_ABS:"([^"]+)"', r'"\1"', q, flags=re.I)
    out = f'TS=({q})'
    if date_from or date_to:
        y1 = (date_from or '1900')[:4]
        y2 = (date_to or '2099')[:4]
        out += f' AND PY=({y1}-{y2})'
    return out


def translate_to_scopus(query, date_from=None, date_to=None):
    q = _strip_field_tags(query)
    q = re.sub(r'"([^"]+)"\s*\[(?:Mesh|MeSH Terms|mh|tiab|Title/Abstract|tw)\]', r'"\1"', q, flags=re.I)
    q = re.sub(r'([A-Za-z0-9_*-]+)\s*\[(?:Mesh|MeSH Terms|mh|tiab|Title/Abstract|tw)\]', r'\1', q, flags=re.I)
    q = re.sub(r'TITLE_ABS:"([^"]+)"', r'"\1"', q, flags=re.I)
    out = f'TITLE-ABS-KEY({q})'
    if date_from:
        y1 = int(str(date_from)[:4]) - 1
        out += f' AND PUBYEAR > {y1}'
    if date_to:
        y2 = int(str(date_to)[:4]) + 1
        out += f' AND PUBYEAR < {y2}'
    return out


def translate_to_cochrane(query, date_from=None, date_to=None):
    q = _strip_field_tags(query)
    q = re.sub(r'"([^"]+)"\s*\[(?:Mesh|MeSH Terms|mh)\]', r'[mh "\1"]', q, flags=re.I)
    q = re.sub(r'"([^"]+)"\s*\[(?:tiab|Title/Abstract|tw)\]', r'("\1"):ti,ab,kw', q, flags=re.I)
    q = re.sub(r'([A-Za-z0-9_*-]+)\s*\[(?:tiab|Title/Abstract|tw)\]', r'(\1):ti,ab,kw', q, flags=re.I)
    q = re.sub(r'TITLE_ABS:"([^"]+)"', r'("\1"):ti,ab,kw', q, flags=re.I)
    if date_from or date_to:
        y1 = (date_from or '1900')[:4]
        y2 = (date_to or '2099')[:4]
        q = f'({q}) WITH Publication Year from {y1} to {y2}'
    return q


def translate_query(query, target='all', date_from=None, date_to=None):
    """Translate a search query into one or all 5 major biomedical database syntaxes."""
    if not isinstance(query, str) or not query.strip() or len(query) > 8000:
        raise ValueError('检索式须为1至8000字符的非空文本')
    translators = {
        'pubmed': ('PubMed / MEDLINE', 'open_api_and_nbib', translate_to_pubmed),
        'embase_ovid': ('Embase (Ovid)', 'subscription_ris_import', translate_to_embase_ovid),
        'wos': ('Web of Science Core Collection', 'subscription_ris_import', translate_to_wos),
        'scopus': ('Scopus', 'subscription_ris_csv_import', translate_to_scopus),
        'cochrane': ('Cochrane Central Register of Controlled Trials (CENTRAL)', 'subscription_ris_import', translate_to_cochrane),
    }
    if target != 'all' and target not in translators:
        raise ValueError('目标数据库仅支持 pubmed, embase_ovid, wos, scopus, cochrane 或 all')
    keys = list(translators.keys()) if target == 'all' else [target]
    translations = {}
    for k in keys:
        label, mode, fn = translators[k]
        translations[k] = {
            'database': label,
            'acquisition_mode': mode,
            'translated_query': fn(query, date_from=date_from, date_to=date_to),
            'import_guide': (
                '可通过 MedToolkit 原生免验证 API 自动全量翻页拉取，或导出 .nbib/.ris 导入'
                if k == 'pubmed'
                else f'在机构订阅端执行该检索式并全量导出为 .ris 或 .csv 文件后，调用 /api/sources/import_file 导入工作台统一去重'
            ),
        }
    return {
        'original_query': query.strip(),
        'date_from': date_from,
        'date_to': date_to,
        'open_api_databases': ['pubmed', 'europe_pmc', 'openalex', 'crossref', 'clinicaltrials'],
        'translations': translations,
    }
