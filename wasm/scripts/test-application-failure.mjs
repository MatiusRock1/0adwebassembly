import test from 'node:test';
import assert from 'node:assert/strict';
import {installApplicationFailureBoundary} from '../browser/application-failure.mjs';

const runtimeURL='http://localhost:8095/pyrogenesis-application.mjs';
function fixture(overrides={}) {
  const target=new EventTarget(),calls=[],failures=[],reports=[];
  const boundary=installApplicationFailureBoundary({eventTarget:target,runtimeURL,
    getApplication:()=>({stopAbortedApplication(){calls.push('stop');}}),
    releasePointer(){calls.push('pointer');},disposeRenderer(){calls.push('renderer');},
    onFailure(reason,cleanup){failures.push({reason,cleanup});},report(error){reports.push(error);},...overrides});
  return {target,calls,failures,reports,boundary};
}
function runtimeError(target,filename=runtimeURL) {
  const event=new Event('error');
  Object.assign(event,{filename,error:{message:'null function'}});
  target.dispatchEvent(event);
}

test('owned runtime failure stops SDK listeners/workers before releasing pointer and disposes renderer',async()=>{
  const f=fixture();runtimeError(f.target);
  assert.equal(f.failures[0].reason,'null function');
  await f.failures[0].cleanup;
  assert.deepEqual(f.calls,['stop','pointer','renderer']);
  assert.deepEqual(f.reports,[]);
});

test('unrelated script errors and events after normal disposal do not abort the game',()=>{
  const f=fixture();runtimeError(f.target,'http://localhost:8095/other.mjs');
  assert.deepEqual(f.failures,[]);
  f.boundary.dispose();runtimeError(f.target);
  assert.deepEqual(f.failures,[]);
});

test('repeated SDK and worker failures share one cleanup and preserve first cause',async()=>{
  const f=fixture();const first=f.boundary.abort('original worker fault');
  runtimeError(f.target);
  assert.equal(f.boundary.abort('secondary proxy failure'),first);
  await first;
  assert.equal(f.failures.length,1);
  assert.equal(f.failures[0].reason,'original worker fault');
  assert.deepEqual(f.calls,['stop','pointer','renderer']);
});

test('startup fallback and cleanup errors still release pointer and renderer',async()=>{
  const f=fixture({getApplication:()=>undefined});
  const stopped=new Error('SDK cleanup failed');
  const cleanup=f.boundary.abort('startup abort',{stopAbortedApplication(){f.calls.push('stop');throw stopped;}});
  await assert.rejects(cleanup,error=>error instanceof AggregateError && error.errors.includes(stopped));
  assert.deepEqual(f.calls,['stop','pointer','renderer']);
  assert.equal(f.reports.length,1);
});


test('fatal cleanup removes input synchronously and survives reentrant abort',async()=>{
  let boundary, nested;
  const calls=[];
  ({boundary}=fixture({getApplication:()=>({stopAbortedApplication(){
    calls.push('stop');
    nested=boundary.abort('secondary callback failure');
  }}),releasePointer(){calls.push('pointer');}}));
  const cleanup=boundary.abort('original worker failure');
  assert.deepEqual(calls,['stop','pointer']);
  assert.equal(nested,cleanup);
  await cleanup;
});
