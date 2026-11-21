"""Verify original release files against the bundled SHA256 manifest."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=root/'MANIFEST.json'
if not manifest.exists():raise SystemExit('No release MANIFEST.json in this directory')
files=json.loads(manifest.read_text())['sha256'];failed=[]
for name,digest in files.items():
 p=root/name
 if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:failed.append(name)
if failed:
 print('Changed or missing files:\n'+'\n'.join(failed));sys.exit(1)
print(f'PASS: {len(files)} release files match SHA256 manifest')
