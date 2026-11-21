"""Loopback HTTP acceptance with temporary data and no external model calls."""
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        cls.token = secrets.token_hex(32)
        cls.proc = subprocess.Popen(
            [sys.executable, '-m', 'workbench', '--data', cls.tmp.name, 'serve', '--port', str(port)],
            env={**os.environ, 'WORKBENCH_ACCESS_TOKEN': cls.token, 'GEMINI_API_KEY': '', 'GEMINI_MODEL': ''},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with urllib.request.urlopen(cls.base, timeout=1):
                    return
            except OSError:
                time.sleep(.05)
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.tmp.cleanup()
        raise RuntimeError('server not ready')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, body=None, status=200):
        req = urllib.request.Request(self.base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.status, status)
            return json.load(response)

    def project(self):
        return self.request('/api/projects', {'question': 'HTTP synthetic acceptance'}, 201)['id']

    def enqueue(self, pid, constant=False):
        return self.request('/api/jobs', {'project': pid, 'kind': 'statistics', 'payload': {
            'classification': 'synthetic', 'method': 'pearson', 'x': 'x', 'y': 'y',
            'rows': [{'x': n, 'y': 1 if constant else n * 2} for n in range(1, 6)]}}, 201)['id']

    def finish(self, pid, jid):
        self.request('/api/run', {'id': jid}, 202)
        for _ in range(200):
            jobs = self.request('/api/jobs?project=' + pid)
            job = next(j for j in jobs if j['id'] == jid)
            if job['state'] in ('completed', 'failed'):
                return job
            time.sleep(.05)
        self.fail('job did not finish')

    def test_screening_scoped_http(self):
        from workbench.core import Store
        pid=self.project();Store(self.tmp.name).save(pid,'screen-source.json',{'method':'deduplication','review_candidates':[],'records':[{'title':'Synthetic review item'}]})
        human=self.request('/api/reviewers',{'actor':'http-human','role':'human'},201)
        model=self.request('/api/reviewers',{'actor':'http-model','role':'model'},201)
        other=self.request('/api/reviewers',{'actor':'http-other','role':'human'},201)
        owner_token=self.token
        protocol=dict(question='HTTP screening',stage='title_abstract',inclusion='Synthetic',exclusion='Other',human_reviewer=human['actor'],llm_reviewer=model['actor'],adjudicator=human['actor'])
        review=self.request('/api/screening-prepare',{'project':pid,'source_artifact':'screen-source.json','protocol':protocol},201)['review']
        self.request('/api/review/state',{'review':review},401)
        try:
            self.token=model['token']
            self.request('/api/projects',status=401)
            self.request('/api/artifact?project='+pid+'&name=screen-source.json',status=401)
            self.request('/api/reviewers',{'actor':'bad','role':'human'},401)
            self.request('/api/review/approve',{'review':review,'confirmed':True,'actor':human['actor']},400)
            self.request('/api/review/approve',{'review':review,'confirmed':True},400)
            self.request('/api/review/ballot',{'review':review},400)
            self.token=other['token'];self.request('/api/review/state',{'review':review},403)
            self.token=human['token'];self.request('/api/review/approve',{'review':review,'confirmed':True})
            self.request('/api/review/reveal',{'review':review},400)
            self.request('/api/review/export',{'review':review},400)
            self.request('/api/review/export_csv',{'review':review},400)
        finally:self.token=owner_token
        self.request('/api/reviewers/revoke',{'actor':human['actor']})
        try:
            self.token=human['token'];self.request('/api/review/state',{'review':review},401)
        finally:self.token=owner_token

    def test_dedup_and_review_http(self):
        from workbench.core import Store
        pid=self.project();store=Store(self.tmp.name)
        store.save(pid,'synthetic-source.json',{'records':[{'title':'Same','pmid':'1'},{'title':'Same','pmid':'1'},{'title':'Same','pmid':'2'}]})
        body={'project':pid,'source_artifact':'synthetic-source.json'}
        jid=self.request('/api/dedup',body,201)['id']
        self.assertEqual(self.request('/api/dedup',body,201)['id'],jid)
        job=self.finish(pid,jid);self.assertEqual(job['state'],'completed')
        name=json.loads(job['result'])['artifact']
        review={'project':pid,'source_artifact':name,'candidate_index':0,'decision':'merge','reason':'Synthetic human review'}
        rjid=self.request('/api/dedup',review,201)['id'];job=self.finish(pid,rjid)
        out=self.request('/api/artifact?project='+pid+'&name='+json.loads(job['result'])['artifact'])
        self.assertEqual(out['unique_count'],1);self.assertEqual(len(out['raw_records']),3)
        original=self.request('/api/artifact?project='+pid+'&name='+name)
        self.assertEqual(original['unique_count'],2)

    def test_dedup_invalid_and_foreign_source(self):
        pid=self.project()
        for name in ['../state.sqlite','missing.json',[],None]:
            self.request('/api/dedup',{'project':pid,'source_artifact':name},400)
        from workbench.core import Store
        other=self.project();Store(self.tmp.name).save(other,'only-other.json',{'records':[]})
        self.request('/api/dedup',{'project':pid,'source_artifact':'only-other.json'},400)

    def test_statistics_artifact_and_no_repeat(self):
        pid = self.project()
        jid = self.enqueue(pid)
        self.assertEqual(self.enqueue(pid), jid)
        job = self.finish(pid, jid)
        self.assertEqual(job['state'], 'completed')
        name = json.loads(job['result'])['artifact']
        result = self.request('/api/artifact?project=' + pid + '&name=' + name)
        self.assertAlmostEqual(result['coefficient'], 1)
        self.assertEqual(result['n'], 5)
        self.assertEqual(result['llm_calls'], 0)
        self.request('/api/run', {'id': jid}, 409)
        other = self.project()
        self.request('/api/artifact?project=' + other + '&name=' + name, status=400)

    def test_categorical_end_to_end(self):
        pid = self.project()
        body = {'project': pid, 'kind': 'statistics', 'payload': {
            'classification': 'synthetic', 'method': 'chi2',
            'table': [[10, 20], [20, 10]],
            'row_labels': ['A', 'B'], 'column_labels': ['yes', 'no']}}
        jid = self.request('/api/jobs', body, 201)['id']
        self.assertEqual(self.request('/api/jobs', body, 201)['id'], jid)
        job = self.finish(pid, jid)
        self.assertEqual(job['state'], 'completed')
        name = json.loads(job['result'])['artifact']
        result = self.request('/api/artifact?project=' + pid + '&name=' + name)
        self.assertAlmostEqual(result['statistic'], 20/3)
        self.assertEqual(result['n'], 60)
        self.assertEqual(result['column_labels'], ['yes', 'no'])
        self.assertIn('fisher', self.request('/api/capabilities')['statistical_methods'])

    def test_group_comparison_end_to_end(self):
        pid = self.project()
        body = {'project': pid, 'kind': 'statistics', 'payload': {
            'classification': 'synthetic', 'method': 'group_numeric', 'group': 'g', 'value': 'v',
            'rows': [{'g': group, 'v': value} for group, values in [('A', [1, 2, 3]), ('B', [4, 5, 6])] for value in values]}}
        jid = self.request('/api/jobs', body, 201)['id']
        job = self.finish(pid, jid)
        self.assertEqual(job['state'], 'completed')
        name = json.loads(job['result'])['artifact']
        result = self.request('/api/artifact?project=' + pid + '&name=' + name)
        self.assertAlmostEqual(result['tests']['cohens_d'], -3)
        self.assertEqual(result['group_order'], ['A', 'B'])
        self.assertEqual(result['complete_rows'], 6)

    def test_baseline_table_end_to_end(self):
        pid = self.project()
        body = {'project': pid, 'kind': 'statistics', 'payload': {
            'classification': 'synthetic', 'method': 'tableone',
            'variable_types': {'v': 'numeric_continuous', 'c': 'categorical'},
            'rows': [{'v': 1, 'c': 'yes'}, {'v': 2, 'c': 'no'}, {'v': 3, 'c': None}]}}
        jid = self.request('/api/jobs', body, 201)['id']
        job = self.finish(pid, jid)
        self.assertEqual(job['state'], 'completed')
        name = json.loads(job['result'])['artifact']
        result = self.request('/api/artifact?project=' + pid + '&name=' + name)
        row = next(r for r in result['table'] if r['variable'] == 'v')
        self.assertEqual(row['sd'], 1)
        self.assertEqual(result['missingness']['Overall']['c']['n_missing'], 1)

    def test_regression_end_to_end(self):
        pid = self.project()
        body = {'project': pid, 'kind': 'statistics', 'payload': {
            'classification': 'synthetic', 'method': 'linear_regression', 'outcome': 'y', 'predictors': ['x'],
            'rows': [{'x': x, 'y': y} for x,y in zip([0,1,2,3,4],[1,2,2,4,6])]}}
        jid = self.request('/api/jobs', body, 201)['id']
        job = self.finish(pid, jid)
        self.assertEqual(job['state'], 'completed')
        name = json.loads(job['result'])['artifact']
        result = self.request('/api/artifact?project=' + pid + '&name=' + name)
        self.assertAlmostEqual(result['coefficients']['x'], 1.2)
        self.assertEqual(result['complete_rows'], 5)

    def test_prediction_evaluation_end_to_end(self):
        pid = self.project()
        body = {'project': pid, 'kind': 'statistics', 'payload': {
            'classification': 'synthetic', 'method': 'prediction_evaluation', 'threshold': .5, 'n_bins': 2, 'evaluation_scope': 'training',
            'rows': [{'observed': y, 'probability': p} for y,p in [(0,.1),(0,.4),(1,.35),(1,.8)]]}}
        jid = self.request('/api/jobs', body, 201)['id']
        job = self.finish(pid, jid)
        self.assertEqual(job['state'], 'completed')
        name = json.loads(job['result'])['artifact']
        result = self.request('/api/artifact?project=' + pid + '&name=' + name)
        self.assertAlmostEqual(result['roc']['auc'], .75)
        self.assertEqual(result['evaluation_scope'], 'training')

    def test_glm_end_to_end(self):
        pid = self.project()
        for method in ['poisson_regression', 'gamma_regression']:
            body = {'project': pid, 'kind': 'statistics', 'payload': {
                'classification': 'synthetic', 'method': method, 'outcome': 'y', 'predictors': ['x'],
                'rows': [{'x': x, 'y': y} for x,ys in [(0,[1,2,3,2]),(1,[2,4,6,4])] for y in ys]}}
            jid = self.request('/api/jobs', body, 201)['id']
            job = self.finish(pid, jid)
            self.assertEqual(job['state'], 'completed')
            name = json.loads(job['result'])['artifact']
            result = self.request('/api/artifact?project=' + pid + '&name=' + name)
            self.assertAlmostEqual(result['fitted_means'][0], 2)
            self.assertEqual(result['complete_rows'], 8)

    def test_imputation_end_to_end(self):
        pid = self.project()
        body = {'project': pid, 'kind': 'statistics', 'payload': {
            'classification': 'synthetic', 'method': 'mice_imputation', 'strategy': 'linear',
            'n_imputations': 1, 'max_iter': 5, 'pool_means': False,
            'variable_types': {'x': 'numeric_continuous', 'y': 'numeric_continuous'},
            'rows': [{'x': x, 'y': y} for x,y in [(1,2),(2,4),(3,None),(4,8)]]}}
        jid = self.request('/api/jobs', body, 201)['id']
        job = self.finish(pid, jid)
        self.assertEqual(job['state'], 'completed')
        name = json.loads(job['result'])['artifact']
        result = self.request('/api/artifact?project=' + pid + '&name=' + name)
        self.assertAlmostEqual(result['datasets'][0][2]['y'], 6)
        self.assertEqual(result['pooled_means'], [])

    def test_failed_job_explicit_retry(self):
        pid = self.project()
        jid = self.enqueue(pid, constant=True)
        self.assertEqual(self.finish(pid, jid)['state'], 'failed')
        self.request('/api/retry', {'id': jid}, 400)
        retry = self.request('/api/retry', {'id': jid, 'confirmed': True}, 201)['id']
        self.assertNotEqual(retry, jid)
        self.assertEqual(self.request('/api/retry', {'id': jid, 'confirmed': True}, 201)['id'], retry)

    def test_malformed_requests_do_not_disconnect(self):
        for body in ([], 'text', 12, {'project': [], 'kind': 'search', 'payload': {}}, {'id': {}}):
            with self.subTest(body=body):
                self.request('/api/jobs', body, 400)
        self.assertEqual(self.request('/api/capabilities')['writing'], 'not_configured')

    def test_reject_input_without_persistence(self):
        pid = self.project()
        self.request('/api/jobs', {'project': pid, 'kind': 'statistics', 'payload': {'classification': 'patient'}}, 400)
        self.request('/api/jobs', {'project': pid, 'kind': 'write', 'payload': {}}, 400)
        self.assertEqual(self.request('/api/jobs?project=' + pid), [])


if __name__ == '__main__':
    unittest.main()
