import test from 'node:test';
import assert from 'node:assert/strict';
import { WebGPUEngine } from '../browser/webgpu-engine.mjs';

test('queue failure during engine disposal still frees resources and closes the session',async()=>{
  const released=[];
  const resource=name=>({destroy(){released.push(name);}});
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    live:true,submit(){},device:{queue:{onSubmittedWorkDone:()=>Promise.reject(new Error('lost'))}},
    report:event=>released.push(event.type),objects:new Map([
      [1,{kind:'buffer',buffer:resource('buffer')}],
      [2,{kind:'texture',texture:resource('texture')}],
      [3,{kind:'stagingTexture',buffer:resource('staging'),texture:resource('borrowed-target')}]
    ]),bindings:new Map([[1,{}]]),pipelines:new Map([[1,{}]]),
    transientArenas:{vertex:[{buffer:resource('vertices')}],index:[{buffer:resource('indices')}]},
    uniformBuffer:resource('uniforms'),depthTexture:resource('depth'),presentationTexture:resource('presentation'),
    session:{async dispose(){released.push('session');}}
  });
  await engine.dispose();await engine.dispose();
  assert.deepEqual(released,['engine-drain-error','buffer','texture','staging','vertices','indices','uniforms','depth','presentation','session']);
  assert.equal(engine.objects.size+engine.bindings.size+engine.pipelines.size,0);
});

test('retirement waits for submitted work and drops shader bindings and pipeline cache entries',async()=>{
  let complete;const destroyed=[];
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    device:{queue:{onSubmittedWorkDone:()=>new Promise(resolve=>{complete=resolve;})}},
    objects:new Map([[1,{kind:'buffer',buffer:{destroy(){destroyed.push(1);}}}],
      [2,{kind:'shader',bindingSlots:new Map([['transform',7]])}],
      [3,{kind:'pipeline',identity:42}]]),
    retired:new Set([1,2,3]),bindings:new Map([[7,{}]]),pipelines:new Map([['[42,43,"rgba8unorm"]',{}],['[44,45,"rgba8unorm"]',{}]]),
    transientArenas:{vertex:[],index:[]},stats:{},report(){}
  });
  engine.submit();assert.deepEqual(destroyed,[]);assert.equal(engine.objects.size,3);
  complete();await Promise.resolve();
  assert.deepEqual(destroyed,[1]);assert.equal(engine.objects.size,0);assert.equal(engine.bindings.size,0);
  assert.deepEqual([...engine.pipelines.keys()],['[44,45,"rgba8unorm"]']);
});

test('retired textures drop only bind groups that retain their views after queue completion',async()=>{
  let complete;let destroyed=false;
  const groups=new Map([['1,4',{}],['2,4',{}],['11,4',{}]]);
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    device:{queue:{onSubmittedWorkDone:()=>new Promise(resolve=>{complete=resolve;})}},
    objects:new Map([[1,{kind:'texture',texture:{destroy(){destroyed=true;}}}],
      [3,{kind:'shader',textureGroups:groups}]]),
    retired:new Set([1]),bindings:new Map(),pipelines:new Map(),
    transientArenas:{vertex:[],index:[]},stats:{},report(){}
  });
  engine.submit();assert.equal(groups.size,3);assert.equal(destroyed,false);
  complete();await Promise.resolve();
  assert.equal(destroyed,true);assert.deepEqual([...groups.keys()],['2,4','11,4']);
});

test('retiring storage resources invalidates cached groups after submitted work completes',async()=>{
  let complete;
  const shader={kind:'shader',storageGroups:new Map([['1,2',{}],['11,2',{}]]),lastStorageGroup:{},lastStorageIds:[1,2]};
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    device:{queue:{onSubmittedWorkDone:()=>new Promise(resolve=>{complete=resolve;})}},
    objects:new Map([[1,{kind:'buffer',buffer:{destroy(){}}}],[3,shader]]),retired:new Set([1]),
    bindings:new Map(),pipelines:new Map(),transientArenas:{vertex:[],index:[]},stats:{},report(){}
  });
  engine.submit();assert.equal(shader.storageGroups.size,2);assert.ok(shader.lastStorageGroup);
  complete();await Promise.resolve();
  assert.deepEqual([...shader.storageGroups.keys()],['11,2']);assert.equal(shader.lastStorageGroup,null);
});

test('shared device health follows actual loss and detaches only its registered owner',async()=>{
  globalThis.GPUBufferUsage={UNIFORM:1,COPY_DST:2};
  let lose;const events=[],heap=new Uint8Array(new SharedArrayBuffer(16)),words=new Int32Array(heap.buffer);
  const device={createBuffer:()=>({destroy(){}}),lost:new Promise(resolve=>{lose=resolve;})};
  const engine=new WebGPUEngine({device},null,{},event=>events.push(event));engine.heap=()=>heap;
  engine.call('observeLive',[4,1]);assert.equal(Atomics.load(words,1),1);
  engine.call('observeLive',[8,0]);assert.equal(engine.liveAddress,4,'another address cannot detach the owner');
  for(const address of [0,2,16,-4,.5,NaN])assert.throws(()=>engine.call('observeLive',[address,1]),/Invalid shared/);
  lose({reason:'unknown',message:'controlled loss'});await Promise.resolve();
  assert.equal(Atomics.load(words,1),0);assert.equal(engine.live,false);assert.equal(events[0].expected,false);
  engine.call('observeLive',[4,0]);Atomics.store(words,1,12345);engine.publishLiveState();
  assert.equal(Atomics.load(words,1),12345,'no writes after the C++ owner unregisters');
});

test('disposal publishes unavailable before draining and cannot write a detached health address',async()=>{
  globalThis.GPUBufferUsage={UNIFORM:1,COPY_DST:2};
  let lose;const heap=new Uint8Array(new SharedArrayBuffer(16)),words=new Int32Array(heap.buffer);
  const device={createBuffer:()=>({destroy(){}}),lost:new Promise(resolve=>{lose=resolve;}),
    queue:{onSubmittedWorkDone:async()=>{assert.equal(Atomics.load(words,1),0);}}};
  const engine=new WebGPUEngine({device,dispose:async()=>{}},null,{});engine.heap=()=>heap;
  engine.call('observeLive',[4,1]);await engine.dispose();
  assert.equal(engine.liveAddress,0);Atomics.store(words,1,6789);
  lose({reason:'destroyed',message:''});await Promise.resolve();
  assert.equal(Atomics.load(words,1),6789);
});
