"""Validated, deduplicated Windows toast submission for observed Kynly results."""
import json
import os
from pathlib import Path
import re
import subprocess

import job_queue as queue
from run_job import TERMINAL, now


def windows_toast(title, message):
    if os.name != 'nt':
        raise OSError('Desktop notifications require Windows')
    # Fixed executable/script and argument list; never evaluate request text as code.
    completed = subprocess.run([
        str(Path(os.environ['SystemRoot'])/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'),
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
        str(Path(__file__).with_name('show-notification.ps1')),
        '-Title', title, '-Message', message,
    ], capture_output=True, text=True, timeout=20)
    if completed.returncode != 0:
        raise OSError('Windows notification script failed; test show-notification.ps1 locally')


def notify(data_dir, body, send=windows_toast):
    allowed = {'job_id','request_key','outcome','job_status','exit_code','checks','message'}
    if not isinstance(body, dict) or set(body)-allowed:
        raise ValueError('Expected a Result Summary object')
    job_id, status, outcome = body.get('job_id'), body.get('job_status'), body.get('outcome')
    if not isinstance(job_id,str) or not re.fullmatch(r'job-[0-9a-f]{32}', job_id):
        raise ValueError('Invalid job ID')
    if not isinstance(status,str) or not isinstance(outcome,str):
        raise ValueError('outcome and job_status must be strings')
    checks = body.get('checks')
    if type(checks) is not int or not 1 <= checks <= 1000:
        raise ValueError('checks must be an integer between 1 and 1000')
    job = queue.inspect(data_dir, job_id)
    if body.get('request_key') != job['request_key']:
        raise ValueError('Request key does not match job')
    if outcome == 'monitoring_limit_reached' and status in ('queued','running') and body.get('exit_code') is None:
        title = 'Kynly: monitoring limit reached'
        message = f'Job {job_id}: last observed {status} after {checks} checks. Monitoring stopped; job was not cancelled.'
        code = None
    elif (outcome == ('passed' if status == 'passed' else 'job_unsuccessful')
          and status in TERMINAL and status == job['status']
          and type(body.get('exit_code')) is int and body['exit_code'] == job['exit_code']):
        title = 'Kynly: tests passed' if status == 'passed' else 'Kynly: job unsuccessful'
        code = job['exit_code']
        message = f'Job {job_id}: {status}, exit code {code}.'
    else:
        raise ValueError('Summary outcome or status does not match a supported result')
    # One attempt per job/outcome/status, including uncertain attempts after crashes.
    key = job_id + ':' + outcome + ':' + status
    with queue.database(data_dir) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS desktop_notifications (
            notification_key TEXT PRIMARY KEY, receipt TEXT NOT NULL)''')
        db.commit()
        with db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT receipt FROM desktop_notifications WHERE notification_key=?',(key,)).fetchone()
            if previous:
                return dict(json.loads(previous['receipt']), duplicate=True)
            receipt = {'notification_key':key,'job_id':job_id,'outcome':outcome,
                       'notification_state':'attempt_started','attempted_at':now(),
                       'duplicate':False,'display_confirmed':False}
            db.execute('INSERT INTO desktop_notifications VALUES (?,?)',(key,json.dumps(receipt)))
        try:
            send(title,message)
            receipt['notification_state'] = 'submitted_to_windows'
        except subprocess.TimeoutExpired:
            receipt['notification_state'] = 'submission_unknown'
            receipt['error'] = 'Notification process timed out; do not assume no notification was shown'
        except OSError as error:
            receipt['notification_state'] = 'failed'
            receipt['error'] = str(error)
        receipt['finished_at'] = now()
        with db:
            db.execute('UPDATE desktop_notifications SET receipt=? WHERE notification_key=?', (json.dumps(receipt),key))
        return receipt
