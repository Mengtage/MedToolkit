"""Scoped reviewer credentials for loopback HTTP. Administrator/disk access is trusted."""
import hashlib
import re
import secrets
from .core import now

class ReviewAccess:
    def __init__(self,store):
        self.store=store
        with store.db() as db:db.execute('CREATE TABLE IF NOT EXISTS review_principals(actor TEXT PRIMARY KEY, role TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL, active INTEGER NOT NULL, created TEXT NOT NULL)')
    def issue(self,actor,role):
        if not isinstance(actor,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',actor):raise ValueError('评审ID使用1至64位字母、数字、下划线或连字符')
        if role not in ('human','model'):raise ValueError('身份须为human或model')
        token=secrets.token_urlsafe(32)
        with self.store.db() as db:
            if db.execute('SELECT 1 FROM review_principals WHERE actor=?',(actor,)).fetchone():raise ValueError('评审ID已存在，不覆盖原身份')
            db.execute('INSERT INTO review_principals VALUES(?,?,?,?,?)',(actor,role,hashlib.sha256(token.encode()).hexdigest(),1,now()))
        return {'actor':actor,'role':role,'token':token}
    def authenticate(self,token):
        if not isinstance(token,str) or len(token)>256:return None
        with self.store.db() as db:r=db.execute('SELECT actor,role FROM review_principals WHERE token_hash=? AND active=1',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return dict(zip(('actor','role'),r)) if r else None
    def list(self):
        with self.store.db() as db:return [dict(zip(('actor','role','active'),r)) for r in db.execute('SELECT actor,role,active FROM review_principals ORDER BY actor')]
    def revoke(self,actor):
        with self.store.db() as db:
            if db.execute('UPDATE review_principals SET active=0 WHERE actor=? AND active=1',(actor,)).rowcount!=1:raise ValueError('身份不存在或已撤销')
        return {'revoked':actor}
    def validate_protocol(self,protocol):
        active={p['actor']:p['role'] for p in self.list() if p['active']}
        for key,role in [('human_reviewer','human'),('llm_reviewer','model'),('adjudicator','human')]:
            if active.get(protocol.get(key))!=role:raise ValueError('方案中的评审者须为已启用的对应身份')
