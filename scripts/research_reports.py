"""Bounded Markdown research reports; no caller-controlled filesystem paths."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import job_queue as queue
from run_job import now, save_json


def validate(body):
    if not isinstance(body,dict) or set(body) != {'request_key','title','summary','sources'}:
        raise ValueError('Expected request_key, title, summary and sources only')
    key=body['request_key']
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,99}',key):
        raise ValueError('Invalid report request key')
    for field,limit in [('title',120),('summary',3000)]:
        value=body[field]
        if not isinstance(value,str) or not value.strip() or len(value)>limit or '\x00' in value:
            raise ValueError('Invalid report '+field)
    if '\n' in body['title'] or '\r' in body['title']:
        raise ValueError('Report title must be one line')
    sources=body['sources']
    if not isinstance(sources,list) or not 1<=len(sources)<=3:
        raise ValueError('Supply one to three sources')
    for source in sources:
        if not isinstance(source,dict) or set(source)!={'title','url'}:
            raise ValueError('Each source requires title and url only')
        if not isinstance(source['title'],str) or not 1<=len(source['title'])<=120 or any(c in source['title'] for c in '\r\n\x00'):
            raise ValueError('Invalid source title')
        url=source['url']
        if not isinstance(url,str) or len(url)>800 or any(c.isspace() for c in url):
            raise ValueError('Invalid source URL')
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError('Sources require HTTP(S) URLs without login credentials')
    return body


def save_report(data_dir, body):
    body=validate(body)
    canonical=json.dumps(body,sort_keys=True,ensure_ascii=False)
    digest=hashlib.sha256(canonical.encode()).hexdigest()
    with queue.database(data_dir) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS research_reports (
            request_key TEXT PRIMARY KEY, digest TEXT NOT NULL, receipt TEXT NOT NULL)''')
        db.commit()
        with db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM research_reports WHERE request_key=?',(body['request_key'],)).fetchone()
            if row:
                if row['digest']!=digest:
                    raise ValueError('Request key already belongs to different report content')
                receipt=json.loads(row['receipt'])
                if not Path(receipt['report_path']).is_file() or not Path(receipt['metadata_path']).is_file():
                    raise OSError('Saved report files are missing; inspect storage before retrying')
                return dict(receipt,duplicate=True)
            report_id='report-'+hashlib.sha256(body['request_key'].encode()).hexdigest()[:32]
            directory=Path(data_dir).expanduser().resolve()/'reports'/report_id
            directory.mkdir(parents=True,exist_ok=True)
            created=now()
            markdown='# '+body['title']+'\n\nCreated: '+created+'\n\n'+body['summary']+'\n\n## Sources\n\n'
            for source in body['sources']:
                markdown+=source['title']+'\n\n'+source['url']+'\n\n'
            target=directory/'report.md'
            temporary=directory/'report.tmp'
            temporary.write_text(markdown,encoding='utf-8')
            temporary.replace(target)
            metadata=directory/'metadata.json'
            save_json(metadata,dict(body,report_id=report_id,created_at=created))
            receipt={'report_id':report_id,'request_key':body['request_key'],'status':'saved',
                     'created_at':created,'report_path':str(target),'metadata_path':str(metadata),'duplicate':False}
            db.execute('INSERT INTO research_reports VALUES (?,?,?)',(body['request_key'],digest,json.dumps(receipt)))
            return receipt
