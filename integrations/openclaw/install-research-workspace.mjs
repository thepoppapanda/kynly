// Run explicitly with Node inside the OpenClaw container; never touches Slate.
import { readFile, writeFile, mkdir, copyFile, rename } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root='/home/node/.openclaw/workspace-research';
const source=await readFile(join(dirname(fileURLToPath(import.meta.url)),'RESEARCH_AGENT.md'),'utf8');
const files={
  'AGENTS.md':source,
  'SOUL.md':'Be concise, truthful, and precise. Research public sources within the user\'s call budget.\n',
  'IDENTITY.md':'Name: Ruby\nRole: Public-source research\n',
  'USER.md':'The user is building Kynly and tests each component incrementally.\n',
  'TOOLS.md':'Only web_search and web_fetch are intended. No job-control tools.\n',
  'HEARTBEAT.md':'# No periodic tasks configured\n',
};
const backup=join(root,'.bootstrap-backups',String(Date.now()));
await mkdir(backup,{recursive:true});
for(const [name,content] of Object.entries(files)){
  try {await copyFile(join(root,name),join(backup,name));} catch(error){if(error.code!=='ENOENT')throw error;}
  await writeFile(join(root,name),content);
}
try {await rename(join(root,'BOOTSTRAP.md'),join(backup,'BOOTSTRAP.md'));}catch(error){if(error.code!=='ENOENT')throw error;}
console.log('Research instructions installed; generated files backed up. Slate workspace unchanged.');
