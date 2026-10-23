import sys
from pathlib import Path
import tempfile
import unittest
import json
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from research_reports import save_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=self.temp.name
        self.body={'request_key':'ruby-test-001','title':'Virtual environments','summary':'A project-specific Python environment.', 'sources':[{'title':'Official venv docs','url':'https://docs.python.org/3/library/venv.html'}]}

    def test_files_persist_with_source_and_metadata(self):
        r=save_report(self.root,self.body)
        self.assertIn(self.body['sources'][0]['url'],Path(r['report_path']).read_text())
        self.assertEqual(json.loads(Path(r['metadata_path']).read_text())['summary'],self.body['summary'])
        self.assertEqual(Path(r['report_path']).parent.parent,Path(self.root)/'reports')

    def test_retries_and_conflicts(self):
        first=save_report(self.root,self.body)
        duplicate=save_report(self.root,self.body)
        self.assertTrue(duplicate['duplicate']);self.assertEqual(first['report_id'],duplicate['report_id'])
        with self.assertRaises(ValueError):save_report(self.root,dict(self.body,summary='Changed'))

    def test_concurrent_same_key(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts=list(pool.map(lambda _:save_report(self.root,self.body),range(4)))
        self.assertEqual(len({r['report_id'] for r in receipts}),1)
        self.assertEqual(sum(not r['duplicate'] for r in receipts),1)

    def test_rejects_path_and_oversize_or_missing_data(self):
        for body in [dict(self.body,path='outside.md'),dict(self.body,request_key='../oops'),dict(self.body,summary='a'*3001),dict(self.body,sources=[])]:
            with self.assertRaises(ValueError):save_report(self.root,body)

    def test_rejects_credential_and_non_web_urls(self):
        for url in ['file:///secret','https://user:password@example.com','not-a-url']:
            with self.assertRaises(ValueError):save_report(self.root,dict(self.body,sources=[{'title':'source','url':url}]))

    def test_missing_files_not_falsely_reported_saved_on_retry(self):
        first=save_report(self.root,self.body);Path(first['report_path']).unlink()
        with self.assertRaises(OSError):save_report(self.root,self.body)
