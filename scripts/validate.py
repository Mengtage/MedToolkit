"""Run core regression and statistical acceptance; any failed suite fails validation."""
import json
import hashlib
from datetime import datetime, timezone
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
REPORTS.mkdir(exist_ok=True)
SUITES = [
    ('core', ['-m', 'unittest', 'discover', '-s', 'tests', '-v']),
    ('groups', ['tests/acceptance_groups.py']),
    ('regression', ['tests/acceptance_regression.py']),
    ('missing', ['tests/acceptance_missing.py']),
]
results = []
for name, args in SUITES:
    run = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    (REPORTS / f'validation-{name}.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    record = {'suite': name, 'exit_code': run.returncode, 'status': 'PASS' if run.returncode == 0 else 'FAIL'}
    if name != 'core':
        try:
            data = json.loads((REPORTS / f'acceptance-{name}.json').read_text())
            rows = data if isinstance(data, list) else data['results']
            record['counts'] = {s: sum(row['status'] == s for row in rows) for s in ['PASS', 'FAIL', 'BLOCKED']}
            if not rows or any(row['status'] != 'PASS' for row in rows):
                record['status'] = 'FAIL'
        except (OSError, KeyError, ValueError, TypeError):
            record['status'] = 'FAIL'
            record['report_error'] = 'missing_or_invalid_report'
    results.append(record)
    print(json.dumps(record, ensure_ascii=False))
summary = {'status': 'PASS' if all(r['status'] == 'PASS' for r in results) else 'FAIL', 'suites': results}
summary['validated_at']=datetime.now(timezone.utc).isoformat()
summary['python']=sys.version.split()[0]
summary['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['workbench','tests','modules/MedStat/src/analysis'] for p in (ROOT/folder).glob('*.py')}
summary['source_sha256']['modules/MedStat/app.py']=hashlib.sha256((ROOT/'modules/MedStat/app.py').read_bytes()).hexdigest()
(REPORTS / 'validation-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
sys.exit(0 if summary['status'] == 'PASS' else 1)
