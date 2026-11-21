"""Native bibliographic & statistical file importers (RIS, PubMed .nbib, CSV)."""
import csv
import io
import math
import re


def parse_ris(text):
    """Parse RIS bibliographic text into MedToolkit normalized records."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('RIS文件内容为空')
    records = []
    cur = None
    last_tag = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip('\r\n')
        m = re.match(r'^([A-Z0-9]{2})\s+-\s?(.*)$', line)
        if m:
            tag, val = m.group(1), m.group(2).strip()
            last_tag = tag
            if tag == 'TY':
                cur = {'authors': []}
            elif tag == 'ER':
                if cur and cur.get('title'):
                    records.append(_finalize_bib_record(cur))
                cur = None
                last_tag = None
            else:
                if cur is None:
                    cur = {'authors': []}
                _apply_ris_tag(cur, tag, val)
        elif cur is not None and last_tag in ('TI', 'T1', 'AB', 'N2') and line.strip():
            key = 'title' if last_tag in ('TI', 'T1') else 'abstract'
            cur[key] = (cur.get(key, '') + ' ' + line.strip()).strip()
    if cur and cur.get('title'):
        records.append(_finalize_bib_record(cur))
    if not records:
        raise ValueError('未从RIS文件中解析到有效文献记录')
    return records


def _apply_ris_tag(cur, tag, val):
    if not val:
        return
    if tag in ('TI', 'T1') and not cur.get('title'):
        cur['title'] = val
    elif tag in ('AB', 'N2'):
        cur['abstract'] = (cur.get('abstract', '') + '\n' + val).strip() if cur.get('abstract') else val
    elif tag in ('AU', 'A1'):
        cur.setdefault('authors', []).append(val.replace(',', ''))
    elif tag in ('JO', 'JF', 'T2', 'JA') and not cur.get('journal'):
        cur['journal'] = val
    elif tag in ('PY', 'Y1', 'DA') and not cur.get('pub_date'):
        cur['pub_date'] = val.split('/')[0].strip() or val
    elif tag == 'VL' and not cur.get('volume'):
        cur['volume'] = val
    elif tag == 'IS' and not cur.get('issue'):
        cur['issue'] = val
    elif tag == 'SP':
        cur['_sp'] = val
    elif tag == 'EP':
        cur['_ep'] = val
    elif tag == 'DO' and not cur.get('doi'):
        m = re.search(r'(10\.\d{4,9}/\S+)', val)
        if m:
            cur['doi'] = m.group(1).rstrip('.,;')
    elif tag in ('AN', 'ID', 'N1', 'UR'):
        m_pmid = re.search(r'(?:PMID[:\s]*|pubmed\.ncbi\.nlm\.nih\.gov/)(\d{4,10})', val, re.I)
        if m_pmid and not cur.get('pmid'):
            cur['pmid'] = m_pmid.group(1)
        elif tag == 'AN' and re.fullmatch(r'\d{4,10}', val) and not cur.get('pmid'):
            cur['pmid'] = val
        m_doi = re.search(r'(10\.\d{4,9}/\S+)', val)
        if m_doi and not cur.get('doi'):
            cur['doi'] = m_doi.group(1).rstrip('.,;')


def parse_nbib(text):
    """Parse PubMed MEDLINE / .nbib format into MedToolkit normalized records."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('NBIB/MEDLINE文件内容为空')
    records = []
    cur = None
    last_tag = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip('\r\n')
        if not line.strip():
            if cur and cur.get('title'):
                records.append(_finalize_bib_record(cur))
                cur = None
                last_tag = None
            continue
        m = re.match(r'^([A-Z]{2,4})\s*-\s+(.*)$', line)
        if m:
            tag, val = m.group(1).strip(), m.group(2).strip()
            last_tag = tag
            if tag == 'PMID' and cur and cur.get('title'):
                records.append(_finalize_bib_record(cur))
                cur = None
            if cur is None:
                cur = {'authors': []}
            if tag == 'PMID':
                if re.fullmatch(r'\d+', val):
                    cur['pmid'] = val
            elif tag == 'TI':
                cur['title'] = (cur.get('title', '') + ' ' + val).strip()
            elif tag == 'AB':
                cur['abstract'] = (cur.get('abstract', '') + ' ' + val).strip()
            elif tag in ('FAU', 'AU'):
                if tag == 'FAU' or not cur.get('_has_fau'):
                    if tag == 'FAU':
                        cur['_has_fau'] = True
                    cur['authors'].append(val.replace(',', ''))
            elif tag in ('JT', 'TA') and not cur.get('journal'):
                cur['journal'] = val
            elif tag == 'DP' and not cur.get('pub_date'):
                cur['pub_date'] = val
            elif tag == 'VI' and not cur.get('volume'):
                cur['volume'] = val
            elif tag == 'IP' and not cur.get('issue'):
                cur['issue'] = val
            elif tag == 'PG' and not cur.get('pages'):
                cur['pages'] = val
            elif tag in ('LID', 'AID'):
                if '[doi]' in val.lower():
                    m_doi = re.search(r'(10\.\d{4,9}/\S+)', val)
                    if m_doi:
                        cur['doi'] = m_doi.group(1)
        elif cur is not None and line.startswith('  ') and last_tag in ('TI', 'AB', 'JT'):
            field = {'TI': 'title', 'AB': 'abstract', 'JT': 'journal'}[last_tag]
            cur[field] = (cur.get(field, '') + ' ' + line.strip()).strip()
    if cur and cur.get('title'):
        records.append(_finalize_bib_record(cur))
    if not records:
        raise ValueError('未从NBIB/MEDLINE文件中解析到有效文献记录')
    return records


def parse_bib_csv(text):
    """Parse CSV bibliographic export into MedToolkit normalized records."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('CSV文件内容为空')
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames:
        raise ValueError('CSV缺少表头')
    records = []
    for row in reader:
        norm = {str(k or '').strip().lower(): str(v or '').strip() for k, v in row.items()}
        title = norm.get('title') or norm.get('article title') or norm.get('document title') or norm.get('题名') or norm.get('标题') or ''
        if not title:
            continue
        cur = {'title': title, 'authors': []}
        abstract = norm.get('abstract') or norm.get('摘要') or ''
        if abstract:
            cur['abstract'] = abstract
        pmid = norm.get('pmid') or norm.get('pubmed id') or ''
        m_pmid = re.search(r'\b(\d{4,10})\b', pmid)
        if m_pmid:
            cur['pmid'] = m_pmid.group(1)
        doi = norm.get('doi') or ''
        m_doi = re.search(r'(10\.\d{4,9}/\S+)', doi)
        if m_doi:
            cur['doi'] = m_doi.group(1).rstrip('.,;')
        authors = norm.get('authors') or norm.get('author') or norm.get('作者') or ''
        if authors:
            sep = ';' if ';' in authors else ','
            cur['authors'] = [a.strip() for a in authors.split(sep) if a.strip()]
        journal = norm.get('journal') or norm.get('journal/book') or norm.get('source title') or norm.get('期刊') or ''
        if journal:
            cur['journal'] = journal
        pub_date = norm.get('pub_date') or norm.get('publication year') or norm.get('year') or norm.get('date') or norm.get('年份') or ''
        if pub_date:
            cur['pub_date'] = pub_date
        for key, aliases in [('volume', ('volume', 'vol', '卷')), ('issue', ('issue', '期')), ('pages', ('pages', 'page', 'pagination', '页码'))]:
            val = next((norm[a] for a in aliases if norm.get(a)), '')
            if val:
                cur[key] = val
        records.append(_finalize_bib_record(cur))
    if not records:
        raise ValueError('未从CSV文件中解析到包含题名的文献记录')
    return records


def _finalize_bib_record(cur):
    sp = cur.pop('_sp', '')
    ep = cur.pop('_ep', '')
    cur.pop('_has_fau', None)
    if sp and not cur.get('pages'):
        cur['pages'] = f'{sp}-{ep}' if ep and ep != sp else sp
    allowed = {'title', 'abstract', 'pmid', 'doi', 'authors', 'journal', 'pub_date', 'volume', 'issue', 'pages'}
    out = {}
    for k in allowed:
        v = cur.get(k)
        if v is None:
            continue
        if k == 'authors':
            if isinstance(v, list):
                clean_a = [str(a).strip() for a in v if str(a).strip()]
                if clean_a:
                    out['authors'] = clean_a
        elif isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out


def parse_bibliographic_file(filename, content):
    """Auto-detect and parse .ris, .nbib/.txt (MEDLINE), or .csv bibliographic files."""
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError('需提供书目文件名')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('书目文件内容为空')
    lower = filename.strip().lower()
    stripped = content.lstrip('\ufeff').lstrip()
    if lower.endswith('.ris') or re.match(r'^TY\s+-', stripped):
        return parse_ris(content)
    if lower.endswith(('.nbib', '.medline')) or re.match(r'^PMID-\s+\d+', stripped):
        return parse_nbib(content)
    if lower.endswith('.csv'):
        return parse_bib_csv(content)
    if re.search(r'^TY\s+-', stripped, re.M):
        return parse_ris(content)
    if re.search(r'^PMID-\s+\d+', stripped, re.M):
        return parse_nbib(content)
    return parse_bib_csv(content)


def parse_statistics_csv(text, selected_columns=None):
    """Parse a CSV table into MedStat rows and inferred variable_types."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('统计CSV内容为空')
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames:
        raise ValueError('统计CSV缺少表头')
    headers = [h.strip() for h in reader.fieldnames if h and h.strip()]
    if selected_columns is not None:
        if not isinstance(selected_columns, list) or not selected_columns or any(c not in headers for c in selected_columns):
            raise ValueError('所选统计列不在CSV表头中')
        headers = [c for c in headers if c in selected_columns]
    if not 1 <= len(headers) <= 30:
        raise ValueError('统计CSV需包含1至30个有效列')
    raw_rows = list(reader)
    if not 1 <= len(raw_rows) <= 10000:
        raise ValueError('统计CSV行数须为1至10000行')
    variable_types = {}
    for col in headers:
        non_empty = [str(r.get(col) or '').strip() for r in raw_rows if str(r.get(col) or '').strip() not in ('', 'NA', 'N/A', 'null', 'None', 'nan', 'NaN')]
        is_num = bool(non_empty)
        for v in non_empty:
            try:
                f = float(v)
                if not math.isfinite(f):
                    is_num = False
                    break
            except ValueError:
                is_num = False
                break
        variable_types[col] = 'numeric_continuous' if is_num else 'categorical'
    rows = []
    for r in raw_rows:
        item = {}
        for col in headers:
            raw_val = str(r.get(col) or '').strip()
            if raw_val in ('', 'NA', 'N/A', 'null', 'None', 'nan', 'NaN'):
                item[col] = None
            elif variable_types[col] == 'numeric_continuous':
                f = float(raw_val)
                item[col] = int(f) if f.is_integer() and '.' not in raw_val else f
            else:
                item[col] = raw_val
        rows.append(item)
    return {'columns': headers, 'variable_types': variable_types, 'rows': rows, 'row_count': len(rows)}
