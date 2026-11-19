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
            return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
        def do_GET(self):
            path=urlparse(self.path)
            static={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css')}
            if path.path in static:
                name,mime=static[path.path];return self.reply(200,(ROOT/'web'/name).read_text(),mime)
            if not self.authorized():return self.reply(401,{'error':'需要访问令牌'})
            try:
                q=parse_qs(path.query)
                if path.path=='/api/capabilities':return self.reply(200,{'search':True,'statistics':'synthetic_only','writing':'not_configured' if not (os.environ.get('GEMINI_API_KEY') and os.environ.get('GEMINI_MODEL')) else 'configured','zotero':'ris_export'})
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
            if not self.authorized():return self.reply(401,{'error':'需要访问令牌'})
            # No CORS and JSON-only requests prevent browser form submissions.
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,{'error':'仅支持JSON'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1_000_000:return self.reply(413,{'error':'请求大小超限'})
                body=json.loads(self.rfile.read(size))
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
            except (KeyError,TypeError,ValueError):self.reply(400,{'error':'输入格式不正确'})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Local preview: http://127.0.0.1:{port}',flush=True)
    server.serve_forever()
