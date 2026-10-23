import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import queue_api as api


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.token = 'a' * 64
        cls.server = api.make_server(cls.temp.name, cls.token, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()
        cls.temp.cleanup()

    def request(self, path, body=None, token=True, extra=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + self.token
        headers.update(extra or {})
        request = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_auth_required(self):
        self.assertEqual(self.request('/health', token=False)[0], 401)
        self.assertEqual(self.request('/health', extra={'Authorization': 'Bearer wrong'})[0], 401)
        self.assertEqual(self.request('/health')[0], 200)

    def test_submit_duplicate_conflict_show_cancel(self):
        body = {'task': 'tests', 'request_key': 'api-smoke'}
        code, job = self.request('/jobs', body)
        self.assertEqual(code, 200)
        self.assertEqual(job['status'], 'queued')
        self.assertNotIn('result_path', job)
        self.assertEqual(self.request('/jobs', body)[1]['job_id'], job['job_id'])
        self.assertEqual(self.request('/jobs', dict(body, task='probe-failure'))[0], 409)
        path = '/jobs/' + job['job_id']
        self.assertEqual(self.request(path)[1]['job_id'], job['job_id'])
        self.assertEqual(self.request(path + '/cancel', {})[1]['status'], 'cancelled')
        self.assertEqual(self.request('/jobs')[0], 200)

    def test_invalid_submission(self):
        for body in ({}, [], {'task': 'shell', 'request_key': 'bad'},
                     {'task': 'tests', 'request_key': 'bad', 'timeout_seconds': True},
                     {'task': 'tests', 'request_key': 'bad', 'command': 'echo bad'}):
            self.assertEqual(self.request('/jobs', body)[0], 400)

    def test_origin_and_unknown_routes(self):
        self.assertEqual(self.request('/health', extra={'Origin': 'http://example.com'})[0], 403)
        self.assertEqual(self.request('/work', {})[0], 404)
        self.assertEqual(self.request('/jobs/job-' + '0' * 32)[0], 404)

    def test_short_token_rejected(self):
        with self.assertRaises(ValueError):
            api.make_server(self.temp.name, 'short', 0)

    def test_submission_records_opt_in_without_changing_task(self):
        code,job=self.request('/jobs',{'task':'tests','request_key':'api-desktop-opt-in','notify_desktop':True})
        self.assertEqual(code,200)
        self.assertTrue(job['desktop_notification_requested'])
        self.assertEqual(job['task'],'tests')
        code,again=self.request('/jobs',{'task':'tests','request_key':'api-desktop-opt-in'})
        self.assertEqual(again['job_id'],job['job_id'])
        self.assertTrue(again['desktop_notification_requested'])
        self.assertEqual(self.request('/jobs',{'task':'tests','request_key':'invalid-opt-in','notify_desktop':'yes'})[0],400)

    def test_report_endpoint_persists_and_deduplicates(self):
        body={'request_key':'http-report-001','title':'HTTP report test','summary':'A stored summary.','sources':[{'title':'Python','url':'https://docs.python.org/3/library/venv.html'}]}
        self.assertEqual(self.request('/research/reports',body,token=False)[0],401)
        code,receipt=self.request('/research/reports',body)
        self.assertEqual(code,200)
        self.assertEqual(receipt['status'],'saved')
        self.assertTrue(Path(receipt['report_path']).is_file())
        code,again=self.request('/research/reports',body)
        self.assertTrue(again['duplicate'])
        self.assertEqual(again['report_id'],receipt['report_id'])
        self.assertEqual(self.request('/research/reports',dict(body,summary='Different'))[0],409)


if __name__ == '__main__':
    unittest.main()
