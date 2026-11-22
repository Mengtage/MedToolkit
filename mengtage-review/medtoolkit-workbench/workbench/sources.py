"""Immutable bibliographic source runs and explicitly selected collection versions."""
from datetime import datetime
import json
from .core import canonical,now
from .fulltext import json_hash
from .deduplication import normalize

META={'database','kind','query','searched_at','total_hits','complete','coverage_note'}

def validate_metadata(value,count):
    if not isinstance(value,dict) or set(value)!=META:raise ValueError('来源信息字段不完整')
    for key in ('database','query','searched_at','coverage_note'):
        if not isinstance(value[key],str) or not 1<=len(value[key].strip())<=8000:raise ValueError('需填写来源名称、检索式、时间和覆盖说明')
    if len(value['database'])>120:raise ValueError('来源名称最多120字符')
    if value['kind'] not in ('database','register'):raise ValueError('本版仅支持数据库或研究注册库；其他来源需独立流程')
    try:datetime.fromisoformat(value['searched_at'].replace('Z','+00:00'))
    except ValueError:raise ValueError('检索时间须为ISO日期或时间')
    hits=value['total_hits']
    if hits is not None and (type(hits) is not int or hits<count):raise ValueError('总命中数不得小于导入记录数；未知填null')
    if type(value['complete']) is not bool or (value['complete'] and hits!=count):raise ValueError('完整导入须明确总命中数等于记录数')

def records_valid(records):
    if not isinstance(records,list) or len(records)>1000:raise ValueError('每次最多1000条记录')
    allowed={'title','abstract','pmid','doi','authors','journal','pub_date','volume','issue','pages'}
    for record in records:
        if not isinstance(record,dict) or set(record)-allowed:raise ValueError('仅允许题名、摘要、PMID、DOI、作者、期刊和日期字段')
        if not isinstance(record.get('title'),str) or not record['title'].strip():raise ValueError('每条记录须有题名')
        for key,value in record.items():
            if key=='authors' and isinstance(value,list) and all(isinstance(v,str) for v in value):continue
            if not isinstance(value,str):raise ValueError('书目字段须为文本，作者可为文本列表')
        normalize(record)
    if len(canonical(records).encode())>2_000_000:raise ValueError('书目数据超过2MB')

class SourceService:
    def __init__(self,store):
        self.store=store
        with store.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS source_runs(project TEXT, id TEXT, artifact TEXT, digest TEXT, created TEXT, PRIMARY KEY(project,id))')
            db.execute('CREATE TABLE IF NOT EXISTS source_collections(project TEXT, id TEXT, artifact TEXT, digest TEXT, created TEXT, PRIMARY KEY(project,id))')
    def load(self,project,id,collection=False):
        self.store.project(project);table='source_collections' if collection else 'source_runs'
        with self.store.db() as db:row=db.execute(f'SELECT artifact,digest FROM {table} WHERE project=? AND id=?',(project,id)).fetchone()
        if row is None:raise ValueError('来源或集合不属于此项目')
        data=json.loads(self.store.artifact(project,row[0]).read_text())
        if json_hash(data)!=row[1]:raise ValueError('来源快照已变化')
        return data,{'id':id,'artifact':row[0],'sha256':row[1]}
    def persist(self,project,core,collection=False):
        self.store.project(project);sid=json_hash(core);table='source_collections' if collection else 'source_runs'
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute(f'SELECT artifact,digest FROM {table} WHERE project=? AND id=?',(project,sid)).fetchone()
            if old:
                existing=json.loads(self.store.artifact(project,old[0]).read_text())
                if json_hash(existing)!=old[1]:raise ValueError('已有快照校验失败')
                return {'id':sid,'artifact':old[0],'sha256':old[1],'reused':True}
            data={**core,'created':now(),'actor':'local_owner','identity_assurance':'single_owner_access_token'}
            name=('collection-' if collection else 'source-')+sid+'.json';self.store.save(project,name,data);digest=json_hash(data)
            db.execute(f'INSERT INTO {table} VALUES(?,?,?,?,?)',(project,sid,name,digest,data['created']))
        return {'id':sid,'artifact':name,'sha256':digest,'reused':False}
    def import_records(self,project,metadata,records,confirmed):
        if confirmed is not True:raise ValueError('请确认导入的是公开书目记录及其来源信息')
        records_valid(records);validate_metadata(metadata,len(records))
        return self.persist(project,{'method':'source_run','metadata':metadata,'records':records,'retrieved':len(records),
            'total_hits':metadata['total_hits'],'complete':metadata['complete'],'origin':'human_import','coverage_assurance':'human_declared'})
    def import_file(self,project,metadata,filename,content,confirmed):
        if confirmed is not True:raise ValueError('请确认导入的是公开书目文件及其来源信息')
        from .importers import parse_bibliographic_file
        records=parse_bibliographic_file(filename,content)
        meta=dict(metadata) if isinstance(metadata,dict) else {}
        if meta.get('complete') is True and meta.get('total_hits') is None:
            meta['total_hits']=len(records)
        records_valid(records);validate_metadata(meta,len(records))
        return self.persist(project,{'method':'source_run','metadata':meta,'records':records,'retrieved':len(records),
            'total_hits':meta['total_hits'],'complete':meta['complete'],'origin':'human_import','coverage_assurance':'human_declared'})
    def capture(self,project,source_artifact,confirmed):
        if confirmed is not True:raise ValueError('请确认登记这次检索')
        jobs=[j for j in self.store.jobs(project) if j['kind']=='search' and j['state']=='completed' and j['result'] and json.loads(j['result']).get('artifact')==source_artifact]
        if len(jobs)!=1:raise ValueError('请选择此项目已完成的原生检索产物')
        raw=json.loads(self.store.artifact(project,source_artifact).read_text());count=len(raw['records'])
        if raw['retrieved']!=count or type(raw['total_hits']) is not int or raw['total_hits']<count:raise ValueError('原检索数量不一致')
        allowed={'title','abstract','pmid','doi','authors','journal','pub_date','volume','issue','pages'}
        cleaned=[]
        for r in raw['records']:
            if not isinstance(r,dict):raise ValueError('检索记录格式无效')
            rec={}
            for k in allowed:
                v=r.get(k)
                if v is None:continue
                if k=='authors' and isinstance(v,list):
                    rec[k]=[str(a) for a in v if str(a).strip()]
                elif str(v).strip():
                    rec[k]=str(v).strip()
            if 'title' not in rec and isinstance(r.get('title'),str):
                rec['title']=r['title']
            cleaned.append(rec)
        records_valid(cleaned)
        db_name=raw.get('database') or 'PubMed'
        source_kind='register' if db_name=='ClinicalTrials.gov' else 'database'
        meta={'database':db_name,'kind':source_kind,'query':raw['query'],'searched_at':jobs[0]['created'],'total_hits':raw['total_hits'],
            'complete':raw['complete'],'coverage_note':'原生检索任务 '+jobs[0]['id']+'；时间为任务创建时间，非数据库更新时间'}
        validate_metadata(meta,count)
        return self.persist(project,{'method':'source_run','metadata':meta,'records':cleaned,'retrieved':count,'total_hits':raw['total_hits'],'complete':raw['complete'],
            'origin':'native_pubmed','coverage_assurance':'native_response_count','original_artifact':source_artifact,'original_sha256':json_hash(raw)})
    def create(self,project,label,source_ids,parent_id,reason,confirmed):
        if confirmed is not True:raise ValueError('请确认本轮完整来源清单')
        if not isinstance(label,str) or not 1<=len(label.strip())<=200 or not isinstance(reason,str) or not 1<=len(reason.strip())<=2000:raise ValueError('需集合名称及建版/修订理由')
        if not isinstance(source_ids,list) or not 1<=len(source_ids)<=50 or any(not isinstance(i,str) for i in source_ids) or len(set(source_ids))!=len(source_ids):raise ValueError('请选择1至50个不同来源快照')
        parent=None
        if parent_id is not None:
            _,parent=self.load(project,parent_id,True)
        runs=[];records=[];origins=[]
        for sid in sorted(source_ids):
            run,ref=self.load(project,sid);runs.append({**ref,'metadata':run['metadata'],'record_count':len(run['records'])})
            for index,record in enumerate(run['records'],1):records.append(record);origins.append({'source_id':sid,'source_record_index':index,'source_sha256':ref['sha256']})
        if not records or len(records)>1000:raise ValueError('合并原始记录须为1至1000条；不要先分别筛选再相加')
        hits=[r['metadata']['total_hits'] for r in runs];complete=all(r['metadata']['complete'] for r in runs)
        core={'method':'source_collection','label':label.strip(),'reason':reason.strip(),'sources':runs,'parent_collection':parent,
            'records':records,'record_origins':origins,'retrieved':len(records),'total_hits':sum(hits) if all(v is not None for v in hits) else None,'complete':complete,
            'policy':'explicit_full_source_selection; no_screening_decisions_inherited'}
        if len(canonical(core).encode())>10_000_000:raise ValueError('来源集合超过10MB')
        return self.persist(project,core,True)
    def list(self,project):
        self.store.project(project);result={}
        for table,key in [('source_runs','runs'),('source_collections','collections')]:
            with self.store.db() as db:ids=[r[0] for r in db.execute(f'SELECT id FROM {table} WHERE project=? ORDER BY created',(project,))]
            rows=[]
            for sid in ids:
                data,ref=self.load(project,sid,key=='collections');rows.append({**ref,**{k:data.get(k) for k in ('metadata','retrieved','total_hits','complete','label','parent_collection','created')},'source_ids':[s['id'] for s in data.get('sources',[])]})
            result[key]=rows
        result['searches']=[{'artifact':json.loads(j['result'])['artifact'],'created':j['created']} for j in self.store.jobs(project) if j['kind']=='search' and j['state']=='completed' and j['result']]
        return result

def collection_accounting(store,project,source):
    rows=[];records=[];origins=[];seen=set()
    for ref in source['sources']:
        if ref['id'] in seen:raise ValueError('来源集合重复包含同一快照')
        seen.add(ref['id']);run=json.loads(store.artifact(project,ref['artifact']).read_text())
        if json_hash(run)!=ref['sha256'] or run['metadata']!=ref['metadata'] or len(run['records'])!=ref['record_count']:raise ValueError('来源快照无法核验')
        validate_metadata(run['metadata'],len(run['records']))
        if run.get('origin')=='native_pubmed':
            raw=json.loads(store.artifact(project,run['original_artifact']).read_text())
            if json_hash(raw)!=run['original_sha256']:raise ValueError('原生检索来源已变化')
        rows.append({'source_id':ref['id'],'source_sha256':ref['sha256'],**run['metadata'],'retrieved':len(run['records']),'coverage_assurance':run['coverage_assurance']})
        for i,record in enumerate(run['records'],1):records.append(record);origins.append({'source_id':ref['id'],'source_record_index':i,'source_sha256':ref['sha256']})
    if not rows or records!=source['records'] or origins!=source['record_origins'] or len(records)!=source['retrieved']:raise ValueError('集合记录与来源位置不一致')
    hits=[r['total_hits'] for r in rows];total=sum(hits) if all(v is not None for v in hits) else None;complete=all(r['complete'] for r in rows)
    if source['total_hits']!=total or source['complete']!=complete:raise ValueError('集合覆盖计数不一致')
    return {'source_breakdown':rows,'search_total_hits':total,'records_not_downloaded':total-len(records) if total is not None else None,
        'search_complete':complete,'collection':{'label':source['label'],'parent_collection':source['parent_collection'],'reason':source['reason']},
        'issues':[] if complete else ['部分来源未取全或命中数未知；此集合不代表完整检索。']}
