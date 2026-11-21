"""Single-owner local manuscript versions with medical SCI writing validation and Vancouver citation rendering."""
import json
import re
import uuid
from .core import canonical, now
from .fulltext import snapshot, validate_snapshot, validate_evidence, json_hash, sha


SECTION_KINDS = [
    ('abstract', ('摘要', 'abstract', 'summary')),
    ('keywords', ('关键词', '关键字', 'keywords', 'key words')),
    ('introduction', ('引言', '前言', '背景', 'introduction', 'background')),
    ('methods', ('方法', '资料与方法', '研究方法', '检索策略', '纳入与排除', 'methods', 'materials and methods', 'methodology', 'search strategy', 'eligibility')),
    ('results', ('结果', '研究结果', 'results', 'findings')),
    ('discussion', ('讨论', 'discussion')),
    ('limitations', ('局限', '局限性', 'limitations', 'strengths and limitations')),
    ('conclusion', ('结论', '结语', 'conclusion', 'conclusions')),
    ('declarations', ('声明', '致谢', '利益冲突', '伦理', '资助', '数据可用性', '作者贡献', '缩略语', 'declarations', 'acknowledgements', 'competing interests', 'conflict of interest', 'funding', 'data availability', 'ethics', 'author contributions', 'abbreviations')),
]

NON_CITING_KINDS = {'abstract', 'keywords', 'conclusion', 'declarations'}
OPTIONAL_CITING_KINDS = {'methods', 'limitations'}

INTERNAL_JARGON_RE = re.compile(
    r'(?:/api/\w+|/sources\b|/screening\b|/studies\b|/writer\b|\bselected_lineage_complete\b|\btableone\b|\bcategorical_auto\b|\bprediction_evaluation_extended\b|\bmengtage-owner\b|\baria-gemini-reviewer\b|\bstudy_pmid_\w+)'
)

AI_TEMPLATE_AND_OVERCLAIM_RE = re.compile(
    r'(?:全面赋能|生态底座|阶段门|显著赋能|完全治愈|无任何副作用|首次证明)'
)


def infer_section_kind(title):
    t = (title or '').strip().lower()
    for kind, keywords in SECTION_KINDS:
        if any(k in t for k in keywords):
            return kind
    return 'other'


def text(value, limit=4000):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise ValueError('文本为空或超过长度限制')
    return value.strip()


def _author_name(a):
    if isinstance(a, str):
        return a.strip().rstrip('.')
    if isinstance(a, dict):
        if a.get('collective_name') or a.get('CollectiveName'):
            return str(a.get('collective_name') or a.get('CollectiveName')).strip()
        last = a.get('last_name') or a.get('LastName') or a.get('last') or ''
        init = a.get('initials') or a.get('Initials') or a.get('first') or ''
        return ' '.join(p for p in (last, init) if p).strip() or str(a.get('name', '')).strip()
    return str(a).strip()


def format_vancouver_reference(item):
    """Format an evidence item into ICMJE / NLM Vancouver bibliographic style."""
    bib = item.get('bibliographic') or {}
    title = (bib.get('title') or '').strip()
    if not title:
        src = (item.get('source') or '').strip()
        return src if src.endswith('.') else src + '.'
    raw_authors = bib.get('authors') or []
    if isinstance(raw_authors, str):
        names = [x.strip() for x in raw_authors.split(',') if x.strip()]
    elif isinstance(raw_authors, list):
        names = [x for x in (_author_name(a) for a in raw_authors) if x]
    else:
        names = []
    if len(names) > 6:
        author_part = ', '.join(names[:6]) + ', et al.'
    elif names:
        author_part = ', '.join(names) + '.'
    else:
        author_part = ''
    title_part = title if title[-1] in '.?!' else title + '.'
    journal = (bib.get('journal') or '').strip().rstrip('.')
    journal_part = (journal + '.') if journal else ''
    pub_date = str(bib.get('pub_date') or '').strip()
    m_year = re.search(r'(19|20)\d{2}', pub_date)
    year = m_year.group(0) if m_year else pub_date
    vol = str(bib.get('volume') or '').strip()
    issue = str(bib.get('issue') or '').strip()
    pages = str(bib.get('pages') or '').strip()
    loc = year
    if vol:
        loc += f';{vol}' + (f'({issue})' if issue else '') + (f':{pages}' if pages else '')
    elif pages:
        loc += f':{pages}'
    loc_part = (loc + '.') if loc else ''
    doi = (bib.get('doi') or '').strip().rstrip('.')
    doi_part = f'doi:{doi}.' if doi else ''
    pmid = str(bib.get('pmid') or '').strip()
    pmid_part = f'PMID: {pmid}.' if pmid else ''
    return ' '.join(p for p in (author_part, title_part, journal_part, loc_part, doi_part, pmid_part) if p)


def _compress_ranges(nums):
    if not nums:
        return ''
    nums = sorted(set(nums))
    ranges = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f'{start}' if start == prev else f'{start},{prev}' if prev == start + 1 else f'{start}–{prev}')
            start = prev = n
    ranges.append(f'{start}' if start == prev else f'{start},{prev}' if prev == start + 1 else f'{start}–{prev}')
    return '[' + ','.join(ranges) + ']'


def order_citations(sections, evidence_items):
    """Map bibliographic evidence IDs to sequential Vancouver numbers by first appearance in text."""
    by_id = {e['id']: e for e in evidence_items}
    bib_numbers = {}
    bib_refs = []
    stat_ids = set()
    used_ids = []
    for s in sections:
        for eid in re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]', s['body']):
            if eid not in by_id:
                continue
            if eid not in used_ids:
                used_ids.append(eid)
            item = by_id[eid]
            if item.get('origin') == 'native_statistics' or item.get('native_statistics'):
                stat_ids.add(eid)
            elif eid not in bib_numbers:
                bib_numbers[eid] = len(bib_numbers) + 1
                bib_refs.append(item)
    return bib_numbers, bib_refs, stat_ids, used_ids


CLUSTER_RE = re.compile(r'\[E:[A-Za-z0-9_-]{1,40}\](?:[\s,，;；、]*\[E:[A-Za-z0-9_-]{1,40}\])*')


def render_academic_text(body, bib_numbers, stat_ids):
    """Replace [E:id] clusters with Vancouver numeric citations [1], [2–4] and strip statistical job tags from prose."""
    def _replace(match):
        cluster = match.group(0)
        eids = re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]', cluster)
        nums = [bib_numbers[eid] for eid in eids if eid in bib_numbers and eid not in stat_ids]
        if not nums:
            return ''
        return _compress_ranges(nums)
    out = CLUSTER_RE.sub(_replace, body)
    out = re.sub(r'[ \t]+([，。；：！？,.;:!?])', r'\1', out)
    out = re.sub(r'[ \t]{2,}', ' ', out)
    return out


SELF_DISCOURSE_RE = re.compile(
    r'(?:本研究|本范围综述|本综述|本文|表\s*[1-9]|图\s*[1-9]|Table\s*[1-9]|Figure\s*[1-9]|研究问题|未来研究|检索共识别|初筛阶段|全文复筛|探索了|致力于|涵盖了|方向：|如下：)'
)


def _is_non_prose_block(p_strip):
    if p_strip.startswith(('#', '### ', '#### ', '|', '表', '图', '**表', '**图', '*注', '注：', 'Note:', '*Note:', '- ', '* ', '1. ', '2. ', '3. ', '4. ')):
        return True
    if SELF_DISCOURSE_RE.search(p_strip):
        return True
    lines = [ln.strip() for ln in p_strip.splitlines() if ln.strip()]
    if lines and all(ln.startswith('|') and ln.endswith('|') for ln in lines):
        return True
    return False


def citation_check(sections, evidence):
    known={e['id'] for e in evidence}; blockers=[]; warnings=[]
    all_ids=[eid for s in sections for eid in re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]',s['body'])]
    multi_section=len(sections)>1
    for section in sections:
        body=section['body']; title=section['title']; kind=infer_section_kind(title)
        ids=re.findall(r'\[E:([A-Za-z0-9_-]{1,40})\]',body)
        unknown=sorted(set(ids)-known)
        if unknown:blockers.append(title+'：未知证据 '+', '.join(unknown))
        if not ids:
            if not multi_section or (kind not in NON_CITING_KINDS and kind not in OPTIONAL_CITING_KINDS):
                if not all_ids or kind not in (NON_CITING_KINDS | OPTIONAL_CITING_KINDS):
                    blockers.append(title+'：尚无证据引用')
        if kind in ('abstract','keywords') and ids:
            warnings.append(title+'：按医学SCI规范，摘要与关键词不应包含文献引用')
        if '[E:' in re.sub(r'\[E:[A-Za-z0-9_-]{1,40}\]','',body):blockers.append(title+'：引用格式错误')
        if '[待补证据]' in body or '[待引用' in body:blockers.append(title+'：存在待补证据')
        if re.search(r'\b[Pp]\s*=\s*0\.000+\b',body):
            warnings.append(title+'：统计P值不应写作P=0.000，按医学SCI规范应写为P<0.001')
        if INTERNAL_JARGON_RE.search(body):
            warnings.append(title+'：正文疑似包含工作台内部路由或变量标识符，请改为规范学术表述')
        if AI_TEMPLATE_AND_OVERCLAIM_RE.search(body):
            warnings.append(title+'：正文包含AI模板腔或过度因果/绝对化表述，请按证据强度降级表述')
        if kind not in NON_CITING_KINDS and kind not in OPTIONAL_CITING_KINDS:
            for paragraph in body.split('\n\n'):
                p_strip=paragraph.strip()
                if p_strip and not _is_non_prose_block(p_strip) and not re.search(r'\[E:[A-Za-z0-9_-]{1,40}\]',p_strip):
                    warnings.append(title+'：无引用段落，请人工核对'+('（含数字）' if re.search(r'\d',p_strip) else ''))
    if not all_ids and not any('尚无证据引用' in b for b in blockers):
        blockers.append(sections[0]['title']+'：尚无证据引用')
    return {'blockers':blockers,'warnings':warnings,'semantic_support':'requires_human_review','rule_version':'writer-citations-sci-v2'}


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
        if not isinstance(items,list) or not 1<=len(items)<=200:raise ValueError('每包须有1至200项证据')
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
            frozen.append({**item,'origin':doc.get('origin','manual_upload'),'document_sha256':json_hash(doc),'file_sha256':doc['snapshot']['file_sha256'],'text_sha256':doc['snapshot']['text_sha256'],'source':doc['source'],'classification':doc['classification'],'support_assurance':'human_declared','lineage_assurance':'manual_ids_not_linked_to_hunter'})
            if doc.get('bibliographic'):frozen[-1]['bibliographic']=doc['bibliographic']
            if doc.get('origin')=='native_statistics':frozen[-1]['native_statistics']=doc['native_statistics']
            if doc.get('origin')=='native_hunter':
                b=doc['native_hunter']
                if item['report_id'] not in ('',b['report_id']) or item['study_ids'] not in ([],b['study_ids']):raise ValueError('手工报告/研究ID与Hunter原生映射冲突')
                frozen[-1].update(native_hunter=b,report_id=b['report_id'],study_ids=b['study_ids'],lineage_assurance='native_hunter_selected_version',captured_by=doc['captured_by'])
        if len(canonical(frozen))>500000:raise ValueError('证据包超过500000字符')
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
        if len(canonical(clean))>600000:raise ValueError('稿件超过600000字符')
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
        view=self.inspect(project,version);m=view['manuscript']
        bib_numbers,bib_refs,stat_ids,used_ids=order_citations(m['sections'],view['evidence']['items'])
        used=set(used_ids)
        refs=[e for e in view['evidence']['items'] if e['id'] in used]
        label='已获作者批准' if view['status']=='approved' else '未批准草稿'
        academic_md=f"# {m['title']}\n\n"
        for s in m['sections']:
            rendered_body=render_academic_text(s['body'],bib_numbers,stat_ids)
            academic_md+=f"## {s['title']}\n\n{rendered_body}\n\n"
        if bib_refs:
            academic_md+='## 参考文献 (References)\n\n'
            for idx,e in enumerate(bib_refs,1):
                academic_md+=f"{idx}. {format_vancouver_reference(e)}\n"
            academic_md+='\n'
        audit_md=f"---\n\n## 附录：工作台证据溯源与作者审核记录\n\n{label} · 版本 {version}\n\n"
        for e in refs:
            v_num=f" → [{bib_numbers[e['id']]}]" if e['id'] in bib_numbers else ''
            audit_md+=f"- [E:{e['id']}]{v_num} {e['source']}；{e['locator']}；原件 SHA256 {e['file_sha256']}\n  摘录：{e['excerpt']}\n"
        for e in refs:
            if e.get('native_statistics'):
                b=e['native_statistics'];audit_md+=f"\n统计证据 [E:{e['id']}]：任务 {b['job_id']}；输入 SHA256 {b['payload_sha256']}；结果 SHA256 {b['artifact_sha256']}；仅合成数据。\n"
        for e in refs:
            if e.get('native_hunter'):
                b=e['native_hunter'];audit_md+=f"\nHunter证据 [E:{e['id']}]：报告 {b['report_id']}；研究 {', '.join(b['study_ids'])}（限批次 {b['review_id']}）；裁决版本 {b['screening_event_hash']}；映射版本 {b['mapping_event_hash']}。\n"
        md=academic_md+audit_md
        bundle={**view,'exported_at':now(),'markdown':md,'academic_markdown':academic_md.strip()+'\n','references':refs,'vancouver_references':[{'number':i,'evidence_id':e['id'],'citation':format_vancouver_reference(e)} for i,e in enumerate(bib_refs,1)],'llm_calls':0,'format':'local_markdown_and_audit_json_no_translation'}
        obj=self.persist(project,'export',bundle)
        return obj

    def export_word(self,project,version):
        import base64
        from .writer_docx import render
        bundle=self.export(project,version)
        try:
            raw=render(bundle,include_audit_appendix=True)
            academic_raw=render(bundle,include_audit_appendix=False)
        except ValueError:raise ValueError('正文含Word不支持的控制字符，请修订后导出')
        filename='manuscript-'+version+'-'+bundle['id']+'.docx'
        target=self.store.artifact(project,filename)
        with target.open('xb') as f:f.write(raw)
        target.chmod(0o600)
        digest=sha(raw)
        manifest=self.persist(project,'word_export',{'version':version,'audit_export_id':bundle['id'],'audit_sha256':json_hash(bundle),'filename':filename,'file_sha256':digest,'academic_file_sha256':sha(academic_raw),'status':bundle['status'],'llm_calls':0,'translation':'none_saved_text_only'})
        return {'filename':filename,'content_base64':base64.b64encode(raw).decode(),'academic_content_base64':base64.b64encode(academic_raw).decode(),'file_sha256':digest,'manifest':manifest,'audit':bundle}

    def capture_statistics(self,project,job_id,confirmed):
        from .writer_statistics import capture
        return capture(self,project,job_id,confirmed)

    def list(self,project):
        self.store.project(project)
        with self.store.db() as db:
            rows=db.execute('SELECT id,kind,created,artifact FROM writer_objects WHERE project=? ORDER BY created',(project,)).fetchall()
            heads=dict(db.execute('SELECT id,version FROM writer_heads WHERE project=?',(project,)))
            reviews={}
            for v,ev in db.execute('SELECT version,event FROM writer_reviews WHERE project=? ORDER BY sequence',(project,)):
                try:reviews[v]=json.loads(ev).get('decision')
                except Exception:pass
        objects=[]
        for oid,kind,created,artifact in rows:
            item={'id':oid,'kind':kind,'created':created}
            try:
                data=json.loads(self.store.artifact(project,artifact).read_text())
                if kind=='document':
                    fname=data.get('snapshot',{}).get('filename','')
                    src=data.get('source','')
                    item['label']=f"{fname+' · ' if fname else ''}{src} · {oid[:8]}"
                elif kind=='evidence':
                    item['label']=f"{data.get('label','')}（{len(data.get('items',[]))}项） · {oid[:8]}"
                elif kind=='manuscript':
                    status={'approved':'已批准','changes_requested':'需修改'}.get(reviews.get(oid),'待审核')
                    head='当前' if heads.get(data.get('manuscript_id'))==oid else '历史'
                    item['label']=f"{data.get('title','')} · {status} · {head} · {oid[:8]}"
            except Exception:
                pass
            objects.append(item)
        return {'objects':objects,'heads':heads}

    def dispatch(self,operation,body):
        fields={'capture_statistics':{'project','job_id','confirmed'},'document':{'project','filename','content_base64','source','classification','confirmed'},'evidence':{'project','label','items','parent_id'},'save':{'project','title','sections','evidence_id','manuscript_id','expected_version'},'inspect':{'project','version'},'review':{'project','version','decision','author','note','confirmed'},'export':{'project','version'},'export_word':{'project','version'},'load':{'project','id'}}
        if operation not in fields or set(body)!=fields[operation]:raise ValueError('写作请求字段不完整或包含未知字段')
        return getattr(self,operation)(**body)
