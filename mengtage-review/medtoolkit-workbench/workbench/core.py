"""Project-scoped artifacts and durable, explicit job execution."""
import hashlib
import fcntl
from contextlib import contextmanager
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def now():
    return datetime.now(timezone.utc).isoformat()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, question TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project TEXT, kind TEXT,
                payload TEXT, state TEXT, created TEXT, updated TEXT, result TEXT, error TEXT,
                UNIQUE(project,kind,payload));
            ''')
        os.chmod(self.root/'state.sqlite',0o600)

    @contextmanager
    def db(self):
        connection=sqlite3.connect(self.root/'state.sqlite', timeout=20)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, question):
        if not isinstance(question,str) or not question.strip() or len(question)>4000:
            raise ValueError('研究问题不能为空或超过4000字符')
        pid=uuid.uuid4().hex
        with self.db() as db:
            db.execute('INSERT INTO projects VALUES(?,?,?)',(pid,question.strip(),now()))
        (self.root/pid).mkdir(mode=0o700)
        return pid

    def project(self,pid):
        if not re.fullmatch('[a-f0-9]{32}',pid):raise ValueError('项目ID无效')
        with self.db() as db:
            r=db.execute('SELECT id,question,created FROM projects WHERE id=?',(pid,)).fetchone()
        if not r:raise ValueError('项目不存在')
        return dict(zip(['id','question','created'],r))

    def projects(self):
        with self.db() as db:
            return [dict(zip(['id','question','created'],r)) for r in db.execute('SELECT * FROM projects ORDER BY created DESC')]

    def artifact(self,pid,name):
        self.project(pid)
        if not re.fullmatch('[a-zA-Z0-9_.-]+',name) or name.startswith('.'):
            raise ValueError('产物名无效')
        return self.root/pid/name

    def save(self,pid,name,value):
        p=self.artifact(pid,name)
        tmp=p.with_suffix(p.suffix+'.tmp')
        tmp.write_text(canonical(value),encoding='utf-8')
        os.chmod(tmp,0o600);os.replace(tmp,p)
        return name

    def enqueue(self,pid,kind,payload):
        self.project(pid)
        if kind not in ['search','statistics','write','deduplicate','dedup_review']:raise ValueError('未知任务')
        if not isinstance(payload,dict):raise ValueError('任务输入必须是对象')
        payload=dict(payload)
        from .adapters import validate_payload
        validate_payload(kind,payload)
        if kind in ('deduplicate','dedup_review'):
            from .dedup_jobs import load_source
            load_source(self,pid,payload)
        if kind=='write':payload['_model']=os.environ.get('GEMINI_MODEL','unconfigured')
        raw=canonical(payload)
        if len(raw)>1_000_000:raise ValueError('任务输入过大')
        jid=uuid.uuid4().hex
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
                       (jid,pid,kind,raw,'queued',now(),now(),None,None))
            return db.execute('SELECT id FROM jobs WHERE project=? AND kind=? AND payload=?',(pid,kind,raw)).fetchone()[0]

    def jobs(self,pid):
        self.project(pid)
        with self.db() as db:
            rows=db.execute('SELECT id,kind,state,created,result,error FROM jobs WHERE project=? ORDER BY created',(pid,)).fetchall()
        return [dict(zip(['id','kind','state','created','result','error'],r)) for r in rows]

    @contextmanager
    def worker_lock(self):
        with (self.root/'.worker.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise ValueError('已有工作进程运行')
            try:yield
            finally:fcntl.flock(lock,fcntl.LOCK_UN)

    def runnable(self,jid):
        with self.db() as db:
            row=db.execute('SELECT state FROM jobs WHERE id=?',(jid,)).fetchone()
        return bool(row and row[0]=='queued')

    def run(self,jid):
        with self.worker_lock():return self._run(jid)

    def _run(self,jid):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            r=db.execute('SELECT project,kind,payload,state FROM jobs WHERE id=?',(jid,)).fetchone()
            if not r:raise ValueError('任务不存在')
            if r[3]!='queued':raise ValueError('只运行queued任务；不自动重试付费调用')
            db.execute('UPDATE jobs SET state=?,updated=? WHERE id=?',('running',now(),jid))
        pid,kind,payload,_=r
        try:
            from .adapters import search, statistics, write
            if kind in ('deduplicate','dedup_review'):
                from .dedup_jobs import run
                result=run(self,pid,json.loads(payload),jid,kind)
            else:result={'search':search,'statistics':statistics,'write':write}[kind](self,pid,json.loads(payload),jid)
            if kind=='statistics':
                result['artifact_sha256']=hashlib.sha256(self.artifact(pid,result['artifact']).read_bytes()).hexdigest()
                result['payload_sha256']=hashlib.sha256(canonical(json.loads(payload)).encode()).hexdigest()
            with self.db() as db:db.execute('UPDATE jobs SET state=?,updated=?,result=? WHERE id=?',('completed',now(),canonical(result),jid))
            return result
        except Exception as e:
            # No provider exception body, prompt, URL or dataset in diagnostic logs.
            msg=str(e) if isinstance(e,ValueError) and any('\u4e00'<=c<='\u9fff' for c in str(e)) and len(str(e))<=200 else type(e).__name__
            with self.db() as db:db.execute('UPDATE jobs SET state=?,updated=?,error=? WHERE id=?',('failed',now(),msg,jid))
            raise

    def retry(self,jid,confirmed=False):
        if confirmed is not True:raise ValueError('需明确确认重试，远端调用可能已完成')
        with self.db() as db:
            row=db.execute('SELECT project,kind,payload,state FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row or row[3] not in ['failed','needs_review']:raise ValueError('只可重试失败或待复核任务')
        payload=json.loads(row[2]);payload['_retry_of']=jid
        return self.enqueue(row[0],row[1],payload)

    def recover(self):
        # Only call when no worker is running. Never auto-repeat an uncertain remote request.
        with self.worker_lock():
            with self.db() as db:
                return db.execute("UPDATE jobs SET state='needs_review',updated=? WHERE state='running'",(now(),)).rowcount
