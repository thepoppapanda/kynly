import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHandler } from './kynly-mcp.mjs';

const rpc = (method, params) => ({ jsonrpc: '2.0', id: 1, method, params });
test('initialization and read-only catalog', async () => {
  const handle = createHandler();
  assert.equal((await handle(rpc('initialize'))).result.serverInfo.name, 'kynly-readonly');
  const names = (await handle(rpc('tools/list'))).result.tools.map(t => t.name);
  assert.deepEqual(names, ['kynly_jobs_list', 'kynly_job_status']);
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
