#!/usr/bin/env python3
"""Local draft helper. No network, model calls, or statistical analysis."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import fcntl


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def initialize(root, question):
    if not question.strip():
        raise ValueError('研究问题不能为空')
    root.mkdir(parents=True, exist_ok=False)
    for name in ('01_search/raw', '02_screening', '03_extraction', '04_analysis', '05_manuscript'):
        (root / name).mkdir(parents=True)
    write_json(root/'project.json', {'schema_version': 1, 'question': question,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'modules': {'literature_csv': 'local_helper', 'search': 'agent_guided',
                    'MedPaperHunter': 'source_missing', 'MedStat': 'source_missing',
                    'MedPaperWriter': 'source_missing'}})
    write_json(root/'status.json', {'stage': 'question_draft', 'blockers': ['研究范围待确认'],
                                  'approval': None})
    return {'initialized': str(root)}


def parse_csv(data, file_hash):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    if not reader.fieldnames or not {'source', 'title'}.issubset(reader.fieldnames):
        raise ValueError('CSV必须有source,title列，编码为UTF-8')
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError('CSV存在重复列名')
    rows = []
    for line, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'第{line}行字段数量不一致')
        if not row['source'].strip() or not row['title'].strip():
            raise ValueError(f'第{line}行source/title为空')
        doi = row.get('doi', '').strip().lower()
        for prefix in ('https://doi.org/', 'http://doi.org/', 'http://dx.doi.org/', 'https://dx.doi.org/', 'doi:'):
            if doi.startswith(prefix):
                doi = doi[len(prefix):].strip()
                break
        pmid = row.get('pmid', '').strip()
        rows.append({'source_file_hash': file_hash, 'source_row': line,
                     'doi': doi, 'pmid': pmid, 'original': row})
    if not rows:
        raise ValueError('CSV没有记录')
    return rows


def group_records(rows):
    doi_pmids, pmid_dois = {}, {}
    for r in rows:
        if r['doi'] and r['pmid']:
            doi_pmids.setdefault(r['doi'], set()).add(r['pmid'])
            pmid_dois.setdefault(r['pmid'], set()).add(r['doi'])
    groups = {}
    for r in rows:
        conflict = len(doi_pmids.get(r['doi'], ())) > 1 or len(pmid_dois.get(r['pmid'], ())) > 1
        valid_doi = r['doi'].startswith('10.') and '/' in r['doi'] and not any(c.isspace() for c in r['doi'])
        valid_pmid = r['pmid'].isascii() and r['pmid'].isdigit() and int(r['pmid']) > 0
        invalid = bool(r['doi'] and not valid_doi) or bool(r['pmid'] and not valid_pmid)
        if conflict or invalid:
            key = f"row:{r['source_file_hash']}:{r['source_row']}"
        elif valid_doi:
            key = 'doi:' + r['doi']
        elif valid_pmid:
            # Do not infer PMID-to-DOI links; review cross-identifier records separately.
            key = 'pmid:' + r['pmid']
        else:
            key = f"row:{r['source_file_hash']}:{r['source_row']}"
        g = groups.setdefault(key, {'record_id': 'rec_' + digest(key.encode())[:20],
            'needs_review': conflict or invalid or not (valid_doi or valid_pmid),
            'reason': 'identifier_conflict' if conflict else 'invalid_identifier' if invalid else
                      'missing_identifier' if not (valid_doi or valid_pmid) else '', 'provenance': []})
        g['provenance'].append(r)
    return list(groups.values())


def import_csv(root, source):
    if not (root/'project.json').is_file():
        raise ValueError('先初始化项目')
    data = source.read_bytes()
    file_hash = digest(data)
    parse_csv(data, file_hash)  # Validate before changing project files.
    with (root/'.import.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        raw = root/'01_search/raw'/f'{file_hash}.csv'
        already = raw.exists()
        if not already:
            tmp = raw.with_suffix('.tmp')
            tmp.write_bytes(data)
            os.replace(tmp, raw)
        all_rows = []
        for path in sorted((root/'01_search/raw').glob('*.csv')):
            content = path.read_bytes()
            if digest(content) != path.stem:
                raise ValueError('原始文件哈希不符：' + path.name)
            all_rows.extend(parse_csv(content, path.stem))
        records = group_records(all_rows)
        result = {'raw_records': len(all_rows), 'unique_records': len(records),
                  'merged_duplicate_records': len(all_rows)-len(records),
                  'review_records': sum(r['needs_review'] for r in records), 'records': records}
        write_json(root/'02_screening/records.json', result)
        return {'input_sha256': file_hash, 'already_imported': already,
                **{k:v for k,v in result.items() if k != 'records'}}


def status(root):
    value = json.loads((root/'status.json').read_text())
    path = root/'02_screening/records.json'
    if path.exists():
        d = json.loads(path.read_text())
        value['literature_counts'] = {k:v for k,v in d.items() if k != 'records'}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('root', type=Path); init.add_argument('--question', required=True)
    imp = sub.add_parser('import'); imp.add_argument('root', type=Path); imp.add_argument('csv', type=Path)
    stat = sub.add_parser('status'); stat.add_argument('root', type=Path)
    a = parser.parse_args()
    try:
        result = initialize(a.root, a.question) if a.command == 'init' else import_csv(a.root, a.csv) if a.command == 'import' else status(a.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, UnicodeError) as exc:
        parser.exit(1, str(exc)+'\n')


if __name__ == '__main__':
    main()
