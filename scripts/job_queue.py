"""Persistent Kynly queue storage. Stores jobs and drains them through the bounded Docker runner."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from run_job import TASKS, TERMINAL, now, run_job, workspace_lock


@contextmanager
def database(data_dir):
    root = Path(data_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(root / 'queue.sqlite3', timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('''CREATE TABLE IF NOT EXISTS jobs (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            request_key TEXT NOT NULL UNIQUE,
            task TEXT NOT NULL,
            timeout_seconds REAL NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued', 'cancelled')),
            created_at TEXT NOT NULL,
            finished_at TEXT
        )''')
        connection.commit()
        # Migrate checkpoint-1 tables transactionally, preserving IDs and order.
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            columns = {row['name'] for row in connection.execute('PRAGMA table_info(jobs)')}
            if 'exit_code' not in columns:
                connection.execute('ALTER TABLE jobs RENAME TO jobs_v1')
                connection.execute("""CREATE TABLE jobs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE, request_key TEXT NOT NULL UNIQUE,
                    task TEXT NOT NULL, timeout_seconds REAL NOT NULL,
                    status TEXT NOT NULL CHECK(status IN
                    ('queued','running','passed','failed','timed_out','cancelled','interrupted')),
                    created_at TEXT NOT NULL, finished_at TEXT,
                    started_at TEXT, exit_code INTEGER, result_path TEXT
                )""")
                connection.execute("""INSERT INTO jobs
                    (sequence,job_id,request_key,task,timeout_seconds,status,created_at,finished_at)
                    SELECT sequence,job_id,request_key,task,timeout_seconds,status,created_at,finished_at FROM jobs_v1""")
                connection.execute('DROP TABLE jobs_v1')
        yield connection
    finally:
        connection.close()


def submit(data_dir, task, timeout, request_key):
    if task not in TASKS:
        raise ValueError('Unknown task')
    if not 0 < timeout <= 3600:
        raise ValueError('Timeout must be greater than 0 and at most 3600')
    if not request_key or len(request_key) > 200:
        raise ValueError('Request key must contain 1 to 200 characters')
    with database(data_dir) as db:
        # Serialize the lookup and insert across independent submitting processes.
        with db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM jobs WHERE request_key=?', (request_key,)).fetchone()
            if existing:
                if existing['task'] != task or existing['timeout_seconds'] != timeout:
                    raise ValueError('Request key already belongs to different job parameters')
                return dict(existing)
            job_id = 'job-' + uuid.uuid4().hex
            db.execute('''INSERT INTO jobs
                (job_id, request_key, task, timeout_seconds, status, created_at)
                VALUES (?, ?, ?, ?, 'queued', ?)''', (job_id, request_key, task, timeout, now()))
            return dict(db.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone())


def inspect(data_dir, job_id=None, limit=50):
    with database(data_dir) as db:
        if job_id:
            row = db.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone()
            if row is None:
                raise ValueError('Job not found')
            return dict(row)
        return [dict(row) for row in db.execute('SELECT * FROM jobs ORDER BY sequence DESC LIMIT ?', (limit,))]


def cancel(data_dir, job_id):
    with database(data_dir) as db:
        with db:
            row = db.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone()
            if row is None:
                raise ValueError('Job not found')
            if row['status'] == 'running':
                raise ValueError('Active cancellation: use run_job.py cancel with the runs directory')
            db.execute("UPDATE jobs SET status='cancelled', finished_at=? WHERE job_id=? AND status='queued'", (now(), job_id))
        return dict(db.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone())


def drain(data_dir, execute=run_job):
    root = Path(data_dir).expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    completed = []
    # Fixed checkout lock also prevents workers with different data directories.
    with workspace_lock(repo / '.kynly' / 'queue-worker.lock'):
        while True:
            with database(root) as db:
                with db:
                    db.execute('BEGIN IMMEDIATE')
                    if db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone():
                        raise RuntimeError('Unresolved running job: recovery required; no jobs started')
                    row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY sequence LIMIT 1").fetchone()
                    if row is None:
                        return completed
                    job = dict(row)
                    result_path = root / 'runs' / job['job_id'] / 'result.json'
                    db.execute("UPDATE jobs SET status='running', started_at=?, result_path=? WHERE job_id=?",
                               (now(), str(result_path), job['job_id']))
            args = argparse.Namespace(task=job['task'], timeout=job['timeout_seconds'],
                                      data_dir=str(root / 'runs'), job_id=job['job_id'])
            # Any unexpected failure leaves a running receipt and stops dispatch.
            # Never guess that a crashed run is safe to retry.
            execute(args)
            result = json.loads(result_path.read_text(encoding='utf-8'))
            if result.get('job_id') != job['job_id'] or result.get('status') not in TERMINAL:
                raise RuntimeError('Runner returned an invalid completion receipt')
            cleanup = result.get('cleanup', {})
            cleanup_output = cleanup.get('output', '').lower()
            if cleanup.get('exit_code') != 0 and 'no such container' not in cleanup_output:
                raise RuntimeError('Container cleanup unconfirmed; queue stopped for recovery')
            with database(root) as db:
                with db:
                    db.execute("UPDATE jobs SET status=?, exit_code=?, finished_at=? WHERE job_id=? AND status='running'",
                               (result['status'], result['exit_code'], result['finished_at'], job['job_id']))
            completed.append(job['job_id'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    commands = parser.add_subparsers(dest='operation', required=True)
    add = commands.add_parser('submit')
    add.add_argument('task', choices=TASKS)
    add.add_argument('--timeout', type=float, default=30)
    add.add_argument('--request-key', required=True)
    commands.add_parser('work')
    listing = commands.add_parser('list')
    listing.add_argument('--limit', type=int, default=50)
    for command in ('show', 'cancel'):
        commands.add_parser(command).add_argument('job_id')
    args = parser.parse_args()
    try:
        if args.operation == 'work':
            result = {'completed': drain(args.data_dir)}
        elif args.operation == 'submit':
            result = submit(args.data_dir, args.task, args.timeout, args.request_key)
        elif args.operation == 'cancel':
            result = cancel(args.data_dir, args.job_id)
        elif args.operation == 'show':
            result = inspect(args.data_dir, args.job_id)
        else:
            if not 1 <= args.limit <= 1000:
                raise ValueError('Limit must be between 1 and 1000')
            result = inspect(args.data_dir, limit=args.limit)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        print('Error: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
