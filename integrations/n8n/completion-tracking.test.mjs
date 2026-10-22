import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
const workflow = JSON.parse(readFileSync(new URL('./kynly-completion-tracking.json', import.meta.url)));
const node = name => workflow.nodes.find(n => n.name === name);
const id = 'job-' + 'a'.repeat(32);
const tracking = {job_id:id, request_key:'test-key', max_checks:12, deadline_ms:120000};
function evaluate(status, index=0, now=0, jobId=id) {
  const sandbox = {
    $input:{first:()=>({json:{job_id:jobId,status,exit_code:status==='passed'?0:null}})},
    $:()=>({first:()=>({json:tracking})}), $runIndex:index, Date:{now:()=>now}
  };
  return JSON.parse(JSON.stringify(runInNewContext('(function(){'+node('Evaluate Status').parameters.jsCode+'})()', sandbox)))[0].json;
}
test('every terminal state stops monitoring with its original status', () => {
  for(const status of ['passed','failed','timed_out','cancelled','interrupted']) {
    const result=evaluate(status);
    assert.equal(result.should_continue,false);
    assert.equal(result.monitoring_outcome,'job_finished');
    assert.equal(result.status,status);
  }
});
test('active jobs continue below bounds and stop at check 12', () => {
  for(const status of ['queued','running']) {
    assert.equal(evaluate(status).should_continue,true);
    const last=evaluate(status,11);
    assert.equal(last.checks,12);
    assert.equal(last.should_continue,false);
    assert.equal(last.monitoring_outcome,'monitoring_limit_reached');
  }
});
test('deadline independently stops polling', () => {
  const result=evaluate('running',1,116000);
  assert.equal(result.checks,2);
  assert.equal(result.monitoring_outcome,'monitoring_limit_reached');
});
test('wrong ID and unknown status fail without continuing', () => {
  assert.throws(()=>evaluate('running',0,0,'job-'+'b'.repeat(32)),/wrong job ID/);
  assert.throws(()=>evaluate('invented'),/Unexpected job status/);
});
test('summary distinguishes monitoring limit from task timeout', () => {
  function summary(result) {
    return JSON.parse(JSON.stringify(runInNewContext('(function(){'+node('Result Summary').parameters.jsCode+'})()',{$input:{first:()=>({json:result})}})))[0].json;
  }
  assert.equal(summary(evaluate('passed')).outcome,'passed');
  assert.equal(summary(evaluate('timed_out')).outcome,'job_unsuccessful');
  const limited=summary(evaluate('running',11));
  assert.equal(limited.outcome,'monitoring_limit_reached');
  assert.equal(limited.job_status,'running');
});
test('template uses credential selection, bounded requests, and no submission loop', () => {
  assert.equal(workflow.active,false);
  for(const n of workflow.nodes.filter(n=>n.type==='n8n-nodes-base.httpRequest')) {
    assert.equal(n.parameters.options.timeout,n.name==='Desktop Notification'?30000:5000);
    assert.equal(n.parameters.genericAuthType,'httpHeaderAuth');
    assert.equal(n.retryOnFail,false);
    assert.equal(n.credentials,undefined);
  }
  assert.deepEqual(node('Wait').parameters,{resume:'timeInterval',amount:5,unit:'seconds'});
  assert.equal(workflow.connections.Wait.main[0][0].node,'Check Job');
  assert.equal(workflow.connections.If.main[1][0].node,'Result Summary');
  assert.equal(node('Tracking Setup').parameters.jsCode.includes('max_checks: 12'),true);
  assert.equal(node('Tracking Setup').parameters.jsCode.includes('Date.now() + 120000'),true);
});

test('notification follows the final summary and serializes only that input', () => {
  const notification=node('Desktop Notification');
  assert.equal(workflow.connections['Result Summary'].main[0][0].node,'Desktop Notification');
  assert.equal(notification.parameters.url,'http://host.docker.internal:8787/notifications');
  assert.equal(notification.parameters.method,'POST');
  assert.equal(notification.parameters.jsonBody,'={{ JSON.stringify($json) }}');
});
