import test from 'node:test';
import assert from 'node:assert/strict';
import {CommandDispatcher} from '../browser/webgpu-dispatch.mjs';
import {WebGPUEngine} from '../browser/webgpu-engine.mjs';

test('FIFO tasks yield between packets and acknowledge only consumed payloads',()=>{
  const tasks=[],events=[];let now=0;
  const dispatcher=new CommandDispatcher({budgetMs:4,now:()=>now,post:task=>tasks.push(task)});
  const owned=new Uint8Array([1,2,3,4]);
  for(let i=0;i<3;i++)dispatcher.enqueue(()=>{events.push(['run',i,[...owned]]);now+=5;},ok=>events.push(['ack',i,ok]));
  assert.equal(tasks.length,1);assert.deepEqual(events,[]);
  tasks.shift()();assert.deepEqual(events,[['run',0,[1,2,3,4]],['ack',0,true]]);assert.equal(tasks.length,1);
  tasks.shift()();tasks.shift()();assert.equal(events.length,6);assert.equal(tasks.length,0);dispatcher.dispose();
});

test('commands appended while draining retain order and schedule exactly once',()=>{
  const tasks=[],events=[];
  const dispatcher=new CommandDispatcher({post:task=>tasks.push(task)});
  dispatcher.enqueue(()=>{events.push('first');dispatcher.enqueue(()=>events.push('last'));});
  dispatcher.enqueue(()=>events.push('middle'));
  tasks.shift()();while(tasks.length)tasks.shift()();
  assert.deepEqual(events,['first','middle','last']);dispatcher.dispose();
});

test('failed command rejects remaining work without executing or reading its payloads',()=>{
  const tasks=[],events=[],error=new Error('original failure');
  const dispatcher=new CommandDispatcher({post:task=>tasks.push(task)});
  dispatcher.enqueue(()=>{throw error;},ok=>events.push(['ack',0,ok]),actual=>events.push(actual));
  dispatcher.enqueue(()=>assert.fail('pending command ran'),ok=>events.push(['ack',1,ok]));
  tasks.shift()();assert.deepEqual(events,[['ack',0,false],['ack',1,false],error]);assert.equal(dispatcher.disposed,true);
  dispatcher.enqueue(()=>assert.fail('late command ran'),ok=>events.push(['late',ok]));assert.deepEqual(events.at(-1),['late',false]);
});

test('disposal cancels queued work and an active command is acknowledged once',()=>{
  const tasks=[],events=[];
  const dispatcher=new CommandDispatcher({post:task=>tasks.push(task)});
  dispatcher.enqueue(()=>{dispatcher.dispose();assert.deepEqual(events,[['queued',false]]);},ok=>events.push(['active',ok]));
  dispatcher.enqueue(()=>assert.fail('cancelled command ran'),ok=>events.push(['queued',ok]));
  tasks.shift()();dispatcher.dispose();assert.deepEqual(events,[['queued',false],['active',false]]);
});

test('frame telemetry follows its ordered presentation after yielding',()=>{
  const tasks=[],events=[];let now=0;
  const dispatcher=new CommandDispatcher({budgetMs:1,now:()=>now,post:task=>tasks.push(task)});
  for(const name of ['commands-1','commands-2','present','frame-observer'])
    dispatcher.enqueue(()=>{events.push(name);now+=2;});
  while(tasks.length)tasks.shift()();
  assert.deepEqual(events,['commands-1','commands-2','present','frame-observer']);dispatcher.dispose();
});

test('presentation waits for distinct display callbacks without overtaking commands or telemetry',()=>{
  const tasks=[],frames=[],events=[];
  const dispatcher=new CommandDispatcher({now:()=>0,post:task=>tasks.push(task),postFrame:task=>{frames.push(task);return ()=>{};}});
  for(const name of ['commands-1','present-1','observer-1','commands-2','present-2','observer-2'])
    dispatcher.enqueue(()=>events.push(name),ok=>events.push([name,ok]),undefined,name.startsWith('present'));
  tasks.shift()();
  assert.deepEqual(events,['commands-1',['commands-1',true]]);
  assert.equal(frames.length,1);assert.equal(tasks.length,0);
  frames.shift()();
  assert.deepEqual(events.slice(2),['present-1',['present-1',true],'observer-1',['observer-1',true],'commands-2',['commands-2',true]]);
  assert.equal(frames.length,1);frames.shift()();
  assert.deepEqual(events.slice(-4),['present-2',['present-2',true],'observer-2',['observer-2',true]]);
  assert.equal(frames.length,0);dispatcher.dispose();
});

test('cancelling a pending display callback rejects payloads once without executing them',()=>{
  const tasks=[],frames=[],events=[];let cancelled=0;
  const dispatcher=new CommandDispatcher({post:task=>tasks.push(task),postFrame:task=>{frames.push(task);return ()=>cancelled++;}});
  dispatcher.enqueue(()=>assert.fail('cancelled presentation ran'),ok=>events.push(ok),undefined,true);
  tasks.shift()();assert.deepEqual(events,[]);dispatcher.dispose();
  assert.equal(cancelled,1);assert.deepEqual(events,[false]);
  frames.shift()();assert.deepEqual(events,[false]);
});

test('browser presentation drains on visibility loss and releases RAF ownership',()=>{
  const saved={document:globalThis.document,requestAnimationFrame:globalThis.requestAnimationFrame,cancelAnimationFrame:globalThis.cancelAnimationFrame};
  const tasks=[],events=[],listeners=new Map();let callback,cancelled;
  try {
    globalThis.document={hidden:false,addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:name=>listeners.delete(name)};
    globalThis.requestAnimationFrame=fn=>{callback=fn;return 42;};globalThis.cancelAnimationFrame=id=>{cancelled=id;};
    const dispatcher=new CommandDispatcher({post:task=>tasks.push(task)});
    dispatcher.enqueue(()=>events.push('present'),ok=>events.push(ok),undefined,true);
    tasks.shift()();assert.deepEqual(events,[]);globalThis.document.hidden=true;listeners.get('visibilitychange')();
    assert.deepEqual(events,['present',true]);assert.equal(cancelled,42);assert.equal(listeners.size,0);
    callback();assert.deepEqual(events,['present',true]);dispatcher.dispose();
  } finally {for(const [key,value] of Object.entries(saved)){if(value===undefined)delete globalThis[key];else globalThis[key]=value;}}
});

test('streamed binary packets preserve shared state, float bits and signed draw offsets',()=>{
  const uniform=new Uint8Array(16),pipeline={},draws=[];
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{stats:{commandBatches:0},
    get(id){assert.equal(id,41);return pipeline;},
    bindings:new Map([[9,{type:'uniform',shader:{uniformBlocks:new Map([[0,uniform]])},block:{binding:0},member:{offset:0}}]]),
    draw(indexed,words,start){draws.push({pipeline:this.currentPipeline,uniform:[...new Float32Array(uniform.buffer)],base:words[start+4]|0});}});
  function packet(values,first) {
    const bytes=new Uint8Array(128);new Float32Array(bytes.buffer,0,4).set(values);
    const words=[...(first?[0,41]:[]),4,9,0,4,9,0,3,0,1,0xfffffffd];
    new Uint32Array(bytes.buffer,32,words.length).set(words);
    engine.call('commands',[['binaryCommands',[32,words.length]]],bytes);bytes.fill(255);
  }
  packet([1e-12,-0,Math.fround(1/3),1e20],true);packet([5,6,7,8],false);
  assert.equal(engine.stats.commandBatches,2);assert.equal(draws[1].pipeline,pipeline);
  assert.deepEqual(draws[0].uniform,[Math.fround(1e-12),-0,Math.fround(1/3),Math.fround(1e20)]);
  assert.deepEqual(draws[1].uniform,[5,6,7,8]);assert.equal(draws[0].base,-3);assert.equal(draws[1].base,-3);
});
