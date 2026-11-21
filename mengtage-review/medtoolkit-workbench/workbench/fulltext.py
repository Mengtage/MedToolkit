"""Local immutable PDF/text snapshots and explicit cross-stage retrieval ledger."""
import base64
import binascii
import hashlib
import json
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from .core import canonical,now

MAX_FILE=5_000_000
MAX_TEXT=1_000_000

def sha(raw):return hashlib.sha256(raw).hexdigest()
def json_hash(value):return sha(canonical(value).encode())

def snapshot(store,project,filename,encoded):
    if not isinstance(filename,str) or not filename or len(filename)>200 or '/' in filename or '\\' in filename:raise ValueError('文件名无效')
    suffix=Path(filename).suffix.lower()
    if suffix not in ('.pdf','.txt'):raise ValueError('仅支持PDF或UTF-8文本')
    try:raw=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError,binascii.Error):raise ValueError('文件编码无效')
    if not 0<len(raw)<=MAX_FILE:raise ValueError('文件大小须为1字节至5MB')
    if suffix=='.pdf':
        if not raw.startswith(b'%PDF-'):raise ValueError('PDF文件头无效')
        try:
            with tempfile.TemporaryDirectory(prefix='medtoolkit-pdf-') as tmp:
                path=Path(tmp)/'source.pdf';path.write_bytes(raw)
                info=subprocess.run(['pdfinfo',str(path)],capture_output=True,timeout=15)
                match=re.search(rb'^Pages:\s+(\d+)',info.stdout,re.M)
                if info.returncode or not match or not 1<=int(match[1])<=200:raise ValueError('PDF不可解析或超过200页')
                count=int(match[1]);out=Path(tmp)/'text.txt'
                run=subprocess.run(['pdftotext','-layout','-enc','UTF-8',str(path),str(out)],capture_output=True,timeout=20)
                if run.returncode or not out.exists() or out.stat().st_size>MAX_TEXT:raise ValueError('提取失败或文本超过1MB')
                text=out.read_text();pages=text.split('\f')
                if pages and not pages[-1].strip():pages.pop()
                if len(pages)!=count:raise ValueError('提取页数不一致，需人工核对')
                version=subprocess.run(['pdftotext','-v'],capture_output=True,timeout=5).stderr.decode(errors='replace').splitlines()[0]
        except (subprocess.TimeoutExpired,FileNotFoundError,UnicodeError):raise ValueError('本机PDF提取不可用或超时')
        extraction={'engine':'pdftotext -layout','version':version,'page_numbering':'physical_pdf_pages_1_based'}
    else:
        try:text=raw.decode('utf-8-sig')
        except UnicodeError:raise ValueError('文本须为UTF-8')
        if len(text.encode())>MAX_TEXT:raise ValueError('文本超过1MB')
        pages=text.split('\f')
        if len(pages)>200:raise ValueError('文本分页超过200')
        extraction={'engine':'utf8-text-v1','version':'1','page_numbering':'form_feed_segments_not_original_pdf_pages'}
    if not any(p.strip() for p in pages):raise ValueError('未提取到可读文本；扫描件需先OCR并人工核对')
    file_hash=sha(raw);blob=f'fulltext-{file_hash}{suffix}';target=store.artifact(project,blob)
    try:
        with target.open('xb') as f:f.write(raw)
        target.chmod(0o600)
    except FileExistsError:
        if sha(target.read_bytes())!=file_hash:raise ValueError('原件快照校验失败')
    items=[{'page':i+1,'text':p,'sha256':sha(p.encode())} for i,p in enumerate(pages)]
    return {'filename':filename,'blob':blob,'file_sha256':file_hash,'text_sha256':json_hash(items),
            'pages':items,'extraction':extraction,'created':now()}

def validate_snapshot(value):
    if not isinstance(value,dict) or not isinstance(value.get('pages'),list) or not value['pages']:raise ValueError('全文快照缺失')
    for i,p in enumerate(value['pages']):
        if not isinstance(p,dict) or p.get('page')!=i+1 or not isinstance(p.get('text'),str) or sha(p['text'].encode())!=p.get('sha256'):raise ValueError('全文页快照校验失败')
    if json_hash(value['pages'])!=value.get('text_sha256'):raise ValueError('全文文本哈希不匹配')
    if not re.fullmatch(r'fulltext-[a-f0-9]{64}\.(pdf|txt)',value.get('blob','')):raise ValueError('原件标识无效')
    if value['blob'][9:73]!=value.get('file_sha256'):raise ValueError('原件标识与哈希不一致')

def validate_evidence(record,locator,quote):
    full=record['fulltext'];validate_snapshot(full)
    if not isinstance(locator,str) or not re.fullmatch(r'p:[1-9][0-9]*',locator):raise ValueError('全文定位须使用p:页号，例如p:1')
    page=int(locator[2:])
    if page>len(full['pages']):raise ValueError('引用页码超出快照')
    if not isinstance(quote,str) or not quote.strip() or len(quote)>5000 or quote not in full['pages'][page-1]['text']:raise ValueError('须提供该页快照中可逐字核对的摘录（最多5000字符）')

class FulltextService:
    def __init__(self,service):
        self.service=service;self.store=service.store
        with self.store.db() as db:db.execute('CREATE TABLE IF NOT EXISTS fulltext_events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, parent_review TEXT NOT NULL, record_id TEXT NOT NULL, event TEXT NOT NULL)')
    def parent(self,review,actor):
        audit=self.service.ledger.export(review,actor);draft=audit['events'][0]['data']
        if draft['protocol']['stage']!='title_abstract' or audit['pending_final']:raise ValueError('需选择已完成全部裁决的题名摘要批次')
        included={r['record_id'] for r in audit['final_decisions'] if r['decision']=='include'}
        decisions={e['data']['record_id']:e['event_hash'] for e in audit['events'] if e['kind']=='adjudicated'}
        records={r['record_id']:r for r in draft['records'] if r['record_id'] in included}
        return audit,records,decisions
    def events(self,review):
        with self.store.db() as db:raw=[json.loads(r[0]) for r in db.execute('SELECT event FROM fulltext_events WHERE parent_review=? ORDER BY sequence',(review,))]
        previous=''
        for event in raw:
            body={k:v for k,v in event.items() if k!='event_hash'}
            if body['previous_hash']!=previous or json_hash(body)!=event['event_hash']:raise ValueError('全文取得记录审计链损坏')
            previous=event['event_hash']
        return raw
    def status(self,review,actor):
        audit,records,decisions=self.parent(review,actor);events=self.events(review);latest={e['record_id']:e for e in events}
        rows=[]
        for rid,item in records.items():
            event=latest.get(rid);valid=event and event['parent_decision_hash']==decisions[rid]
            rows.append({'record_id':rid,'title':item['record'].get('title',''),'status':event['status'] if valid else 'pending','event':event if valid else None})
        return {'review':review,'records':rows,'parent_event_hash':audit['events'][-1]['event_hash'],'events':events}
    def register(self,review,record_id,status,reason,actor,filename=None,content_base64=None):
        audit,records,decisions=self.parent(review,actor)
        if record_id not in records:raise ValueError('只能为父批次最终纳入记录登记全文')
        if status not in ('retrieved','not_retrieved') or not isinstance(reason,str) or not 1<=len(reason.strip())<=2000:raise ValueError('需填写取得状态及说明')
        project=audit['events'][0]['project_id']
        document=snapshot(self.store,project,filename,content_base64) if status=='retrieved' else None
        if status=='not_retrieved' and (filename is not None or content_base64 is not None):raise ValueError('未取得全文时不能携带文件')
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            # Recheck the selected final decision before appending a retrieval event.
            current,_,decision_now=self.parent(review,actor)
            if decision_now.get(record_id)!=decisions[record_id]:raise ValueError('父阶段裁决已变化，请刷新')
            events=self.events(review)
            event={'event_id':uuid.uuid4().hex,'parent_review_id':review,'record_id':record_id,'parent_record_sha256':records[record_id]['record_sha256'],
                   'parent_decision_hash':decisions[record_id],'status':status,'reason':reason.strip(),'document':document,
                   'actor':actor,'timestamp':now(),'previous_hash':events[-1]['event_hash'] if events else ''}
            event['event_hash']=json_hash(event)
            db.execute('INSERT INTO fulltext_events(parent_review,record_id,event) VALUES(?,?,?)',(review,record_id,canonical(event)))
        return {'event_hash':event['event_hash'],'status':status}
    def prepare(self,review,actor,protocol):
        audit,records,decisions=self.parent(review,actor);status=self.status(review,actor)
        if any(r['status']=='pending' for r in status['records']):raise ValueError('请先逐条登记取得或未取得全文')
        from .screening_exports import REASON_CODES,REASON_VERSION
        if not isinstance(protocol,dict):raise ValueError('需要全文筛选方案')
        protocol=dict(protocol);protocol['stage']='full_text'
        protocol.setdefault('reason_codes',dict(REASON_CODES));protocol.setdefault('reason_codebook_version',REASON_VERSION)
        self.service.access.validate_protocol(protocol)
        selected=[];missing=[]
        for row in status['records']:
            rid=row['record_id'];event=row['event']
            if row['status']=='not_retrieved':missing.append({'parent_record_id':rid,'reason':event['reason'],'retrieval_event_hash':event['event_hash']});continue
            document=event['document'];validate_snapshot(document)
            raw=self.store.artifact(audit['events'][0]['project_id'],document['blob']).read_bytes()
            if sha(raw)!=document['file_sha256']:raise ValueError('全文原件哈希不匹配')
            bib={k:v for k,v in records[rid]['record'].items() if k in ('title','abstract','pmid','doi','authors','journal','pub_date')}
            selected.append({**bib,'parent_review_id':review,'parent_record_id':rid,'report_id':review+':'+rid,
                'parent_record_sha256':records[rid]['record_sha256'],'parent_decision_hash':decisions[rid],
                'fulltext':document,'retrieval_event_hash':event['event_hash']})
        if not selected:raise ValueError('没有取得全文的报告，保留取得记录，不创建空筛选批次')
        source={'method':'fulltext_manifest','records':selected,'lineage':{'parent_review_id':review,'parent_event_hash':audit['events'][-1]['event_hash'],
                'reports_sought':len(records),'reports_retrieved':len(selected),'reports_not_retrieved':missing,'retrieval_events':status['events']}}
        if len(canonical(source).encode())>10_000_000:raise ValueError('全文批次快照超过10MB，请缩小批次')
        project=audit['events'][0]['project_id'];name=self.store.save(project,uuid.uuid4().hex+'-fulltext.json',source)
        child=self.service.ledger.prepare(project,name,protocol,actor,identity_assurance='scoped_reviewer_token')
        return {'review':child,'source_artifact':name,'reports_not_retrieved':len(missing)}
    def file(self,review,record_id,actor):
        events=self.service.events(review,actor);draft=events[0]['data']
        if draft['protocol']['stage']!='full_text' or (actor!=draft['protocol']['human_reviewer'] and not any(e['kind']=='approved' for e in events)):raise ValueError('全文批次尚未批准')
        item=next((r for r in draft['records'] if r['record_id']==record_id),None)
        if item is None:raise ValueError('记录不存在')
        document=item['record']['fulltext'];validate_snapshot(document)
        raw=self.store.artifact(events[0]['project_id'],document['blob']).read_bytes()
        if sha(raw)!=document['file_sha256']:raise ValueError('全文原件哈希不匹配')
        return {'filename':document['filename'],'content_base64':base64.b64encode(raw).decode(),'file_sha256':document['file_sha256']}
