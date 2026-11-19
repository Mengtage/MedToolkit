import json,os,secrets,socket,subprocess,sys,tempfile,time,unittest
import urllib.request,urllib.error

class HttpTest(unittest.TestCase):
    def test_auth_and_private_response(self):
        with tempfile.TemporaryDirectory() as d:
            sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
            token=secrets.token_hex(32)
            env={**os.environ,'WORKBENCH_ACCESS_TOKEN':token}
            proc=subprocess.Popen([sys.executable,'-m','workbench','--data',d,'serve','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                base=f'http://127.0.0.1:{port}'
                for _ in range(30):
                    try:
                        with urllib.request.urlopen(base,timeout=1) as r:self.assertIn(b'MENGTAGE',r.read())
                        break
                    except OSError:time.sleep(.1)
                else:self.fail('server not ready')
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+'/api/projects')
                self.assertEqual(e.exception.code,401);e.exception.close()
                req=urllib.request.Request(base+'/api/projects',data=json.dumps({'question':'<script>test</script>'}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                with urllib.request.urlopen(req) as r:
                    self.assertEqual(r.status,201);self.assertEqual(r.headers['Cache-Control'],'no-store')
                req=urllib.request.Request(base+'/api/projects',headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(req) as r:self.assertEqual(len(json.load(r)),1)
            finally:proc.terminate();proc.wait(timeout=5)

if __name__=='__main__':unittest.main()
