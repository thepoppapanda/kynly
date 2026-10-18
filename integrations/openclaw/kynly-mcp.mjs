// Read-only MCP stdio adapter for Kynly. Node 22+; no dependencies.
import { readFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { pathToFileURL } from 'node:url';

const tools = [
  { name: 'kynly_jobs_list', description: 'List up to 50 recent Kynly jobs and their recorded statuses. Does not run jobs.', inputSchema: { type: 'object', properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true } },
  { name: 'kynly_job_status', description: 'Get the recorded status and exit code of one Kynly job by its exact job ID.', inputSchema: { type: 'object', properties: { job_id: { type: 'string', pattern: '^job-[0-9a-f]{32}$' } }, required: ['job_id'], additionalProperties: false }, annotations: { readOnlyHint: true } },
];

export function createHandler({ tokenFile = '/home/node/.openclaw/kynly-tools/api-token.txt', baseUrl = 'http://host.docker.internal:8787' } = {}) {
  return async function handle(message) {
    if (!message || message.jsonrpc !== '2.0' || typeof message.method !== 'string') return { jsonrpc: '2.0', id: message?.id ?? null, error: { code: -32600, message: 'Invalid request' } };
    if (message.id === undefined) return undefined;
    const reply = result => ({ jsonrpc: '2.0', id: message.id, result });
    if (message.method === 'initialize') return reply({ protocolVersion: '2025-03-26', capabilities: { tools: { listChanged: false } }, serverInfo: { name: 'kynly-readonly', version: '0.1.0' } });
    if (message.method === 'ping') return reply({});
    if (message.method === 'tools/list') return reply({ tools });
    if (message.method !== 'tools/call') return { jsonrpc: '2.0', id: message.id, error: { code: -32601, message: 'Method not found' } };
    try {
      const name = message.params?.name;
      const args = message.params?.arguments ?? {};
      if (!args || typeof args !== 'object' || Array.isArray(args)) throw Error('Arguments must be an object');
      let path;
      if (name === 'kynly_jobs_list' && Object.keys(args).length === 0) path = '/jobs';
      else if (name === 'kynly_job_status' && Object.keys(args).length === 1 && /^job-[0-9a-f]{32}$/.test(args.job_id)) path = '/jobs/' + args.job_id;
      else throw Error('Unknown tool or invalid arguments');
      const token = (await readFile(tokenFile, 'utf8')).trim();
      if (token.length < 32) throw Error('Credential unavailable');
      const response = await fetch(baseUrl + path, { headers: { Authorization: 'Bearer ' + token }, signal: AbortSignal.timeout(10000), redirect: 'error' });
      if (!response.ok) throw Error('Kynly API returned HTTP ' + response.status);
      const data = await response.json();
      return reply({ content: [{ type: 'text', text: JSON.stringify(data) }] });
    } catch (error) {
      // File errors and network exceptions can include internal details; redact them.
      const text = /^(Unknown tool|Arguments must|Kynly API returned HTTP)/.test(error.message) ? error.message : 'Kynly API or credential unavailable';
      return reply({ isError: true, content: [{ type: 'text', text }] });
    }
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const handle = createHandler();
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  for await (const line of lines) {
    let response;
    try {
      if (Buffer.byteLength(line) > 65536) throw Error('Oversized request');
      const parsed = JSON.parse(line);
      if (Array.isArray(parsed)) {
        response = [];
        for (const item of parsed) { const answer = await handle(item); if (answer) response.push(answer); }
        if (!response.length) continue;
      } else response = await handle(parsed);
    } catch {
      response = { jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Invalid JSON request' } };
    }
    if (response) process.stdout.write(JSON.stringify(response) + '\n');
  }
}
