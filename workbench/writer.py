"""Single-owner local manuscript versions; evidence matching is not semantic verification."""
import json
import re
import uuid
from .core import canonical, now
from .fulltext import snapshot, validate_snapshot, validate_evidence, json_hash, sha


def text(value, limit=4000):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise ValueError('文本为空或超过长度限制')
    return value.strip()


def citation_check(sections, evidence):
    known={e['id'] for e in evidence}; blockers=[]; warnings=[]
    for section in sections:
        body=section['body']; ids=re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]',body)
        unknown=sorted(set(ids)-known)
        if unknown:blockers.append(section['title']+'：未知证据 '+', '.join(unknown))
        if not ids:blockers.append(section['title']+'：尚无证据引用')
        if '[E:' in re.sub(r'\[E:[A-Za-z0-9_-]{1,40}\]','',body):blockers.append(section['title']+'：引用格式错误')
        if '[待补证据]' in body:blockers.append(section['title']+'：存在待补证据')
        for paragraph in body.split('\n\n'):
            if paragraph.strip() and not re.search(r'\[E:[A-Za-z0-9_-]{1,40}\]',paragraph):
                warnings.append(section['title']+'：无引用段落，请人工核对'+('（含数字）' if re.search(r'\d',paragraph) else ''))
    return {'blockers':blockers,'warnings':warnings,'semantic_support':'requires_human_review','rule_version':'writer-citations-v1'}


class WriterService:
    def __init__(self,store):
        self.store=store
        with store.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS writer_objects(project TEXT,id TEXT,kind TEXT,artifact TEXT,digest TEXT,created TEXT,PRIMARY KEY(project,id));
            CREATE TABLE IF NOT EXISTS writer_heads(project TEXT,id TEXT,version TEXT,PRIMARY KEY(project,id));
            CREATE TABLE IF NOT EXISTS writer_reviews(project TEXT,version TEXT,sequence INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT);''')

    def load(self,project,id,kind=None):
        self.store.project(project)
        with self.store.db() as db:row=db.execute('SELECT kind,artifact,digest FROM writer_objects WHERE project=? AND id=?',(project,id)).fetchone()
        if not row or (kind and row[0]!=kind):raise ValueError('对象不属于此项目或类型错误')
        obj=json.loads(self.store.artifact(project,row[1]).read_text())
        if json_hash(obj)!=row[2]:raise ValueError('写作快照哈希不匹配')
        return obj

    def persist(self,project,kind,data,db=None):
        id=uuid.uuid4().hex; obj={**data,'id':id,'kind':kind,'project':project,'created':now(),'actor':'local_owner','identity_assurance':'single_owner_access_token'}
        name='writer-'+id+'.json';self.store.save(project,name,obj)
        args=(project,id,kind,name,json_hash(obj),obj['created'])
        if db is not None:db.execute('INSERT INTO writer_objects VALUES(?,?,?,?,?,?)',args)
        else:
            with self.store.db() as conn:conn.execute('INSERT INTO writer_objects VALUES(?,?,?,?,?,?)',args)
        return obj

    def document(self,project,filename,content_base64,source,classification,confirmed):
        self.store.project(project)
        if classification not in ('public','synthetic') or confirmed is not True:raise ValueError('仅接收确认可本地使用的公开/合成材料')
        source=text(source,2000)
        doc=snapshot(self.store,project,filename,content_base64)
        return self.persist(project,'document',{'source':source,'classification':classification,'snapshot':doc,'origin':'manual_upload','screening_inclusion':'not_asserted'})

    def verify_document(self,project,id):
        obj=self.load(project,id,'document');doc=obj['snapshot'];validate_snapshot(doc)
        if sha(self.store.artifact(project,doc['blob']).read_bytes())!=doc['file_sha256']:raise ValueError('原文文件已变化')
        if obj.get('origin')=='native_statistics':
            from .writer_statistics import verify
            verify(self.store,project,obj)
        if obj.get('origin')=='native_hunter':
            from .writer_hunter import verify
            verify(self.store,project,obj)
        return obj

    def evidence(self,project,label,items,parent_id=None):
        self.store.project(project);label=text(label,200)
        if parent_id:self.load(project,parent_id,'evidence')
        if not isinstance(items,list) or not 1<=len(items)<=30:raise ValueError('每包须有1至30项证据')
        seen=set();frozen=[]
        for item in items:
            if not isinstance(item,dict) or set(item)!={'id','document_id','locator','excerpt','support_note','verified_by','report_id','study_ids'}:raise ValueError('证据字段不完整')
            eid=item['id']
            if not isinstance(eid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',eid) or eid in seen:raise ValueError('证据ID无效或重复')
            seen.add(eid);doc=self.verify_document(project,item['document_id'])
            validate_evidence({'fulltext':doc['snapshot']},item['locator'],item['excerpt'])
            for field in ('support_note','verified_by'):text(item[field],2000)
            if not isinstance(item['report_id'],str) or len(item['report_id'])>200:raise ValueError('报告ID无效')
            if not isinstance(item['study_ids'],list) or len(item['study_ids'])>20 or any(not isinstance(s,str) or not 1<=len(s)<=200 for s in item['study_ids']):raise ValueError('研究ID无效')
            frozen.append({**item,'document_sha256':json_hash(doc),'file_sha256':doc['snapshot']['file_sha256'],'text_sha256':doc['snapshot']['text_sha256'],'source':doc['source'],'classification':doc['classification'],'support_assurance':'human_declared','lineage_assurance':'manual_ids_not_linked_to_hunter'})
            if doc.get('origin')=='native_statistics':frozen[-1]['native_statistics']=doc['native_statistics']
            if doc.get('origin')=='native_hunter':
                b=doc['native_hunter']
                if item['report_id'] not in ('',b['report_id']) or item['study_ids'] not in ([],b['study_ids']):raise ValueError('手工报告/研究ID与Hunter原生映射冲突')
                frozen[-1].update(native_hunter=b,report_id=b['report_id'],study_ids=b['study_ids'],lineage_assurance='native_hunter_selected_version',captured_by=doc['captured_by'])
        if len(canonical(frozen))>60000:raise ValueError('证据包超过60000字符')
        return self.persist(project,'evidence',{'label':label,'items':frozen,'parent_id':parent_id})

    def verify_package(self,project,id):
        package=self.load(project,id,'evidence')
        for e in package['items']:
            doc=self.verify_document(project,e['document_id'])
            if json_hash(doc)!=e['document_sha256']:raise ValueError('原文版本不一致')
            validate_evidence({'fulltext':doc['snapshot']},e['locator'],e['excerpt'])
        return package

    def save(self,project,title,sections,evidence_id,manuscript_id=None,expected_version=None):
        title=text(title,300);package=self.verify_package(project,evidence_id)
        if not isinstance(sections,list) or not 1<=len(sections)<=30:raise ValueError('须有1至30个章节')
        clean=[]
        for s in sections:
            if not isinstance(s,dict) or set(s)!={'title','body'}:raise ValueError('章节须包含标题和正文')
            clean.append({'title':text(s['title'],300),'body':text(s['body'],60000)})
        if len(canonical(clean))>300000:raise ValueError('稿件超过300000字符')
        checks=citation_check(clean,package['items'])
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if manuscript_id:
                row=db.execute('SELECT version FROM writer_heads WHERE project=? AND id=?',(project,manuscript_id)).fetchone()
                if not row or row[0]!=expected_version:raise ValueError('稿件已更新或不属于此项目，请刷新后合并')
                self.load(project,expected_version,'manuscript')
            else:
                if expected_version is not None:raise ValueError('新稿不能指定旧版本')
                manuscript_id=uuid.uuid4().hex
            obj=self.persist(project,'manuscript',{'manuscript_id':manuscript_id,'parent_version':expected_version,'title':title,'sections':clean,'evidence_id':evidence_id,'evidence_sha256':json_hash(package),'checks':checks,'llm_calls':0,'origin':'manual_draft'},db)
            db.execute('INSERT OR REPLACE INTO writer_heads VALUES(?,?,?)',(project,manuscript_id,obj['id']))
        return obj

    def reviews(self,project,version):
        with self.store.db() as db:rows=db.execute('SELECT event FROM writer_reviews WHERE project=? AND version=? ORDER BY sequence',(project,version)).fetchall()
        events=[];previous=''
        for row in rows:
            event=json.loads(row[0]);body={k:v for k,v in event.items() if k!='hash'}
            if event['previous_hash']!=previous or json_hash(body)!=event['hash']:raise ValueError('审核记录已变化')
            events.append(event);previous=event['hash']
        return events

    def inspect(self,project,version):
        obj=self.load(project,version,'manuscript');package=self.verify_package(project,obj['evidence_id'])
        if json_hash(package)!=obj['evidence_sha256']:raise ValueError('证据包版本不一致')
        events=self.reviews(project,version)
        with self.store.db() as db:head=db.execute('SELECT version FROM writer_heads WHERE project=? AND id=?',(project,obj['manuscript_id'])).fetchone()[0]
        return {'manuscript':obj,'evidence':package,'reviews':events,'status':events[-1]['decision'] if events else 'needs_human_review','is_current':head==version}

    def review(self,project,version,decision,author,note,confirmed):
        if decision not in ('approved','changes_requested') or confirmed is not True:raise ValueError('请明确确认本版的作者审核')
        author=text(author,200);note=text(note,4000)
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');view=self.inspect(project,version)
            if not view['is_current']:raise ValueError('仅可审核当前版本')
            if decision=='approved' and view['manuscript']['checks']['blockers']:raise ValueError('先修复引用阻断项，再批准')
            events=view['reviews'];event={'version':version,'manuscript_sha256':json_hash(view['manuscript']),'decision':decision,'author':author,'note':note,'timestamp':now(),'actor':'local_owner','author_assurance':'owner_declared_name','support_confirmed':confirmed,'previous_hash':events[-1]['hash'] if events else ''}
            event['hash']=json_hash(event);db.execute('INSERT INTO writer_reviews(project,version,event) VALUES(?,?,?)',(project,version,canonical(event)))
        return event

    def export(self,project,version):
        view=self.inspect(project,version);m=view['manuscript'];used=set(re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]','\n'.join(s['body'] for s in m['sections'])))
        refs=[e for e in view['evidence']['items'] if e['id'] in used]
        label='已获作者批准' if view['status']=='approved' else '未批准草稿'
        md=f"# {m['title']}\n\n{label} · 版本 {version}\n\n"
        for s in m['sections']:md+=f"## {s['title']}\n\n{s['body']}\n\n"
        md+='## 引用证据\n\n'
        for e in refs:md+=f"- [E:{e['id']}] {e['source']}；{e['locator']}；原件 SHA256 {e['file_sha256']}\n  摘录：{e['excerpt']}\n"
        for e in refs:
            if e.get('native_statistics'):
                b=e['native_statistics'];md+=f"\n统计证据 [E:{e['id']}]：任务 {b['job_id']}；输入 SHA256 {b['payload_sha256']}；结果 SHA256 {b['artifact_sha256']}；仅合成数据。\n"
        for e in refs:
            if e.get('native_hunter'):
                b=e['native_hunter'];md+=f"\nHunter证据 [E:{e['id']}]：报告 {b['report_id']}；研究 {', '.join(b['study_ids'])}（限批次 {b['review_id']}）；裁决版本 {b['screening_event_hash']}；映射版本 {b['mapping_event_hash']}。\n"
        bundle={**view,'exported_at':now(),'markdown':md,'references':refs,'llm_calls':0,'format':'local_markdown_and_audit_json_no_translation'}
        obj=self.persist(project,'export',bundle)
        return obj

    def export_word(self,project,version):
        import base64
        from .writer_docx import render
        bundle=self.export(project,version)
        try:raw=render(bundle)
        except ValueError:raise ValueError('正文含Word不支持的控制字符，请修订后导出')
        filename='manuscript-'+version+'-'+bundle['id']+'.docx'
        target=self.store.artifact(project,filename)
        with target.open('xb') as f:f.write(raw)
        target.chmod(0o600)
        digest=sha(raw)
        manifest=self.persist(project,'word_export',{'version':version,'audit_export_id':bundle['id'],'audit_sha256':json_hash(bundle),'filename':filename,'file_sha256':digest,'status':bundle['status'],'llm_calls':0,'translation':'none_saved_text_only'})
        return {'filename':filename,'content_base64':base64.b64encode(raw).decode(),'file_sha256':digest,'manifest':manifest,'audit':bundle}

    def capture_statistics(self,project,job_id,confirmed):
        from .writer_statistics import capture
        return capture(self,project,job_id,confirmed)

    def list(self,project):
        self.store.project(project)
        with self.store.db() as db:
            rows=db.execute('SELECT id,kind,created FROM writer_objects WHERE project=? ORDER BY created',(project,)).fetchall()
            heads=dict(db.execute('SELECT id,version FROM writer_heads WHERE project=?',(project,)))
        return {'objects':[{'id':r[0],'kind':r[1],'created':r[2]} for r in rows],'heads':heads}

    def dispatch(self,operation,body):
        fields={'capture_statistics':{'project','job_id','confirmed'},'document':{'project','filename','content_base64','source','classification','confirmed'},'evidence':{'project','label','items','parent_id'},'save':{'project','title','sections','evidence_id','manuscript_id','expected_version'},'inspect':{'project','version'},'review':{'project','version','decision','author','note','confirmed'},'export':{'project','version'},'export_word':{'project','version'},'load':{'project','id'}}
        if operation not in fields or set(body)!=fields[operation]:raise ValueError('写作请求字段不完整或包含未知字段')
        return getattr(self,operation)(**body)
