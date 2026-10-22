import sys
from pathlib import Path
import tempfile
import unittest
import subprocess

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import job_queue as queue
import desktop_notifications as desktop


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=self.temp.name
        job=queue.submit(self.root,'tests',30,'notify-test')
        with queue.database(self.root) as db:
            with db:
                db.execute("UPDATE jobs SET status='passed',exit_code=0 WHERE job_id=?",(job['job_id'],))
        self.body={'job_id':job['job_id'],'request_key':'notify-test','outcome':'passed','job_status':'passed','exit_code':0,'checks':1}

    def test_duplicate_is_not_sent_twice(self):
        sent=[]
        first=desktop.notify(self.root,self.body,lambda *args:sent.append(args))
        again=desktop.notify(self.root,self.body,lambda *args:sent.append(args))
        self.assertEqual(len(sent),1)
        self.assertEqual(first['notification_state'],'submitted_to_windows')
        self.assertTrue(again['duplicate'])
        self.assertFalse(first['display_confirmed'])

    def test_mismatch_and_unsupported_fields_rejected(self):
        for fields in ({'job_status':'failed'}, {'request_key':'wrong'}, {'checks':True}, {'command':'echo bad'}):
            with self.assertRaises(ValueError):
                desktop.notify(self.root,dict(self.body,**fields),lambda *_:self.fail('Sent invalid summary'))

    def test_monitoring_limit_is_not_job_timeout(self):
        sent=[]
        body=dict(self.body,outcome='monitoring_limit_reached',job_status='running',exit_code=None)
        desktop.notify(self.root,body,lambda *args:sent.append(args))
        self.assertIn('last observed running',sent[0][1])
        self.assertIn('not cancelled',sent[0][1])

    def test_timeout_is_uncertain_and_not_retried(self):
        def timeout(*args):
            raise subprocess.TimeoutExpired('powershell',20)
        receipt=desktop.notify(self.root,self.body,timeout)
        self.assertEqual(receipt['notification_state'],'submission_unknown')
        self.assertTrue(desktop.notify(self.root,self.body,lambda *_:self.fail('Retried uncertain delivery'))['duplicate'])

    def test_failure_preserves_job_outcome(self):
        def fail(*args):
            raise OSError('unavailable')
        receipt=desktop.notify(self.root,self.body,fail)
        self.assertEqual(receipt['notification_state'],'failed')
        self.assertEqual(queue.inspect(self.root,self.body['job_id'])['status'],'passed')

    def test_message_input_is_not_executed_or_used(self):
        sent=[]
        desktop.notify(self.root,dict(self.body,message='arbitrary external text'),lambda *args:sent.append(args))
        self.assertNotIn('arbitrary external text',sent[0][1])
