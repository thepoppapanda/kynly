"""Start, inspect, and gracefully stop Kynly's local API/worker host."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import job_queue as queue
from queue_api import make_server
from desktop_notifications import dispatch_subscriptions
from run_job import now, save_json, workspace_lock

RUNTIME = Path(__file__).resolve().parents[1] / '.kynly' / 'background'
TOKEN_FILE = RUNTIME.parent / 'api-token.txt'


def serve(data_dir, token, runtime, instance, port=8787):
    runtime = Path(runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    state_path = runtime / 'state.json'
    stop = threading.Event()
    with workspace_lock(runtime / 'host.lock'):
        server = None
        api_thread = None
        notification_thread = None
        notification_stop = threading.Event()
        state = {'instance': instance, 'pid': os.getpid(), 'status': 'starting',
                 'started_at': now(), 'data_dir': str(Path(data_dir).resolve())}
        try:
            with queue.database(data_dir) as db:
                if db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone():
                    raise RuntimeError('Unresolved running job; run queue recovery before starting')
            server = make_server(data_dir, token, port)
            api_thread = threading.Thread(target=server.serve_forever, daemon=True)
            api_thread.start()
            def watch_notifications():
                while not notification_stop.is_set():
                    try:
                        dispatch_subscriptions(data_dir, stop_event=notification_stop)
                    except Exception as error:
                        print('Notification dispatcher error: ' + str(error), flush=True)
                    notification_stop.wait(2)
            notification_thread = threading.Thread(target=watch_notifications, daemon=True)
            notification_thread.start()
            def watch_stop():
                while not stop.wait(0.2):
                    if (runtime / (instance + '.stop')).exists():
                        stop.set()
            threading.Thread(target=watch_stop, daemon=True).start()
            # drain acquires the queue-worker lock; publish readiness only after it does.
            class ReadyEvent:
                def is_set(self):
                    if state['status'] == 'starting':
                        state.update(status='running', port=server.server_port)
                        save_json(state_path, state)
                    return stop.is_set()
                def wait(self, seconds):
                    return stop.wait(seconds)
            queue.drain(data_dir, watch=True, stop_event=ReadyEvent())
            state['status'] = 'stopped'
        except BaseException as error:
            state.update(status='failed', error=str(error) or type(error).__name__)
            raise
        finally:
            stop.set()
            notification_stop.set()
            if notification_thread:
                notification_thread.join(timeout=25)
            if server:
                server.shutdown()
                server.server_close()
            if api_thread:
                api_thread.join(timeout=5)
            state['finished_at'] = now()
            save_json(state_path, state)


def status(runtime=RUNTIME):
    runtime = Path(runtime)
    path = runtime / 'state.json'
    if not path.exists():
        return {'status': 'stopped'}
    state = json.loads(path.read_text(encoding='utf-8'))
    try:
        with workspace_lock(runtime / 'host.lock'):
            if state.get('status') in ('running', 'starting'):
                state['status'] = 'stale'
    except RuntimeError:
        if (runtime / (state.get('instance', '') + '.stop')).exists():
            state['status'] = 'stopping'
    return state


def start(data_dir, port):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    # Serialize launchers separately from the lifetime lock held by the child.
    with workspace_lock(RUNTIME / 'launcher.lock'):
        current = status()
        if current['status'] in ('running', 'starting', 'stopping'):
            return current
        token = TOKEN_FILE.read_text(encoding='utf-8').strip()
        if len(token) < 32:
            raise ValueError('Missing or invalid .kynly/api-token.txt')
        instance = uuid.uuid4().hex
        command = [sys.executable, str(Path(__file__).resolve()), '_serve',
                   '--data-dir', str(Path(data_dir).resolve()), '--port', str(port), '--instance', instance]
        options = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
        with (RUNTIME / 'host.log').open('ab') as log:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, cwd=Path(__file__).resolve().parents[1], **options)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state = status()
            if state.get('instance') == instance and state['status'] == 'running':
                return state
            if child.poll() is not None:
                raise RuntimeError('Background host failed to start; inspect .kynly/background/host.log')
            time.sleep(0.1)
        raise RuntimeError('Startup not confirmed; inspect status and host.log before retrying')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['start', 'status', 'stop', '_serve'])
    parser.add_argument('--data-dir')
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--instance')
    args = parser.parse_args()
    try:
        if args.operation == '_serve':
            serve(args.data_dir, TOKEN_FILE.read_text(encoding='utf-8').strip(), RUNTIME, args.instance, args.port)
            return 0
        if args.operation == 'start':
            if not args.data_dir:
                parser.error('start requires --data-dir')
            if not 1 <= args.port <= 65535:
                parser.error('port must be between 1 and 65535')
            value = start(args.data_dir, args.port)
        else:
            value = status()
            if args.operation == 'stop' and value.get('status') in ('running', 'starting', 'stopping'):
                (RUNTIME / (value['instance'] + '.stop')).touch()
                value['status'] = 'stopping'
                value['note'] = 'Active job finishes before shutdown; check status again afterward'
        print(json.dumps(value, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print('Error: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
