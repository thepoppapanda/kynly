"""Loopback-only authenticated HTTP interface to Kynly queue storage."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import re
import sqlite3
import sys

import job_queue as queue
from research_reports import save_report
from desktop_notifications import notify, subscribe, notification_requested

JOB_PATH = re.compile(r'/jobs/(job-[0-9a-f]{32})(/cancel)?')
PUBLIC_FIELDS = ('sequence', 'job_id', 'request_key', 'task', 'timeout_seconds',
                 'status', 'created_at', 'started_at', 'finished_at', 'exit_code')


def public(job):
    return {key: job.get(key) for key in PUBLIC_FIELDS}


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass  # Never print request headers, body, or token.

    def reply(self, code, value):
        data = json.dumps(value).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def dispatch(self):
        authorization = self.headers.get_all('Authorization', [])
        expected = ('Bearer ' + self.server.token).encode('utf-8')
        if len(authorization) != 1 or not hmac.compare_digest(authorization[0].encode('utf-8'), expected):
            self.reply(401, {'error': 'Unauthorized'})
            return
        if self.headers.get('Origin'):
            self.reply(403, {'error': 'Browser-origin requests are not supported'})
            return
        match = JOB_PATH.fullmatch(self.path)
        try:
            if self.command == 'GET' and self.path == '/health':
                queue.inspect(self.server.data_dir, limit=1)
                self.reply(200, {'status': 'ok', 'service': 'kynly-queue', 'executes_jobs': False})
            elif self.command == 'GET' and self.path == '/jobs':
                self.reply(200, {'jobs': [public(j) for j in queue.inspect(self.server.data_dir)]})
            elif self.command == 'GET' and match and not match[2]:
                self.reply(200, public(queue.inspect(self.server.data_dir, match[1])))
            elif self.command == 'POST' and self.path == '/research/reports':
                self.reply(200, save_report(self.server.data_dir, self.body()))
            elif self.command == 'POST' and self.path == '/notifications':
                self.reply(200, notify(self.server.data_dir, self.body()))
            elif self.command == 'POST' and self.path == '/jobs':
                body = self.body()
                if not isinstance(body, dict) or set(body) - {'task', 'timeout_seconds', 'request_key', 'notify_desktop'}:
                    raise ValueError('Expected task, timeout_seconds, request_key, and optional notify_desktop')
                task, key = body.get('task'), body.get('request_key')
                timeout = body.get('timeout_seconds', 30)
                if not isinstance(task, str) or not isinstance(key, str):
                    raise ValueError('task and request_key must be strings')
                if type(timeout) not in (int, float) or not math.isfinite(timeout):
                    raise ValueError('timeout_seconds must be a finite number')
                requested = body.get('notify_desktop', False)
                if type(requested) is not bool:
                    raise ValueError('notify_desktop must be a boolean')
                job = queue.submit(self.server.data_dir, task, timeout, key)
                if requested:
                    subscribe(self.server.data_dir, job['job_id'])
                self.reply(200, dict(public(job), desktop_notification_requested=notification_requested(self.server.data_dir, job['job_id'])))
            elif self.command == 'POST' and match and match[2]:
                if self.body() != {}:
                    raise ValueError('Cancellation body must be an empty JSON object')
                self.reply(200, public(queue.cancel(self.server.data_dir, match[1])))
            else:
                self.reply(404, {'error': 'Route not found'})
        except ValueError as error:
            message = str(error)
            code = 404 if message == 'Job not found' else 409 if message.startswith(('Request key already', 'Active cancellation:')) else 400
            self.reply(code, {'error': message})
        except (OSError, sqlite3.Error):
            self.reply(503, {'error': 'Queue storage unavailable'})

    def body(self):
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            raise ValueError('One Content-Length header is required; chunking is unsupported')
        length = int(self.headers['Content-Length'])
        if not 0 < length <= 8192:
            raise ValueError('JSON body must contain 1 to 8192 bytes')
        if self.headers.get_content_type() != 'application/json':
            raise ValueError('Content-Type must be application/json')
        try:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid JSON body') from error

    do_GET = dispatch
    do_POST = dispatch


def make_server(data_dir, token, port=8787):
    if not isinstance(token, str) or len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError('KYNLY_API_TOKEN must contain at least 32 non-whitespace ASCII characters')
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.data_dir, server.token = data_dir, token
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    try:
        with make_server(args.data_dir, os.environ.get('KYNLY_API_TOKEN', ''), args.port) as server:
            print(f'Kynly queue API: http://127.0.0.1:{args.port} (Ctrl+C to stop)', flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError) as error:
        print('Error: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
