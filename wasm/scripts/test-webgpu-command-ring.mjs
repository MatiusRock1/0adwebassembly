import test from 'node:test';
import assert from 'node:assert/strict';
import {CommandRing,RING_HEADER_BYTES,RING_RECORD_BYTES} from '../browser/webgpu-command-ring.mjs';

// Writes the ring exactly as Device.cpp does (CommandRing, RingRecord).
function engineRing(capacity,bytes=4096,address=64){
  const memory={buffer:new SharedArrayBuffer(bytes)};
  new Uint32Array(memory.buffer).set([0,0,capacity,RING_RECORD_BYTES],address/4);
  let heap=address+RING_HEADER_BYTES+capacity*RING_RECORD_BYTES;
  const text=value=>{const encoded=new TextEncoder().encode(value),pointer=heap;new Uint8Array(memory.buffer).set(encoded,pointer);heap+=encoded.length;return [pointer,encoded.length];};
  const publish=({method,args='[]',data=0,size=0,sequence=0,ready=4,result=0,publishedAt=0})=>{
    const signed=new Int32Array(memory.buffer),words=new Uint32Array(memory.buffer);
    const head=Atomics.load(signed,address/4)>>>0,base=address+RING_HEADER_BYTES+(head%capacity)*RING_RECORD_BYTES;
    new Float64Array(memory.buffer)[base/8]=publishedAt;
    words.set([...text(method),...text(args),data,size,sequence,ready,result,result?1:0],base/4+2);
    Atomics.store(signed,address/4,(head+1)|0);Atomics.notify(signed,address/4);
  };
  const tail=()=>Atomics.load(new Int32Array(memory.buffer),address/4+1)>>>0;
  const grow=extra=>{const next=new SharedArrayBuffer(memory.buffer.byteLength+extra);new Uint8Array(next).set(new Uint8Array(memory.buffer));memory.buffer=next;heap=memory.buffer.byteLength-extra;};
  return {memory,address,publish,tail,grow};
}

test('records keep publication order and call fields, and free their slots across wraparound',()=>{
  const engine=engineRing(4),ring=new CommandRing(engine.memory,engine.address,4);
  engine.publish({method:'commands',args:'[["draw",[0,3]]]',data:1024,size:64,sequence:1,ready:16,publishedAt:1234.5});
  engine.publish({method:'createBuffer',args:'["vertices",0,64,0]',ready:20,result:24});
  engine.publish({method:'present',args:'[32,33.33]',sequence:2,ready:28});
  const first=ring.poll();
  assert.deepEqual(first.map(record=>record.method),['commands','createBuffer','present']);
  assert.deepEqual(first[0],{method:'commands',args:[['draw',[0,3]]],offset:1024,length:64,sequence:1,ready:16,result:undefined,publishedAt:1234.5,ringIndex:1});
  assert.equal(first[1].sequence,undefined,'synchronous calls carry a result instead of a sequence');
  assert.equal(first[1].result,24);assert.deepEqual(first[1].args,['vertices',0,64,0]);
  assert.equal(engine.tail(),3);assert.deepEqual(ring.poll(),[]);
  for(let sequence=3;sequence<=5;sequence++)engine.publish({method:'commands',sequence,ready:16});
  assert.deepEqual(ring.poll().map(record=>[record.sequence,record.ringIndex]),[[3,4],[4,5],[5,6]]);
  assert.equal(engine.tail(),6);assert.equal(ring.stats.records,6);assert.equal(ring.stats.maxBatch,3);
});

test('a grown memory is read through its new buffer',()=>{
  const engine=engineRing(2,1024),ring=new CommandRing(engine.memory,engine.address,2);
  engine.grow(1024);
  engine.publish({method:'commands',args:'[["clear",[1,1,1]]]',sequence:1});
  const [record]=ring.poll();
  assert.ok(record.offset===0&&record.args[0][0]==='clear');
  assert.equal(ring.buffer,engine.memory.buffer);
});

test('an unexpected address or layout is rejected before reading records',()=>{
  const engine=engineRing(4);
  assert.throws(()=>new CommandRing(engine.memory,engine.address+4,4),/Invalid shared command ring/);
  assert.throws(()=>new CommandRing(engine.memory,engine.address,8),/layout changed/);
  assert.throws(()=>new CommandRing(engine.memory,4096,4),/Invalid shared command ring/);
});

test('run delivers records published later and stops once closed',async()=>{
  const engine=engineRing(4),ring=new CommandRing(engine.memory,engine.address,4),delivered=[];
  const running=ring.run(record=>delivered.push(record.sequence));
  await new Promise(resolve=>setTimeout(resolve,5));
  engine.publish({method:'commands',sequence:1});
  await new Promise(resolve=>setTimeout(resolve,5));
  engine.publish({method:'commands',sequence:2});engine.publish({method:'present',sequence:3});
  await new Promise(resolve=>setTimeout(resolve,5));
  assert.deepEqual(delivered,[1,2,3]);
  ring.close();Atomics.notify(new Int32Array(engine.memory.buffer),engine.address/4);
  await running;assert.ok(ring.stats.waits>=2);
});
