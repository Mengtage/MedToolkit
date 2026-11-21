"""Single-owner loopback preview. External TLS/auth gateway required for deployment."""
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from .core import ROOT


def serve(store,port=8765):
    token=os.environ.get('WORKBENCH_ACCESS_TOKEN','')
    if len(token)<32:raise ValueError('WORKBENCH_ACCESS_TOKEN至少32字符，须在服务端配置')
    from .screening_http import ScreeningService
    screening=ScreeningService(store)
    from .sources import SourceService
    sources=SourceService(store)
    from .writer import WriterService
    writer=WriterService(store)
    worker=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,value,content_type='application/json; charset=utf-8'):
            raw=value.encode() if isinstance(value,str) else json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization','').encode('utf-8'),('Bearer '+token).encode('utf-8'))
        def do_GET(self):
            path=urlparse(self.path)
            static={'/writer':('writer.html','text/html; charset=utf-8'),'/writer.js':('writer.js','text/javascript; charset=utf-8'),'/evaluation.js':('evaluation.js','text/javascript; charset=utf-8'),'/sources':('sources.html','text/html; charset=utf-8'),'/sources.js':('sources.js','text/javascript; charset=utf-8'),'/studies.js':('studies.js','text/javascript; charset=utf-8'),'/fulltext.js':('fulltext.js','text/javascript; charset=utf-8'),'/screening':('screening.html','text/html; charset=utf-8'),'/screening.js':('screening.js','text/javascript; charset=utf-8'),'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css')}
            if path.path in static:
                name,mime=static[path.path];return self.reply(200,(ROOT/'web'/name).read_text(),mime)
            if path.path.startswith('/api/review/'):
                principal=screening.access.authenticate(self.headers.get('Authorization','').removeprefix('Bearer '))
                if not principal:return self.reply(401,{'error':'需要有效的独立评审令牌'})
                if path.path=='/api/review/identity':return self.reply(200,principal)
                if path.path=='/api/review/list':return self.reply(200,screening.list(principal['actor']))
                return self.reply(404,{'error':'路径不存在'})
            if not self.authorized():return self.reply(401,{'error':'需要访问令牌'})
            try:
                q=parse_qs(path.query)
                if path.path=='/api/capabilities':return self.reply(200,{'search':True,'statistics':'synthetic_only','statistical_methods':['pearson','spearman','categorical_auto','chi2','fisher','yates','group_numeric','tableone','linear_regression','logistic_regression','prediction_evaluation','prediction_evaluation_extended','poisson_regression','gamma_regression','mice_imputation'],'writing':'not_configured' if not (os.environ.get('GEMINI_API_KEY') and os.environ.get('GEMINI_MODEL')) else 'configured','zotero':'ris_export'})
                if path.path=='/api/reviewers':return self.reply(200,screening.access.list())
                if path.path=='/api/sources':return self.reply(200,sources.list(q['project'][0]))
                if path.path=='/api/writer':return self.reply(200,writer.list(q['project'][0]))
                if path.path=='/api/projects':return self.reply(200,store.projects())
                if path.path=='/api/jobs':return self.reply(200,store.jobs(q['project'][0]))
                if path.path=='/api/export-ris':
                    from .exports import ris
                    data=json.loads(store.artifact(q['project'][0],q['name'][0]).read_text())
                    return self.reply(200,{'filename':'references.ris','content':ris(data['records'])})
                if path.path=='/api/artifact':
                    p=store.artifact(q['project'][0],q['name'][0]);return self.reply(200,json.loads(p.read_text()))
                self.reply(404,{'error':'路径不存在'})
            except (KeyError,ValueError,FileNotFoundError):self.reply(400,{'error':'项目或产物不存在'})
        def do_POST(self):
            reviewer_route=self.path.startswith('/api/review/')
            principal=screening.access.authenticate(self.headers.get('Authorization','').removeprefix('Bearer ')) if reviewer_route else None
            if reviewer_route and not principal:return self.reply(401,{'error':'需要有效的独立评审令牌'})
            if not reviewer_route and not self.authorized():return self.reply(401,{'error':'需要访问令牌'})
            # No CORS and JSON-only requests prevent browser form submissions.
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,{'error':'仅支持JSON'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=(8_000_000 if self.path in ('/api/review/fulltext_register','/api/sources/import_records','/api/writer/document') else 1_000_000):return self.reply(413,{'error':'请求大小超限'})
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('请求必须是JSON对象')
                if reviewer_route:
                    operation=self.path.removeprefix('/api/review/')
                    return self.reply(200,screening.dispatch(operation,body,principal))
                if self.path.startswith('/api/writer/'):
                    return self.reply(200,writer.dispatch(self.path.removeprefix('/api/writer/'),body))
                if self.path.startswith('/api/sources/'):
                    operation=self.path.removeprefix('/api/sources/')
                    fields={'import_records':{'project','metadata','records','confirmed'},'capture':{'project','source_artifact','confirmed'},'create':{'project','label','source_ids','parent_id','reason','confirmed'}}
                    if operation not in fields or set(body)!=fields[operation]:raise ValueError('来源请求字段无效')
                    return self.reply(201,getattr(sources,operation)(**body))
                if self.path=='/api/reviewers':
                    if set(body)!={'actor','role'}:raise ValueError('身份字段无效')
                    return self.reply(201,screening.access.issue(**body))
                if self.path=='/api/reviewers/revoke':
                    if set(body)!={'actor'}:raise ValueError('身份字段无效')
                    return self.reply(200,screening.access.revoke(body['actor']))
                if self.path=='/api/reviewers/rotate':
                    if set(body)!={'actor'}:raise ValueError('身份字段无效')
                    return self.reply(200,screening.access.rotate(body['actor']))
                if self.path=='/api/screening-prepare':
                    if set(body)!={'project','source_artifact','protocol'}:raise ValueError('方案字段无效')
                    return self.reply(201,screening.prepare(**body))
                for field in ('project','kind','id'):
                    if field in body and not isinstance(body[field],str):raise ValueError('标识必须是字符串')
                if self.path=='/api/dedup':
                    from .dedup_jobs import digest
                    pid=body['project'];name=body['source_artifact']
                    source=json.loads(store.artifact(pid,name).read_text())
                    payload={'source_artifact':name,'source_sha256':digest(source)}
                    kind='deduplicate'
                    if 'decision' in body:
                        kind='dedup_review'
                        payload.update({k:body[k] for k in ('candidate_index','decision','reason')})
                    return self.reply(201,{'id':store.enqueue(pid,kind,payload)})
                if self.path=='/api/projects':return self.reply(201,{'id':store.create(body['question'])})
                if self.path=='/api/jobs':return self.reply(201,{'id':store.enqueue(body['project'],body['kind'],body['payload'])})
                if self.path=='/api/retry':return self.reply(201,{'id':store.retry(body['id'],body.get('confirmed',False))})
                if self.path=='/api/run':
                    jid=body['id']
                    if not store.runnable(jid):return self.reply(409,{'error':'任务不存在或不是待运行状态'})
                    if not worker.acquire(blocking=False):return self.reply(409,{'error':'已有任务运行'})
                    def run():
                        try:store.run(jid)
                        except Exception:pass
                        finally:worker.release()
                    threading.Thread(target=run,daemon=True).start()
                    return self.reply(202,{'state':'submitted'})
                self.reply(404,{'error':'路径不存在'})
            except PermissionError:self.reply(403,{'error':'无此批次权限'})
            except (KeyError,TypeError,ValueError,FileNotFoundError) as exc:
                self.reply(400,{'error':str(exc) if isinstance(exc,ValueError) and (reviewer_route or self.path.startswith('/api/screening') or self.path.startswith('/api/reviewers') or self.path.startswith('/api/sources') or self.path.startswith('/api/writer/')) else '输入格式不正确'})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Local preview: http://127.0.0.1:{port}',flush=True)
    server.serve_forever()
