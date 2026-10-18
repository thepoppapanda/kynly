import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHandler } from './kynly-mcp.mjs';

const rpc = (method, params) => ({ jsonrpc: '2.0', id: 1, method, params });
test('initialization and scoped catalog', async () => {
  const handle = createHandler();
  assert.equal((await handle(rpc('initialize'))).result.serverInfo.name, 'kynly-tools');
  const names = (await handle(rpc('tools/list'))).result.tools.map(t => t.name);
  assert.deepEqual(names, ['kynly_submit_tests', 'kynly_jobs_list', 'kynly_job_status']);
  assert.equal(await handle({ jsonrpc: '2.0', method: 'notifications/initialized' }), undefined);
});
test('rejects unknown tools and traversal without reading credentials', async () => {
  const handle = createHandler({ tokenFile: '/nonexistent' });
  for (const params of [{ name: 'submit', arguments: {} }, { name: 'kynly_job_status', arguments: { job_id: '../secret' } }]) {
    assert.equal((await handle(rpc('tools/call', params))).result.isError, true);
  }
});
test('real HTTP GET authenticates and returns observed status', async () => {
  const root = await mkdtemp(join(tmpdir(), 'kynly-mcp-'));
  const tokenFile = join(root, 'token');
  const token = 'a'.repeat(64);
  await writeFile(tokenFile, token);
  const server = createServer((req, res) => {
    assert.equal(req.method, 'GET');
    assert.equal(req.headers.authorization, 'Bearer ' + token);
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ status: 'passed', exit_code: 0 }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const handle = createHandler({ tokenFile, baseUrl: 'http://127.0.0.1:' + server.address().port });
    const result = await handle(rpc('tools/call', { name: 'kynly_job_status', arguments: { job_id: 'job-' + 'a'.repeat(32) } }));
    assert.deepEqual(JSON.parse(result.result.content[0].text), { status: 'passed', exit_code: 0 });
  } finally {
    await new Promise(resolve => server.close(resolve));
    await rm(root, { recursive: true });
  }
});
test('missing credential returns redacted error', async () => {
  const result = await createHandler({ tokenFile: '/nonexistent/secret' })(rpc('tools/call', { name: 'kynly_jobs_list' }));
  assert.equal(result.result.isError, true);
  assert.equal(result.result.content[0].text, 'Kynly API or credential unavailable');
});

test('submission fixes task and timeout and forwards stable retry key', async () => {
  const root = await mkdtemp(join(tmpdir(), 'kynly-submit-'));
  const tokenFile = join(root, 'token');
  await writeFile(tokenFile, 'b'.repeat(64));
  const bodies = [];
  const server = createServer(async (req, res) => {
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/jobs');
    assert.equal(req.headers['content-type'], 'application/json');
    let text = ''; for await (const chunk of req) text += chunk;
    bodies.push(JSON.parse(text));
    res.end(JSON.stringify({ job_id: 'job-' + 'a'.repeat(32), status: 'queued' }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const handle = createHandler({ tokenFile, baseUrl: 'http://127.0.0.1:' + server.address().port });
    const request = rpc('tools/call', { name: 'kynly_submit_tests', arguments: { request_key: 'openclaw-test-001' } });
    for (let i=0; i<2; i++) assert.equal((await handle(request)).result.isError, undefined);
    assert.deepEqual(bodies, Array(2).fill({ task: 'tests', timeout_seconds: 30, request_key: 'openclaw-test-001' }));
  } finally {
    await new Promise(resolve => server.close(resolve));
    await rm(root, { recursive: true });
  }
});
test('submission rejects task overrides, timeout overrides, and invalid keys', async () => {
  const handle = createHandler({ tokenFile: '/missing' });
  for (const args of [{request_key:'ok',task:'probe-failure'}, {request_key:'ok',timeout_seconds:120}, {request_key:''}, {request_key:'a'.repeat(101)}, {request_key:'bad key'}, {request_key:7}]) {
    const response = await handle(rpc('tools/call', { name: 'kynly_submit_tests', arguments: args }));
    assert.equal(response.result.isError, true);
    assert.equal(response.result.content[0].text, 'Unknown tool or invalid arguments');
  }
});
