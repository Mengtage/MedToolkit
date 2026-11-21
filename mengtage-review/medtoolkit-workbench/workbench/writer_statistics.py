"""Bind a completed native MedStat job using its completion-time hashes."""
import base64,json
from .core import canonical
from .fulltext import sha,snapshot


def load(store,project,job_id):
    store.project(project)
    with store.db() as db:
        row=db.execute('SELECT kind,state,payload,result FROM jobs WHERE project=? AND id=?',(project,job_id)).fetchone()
    if not row or row[0]!='statistics' or row[1]!='completed':raise ValueError('请选择当前项目已完成的MedStat任务')
    payload=json.loads(row[2]);result=json.loads(row[3])
    if payload.get('classification')!='synthetic':raise ValueError('当前仅接合成统计证据')
    if not result.get('artifact_sha256') or not result.get('payload_sha256'):raise ValueError('旧任务缺少完成时哈希；请新建合成分析任务后引用')
    if sha(canonical(payload).encode())!=result['payload_sha256']:raise ValueError('分析任务输入已变化')
    raw=store.artifact(project,result['artifact']).read_bytes()
    if sha(raw)!=result['artifact_sha256']:raise ValueError('统计产物与完成时哈希不一致')
    data=json.loads(raw)
    if (data.get('requested_method') or data.get('method'))!=payload['method']:raise ValueError('分析方法与任务输入不一致')
    binding={'job_id':job_id,'artifact':result['artifact'],'artifact_sha256':result['artifact_sha256'],'payload_sha256':result['payload_sha256'],'method':payload['method'],'classification':'synthetic','analysis_input_sha256':data.get('input_sha256'),'environment':data.get('environment',{})}
    return data,binding


def capture(service,project,job_id,confirmed):
    if confirmed is not True:raise ValueError('请确认将此合成分析结果作为写作材料，统计含义仍需作者核对')
    data,binding=load(service.store,project,job_id)
    content=json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).encode()
    doc=snapshot(service.store,project,'medstat-'+job_id+'.txt',base64.b64encode(content).decode())
    return service.persist(project,'document',{'source':'MedStat '+binding['method']+' · synthetic · '+job_id,'classification':'synthetic','snapshot':doc,'origin':'native_statistics','native_statistics':binding,'screening_inclusion':'not_applicable'})


def verify(store,project,obj):
    _,binding=load(store,project,obj['native_statistics']['job_id'])
    if binding!=obj['native_statistics']:raise ValueError('统计任务绑定已变化')
