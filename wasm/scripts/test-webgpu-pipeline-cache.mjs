import test from 'node:test';
import assert from 'node:assert/strict';
import {PipelineStore,PipelineWarmup,pipelineCacheKey} from '../browser/webgpu-pipeline-cache.mjs';
import {WebGPUEngine} from '../browser/webgpu-engine.mjs';
import {PipelinePending} from '../browser/webgpu-pipeline-pending.mjs';

// The IndexedDB requests PipelineStore uses, completed asynchronously.
function fakeIndexedDB(){
  const stores=new Map(),later=run=>setTimeout(run,0);
  const database={
    createObjectStore(name){stores.set(name,new Map());},
    transaction(name){
      const store=stores.get(name),transaction={objectStore:()=>({
        get(key){const request={};later(()=>{request.result=structuredClone(store.get(key));request.onsuccess?.();});return request;},
        put(value,key){store.set(key,structuredClone(value));later(()=>transaction.oncomplete?.());}
      })};
      return transaction;
    },
    close(){}
  };
  return {stores,open(){const request={result:database};later(()=>{if(!stores.size)request.onupgradeneeded?.();request.onsuccess?.();});return request;}};
}
const recipe=n=>({type:'render',program:'p'+n,variant:'{}'});
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));

test('the cache key separates shader catalogs, GPUs and canvas formats',()=>{
  const diagnostics={adapter:{vendor:'nvidia',architecture:'ampere',device:'',description:''},format:'bgra8unorm'};
  const key=pipelineCacheKey({provenance:{buildFingerprint:'abc'}},diagnostics);
  assert.equal(key,'abc|nvidia|ampere|||bgra8unorm');
  assert.notEqual(pipelineCacheKey({provenance:{buildFingerprint:'abd'}},diagnostics),key);
  assert.notEqual(pipelineCacheKey({provenance:{buildFingerprint:'abc'}},{...diagnostics,format:'rgba8unorm'}),key);
});

test('recipes persist in use order and a later session loads them before its own',async()=>{
  const indexedDB=fakeIndexedDB(),first=new PipelineStore({key:'k',indexedDB,delayMs:0});
  assert.deepEqual(await first.load(),[]);
  for(const n of [1,2,1])first.add(JSON.stringify(recipe(n)));
  await first.close();
  assert.deepEqual(indexedDB.stores.get('recipes').get('k'),{version:1,recipes:[recipe(1),recipe(2)]});
  const second=new PipelineStore({key:'k',indexedDB});
  second.add(JSON.stringify(recipe(3)));
  assert.deepEqual(await second.load(),[recipe(1),recipe(2)]);
  assert.deepEqual([...second.recipes.values()],[recipe(1),recipe(2),recipe(3)]);
  assert.equal(second.stats.loaded,2);
  second.remove(JSON.stringify(recipe(1)));await second.close();
  assert.deepEqual(indexedDB.stores.get('recipes').get('k').recipes,[recipe(2),recipe(3)]);
  assert.equal(indexedDB.stores.get('recipes').has('other'),false);
});

test('the list is bounded and storage failures are reported, never thrown',async()=>{
  const bounded=new PipelineStore({key:'k',indexedDB:fakeIndexedDB(),limit:2,delayMs:0});
  for(const n of [1,2,3])bounded.add(JSON.stringify(recipe(n)));
  assert.equal(bounded.recipes.size,2);await bounded.close();
  const events=[],unavailable=new PipelineStore({key:'k',indexedDB:undefined,report:event=>events.push(event),delayMs:0});
  assert.deepEqual(await unavailable.load(),[]);
  unavailable.add(JSON.stringify(recipe(1)));await unavailable.close();
  assert.ok(events.length>=2&&events.every(event=>event.type==='pipeline-cache-error'));
  assert.equal(unavailable.stats.errors,events.length);
});

test('warm-up keeps use order, bounds concurrency, skips known recipes and drops failures',async()=>{
  const started=[],resolvers=new Map(),failed=[],events=[];let active=0,maxActive=0;
  const engine={warmPipeline(key,item){
    if(item.program==='p3')return null;
    started.push(item.program);active++;maxActive=Math.max(maxActive,active);
    return new Promise((resolve,reject)=>resolvers.set(item.program,{resolve:()=>{active--;resolve();},reject:()=>{active--;reject(new Error('stale'));}}));
  }};
  const recipes=[1,2,3,4,5].map(recipe);
  const warmup=new PipelineWarmup(engine,recipes,{concurrency:2,onFailure:key=>failed.push(JSON.parse(key).program),report:event=>events.push(event)});
  const done=warmup.start();
  assert.deepEqual(started,['p1','p2']);
  resolvers.get('p1').resolve();await tick();
  assert.deepEqual(started,['p1','p2','p4'],'p3 is already compiled');
  resolvers.get('p2').reject();await tick();
  resolvers.get('p4').resolve();await tick();resolvers.get('p5').resolve();
  const stats=await done;
  assert.equal(maxActive,2);assert.deepEqual(failed,['p2']);
  assert.deepEqual({compiled:stats.compiled,skipped:stats.skipped,failed:stats.failed,queued:stats.queued},{compiled:3,skipped:1,failed:1,queued:5});
  assert.deepEqual(events.map(event=>event.type),['pipeline-warmup-skipped','pipeline-warmup']);
});

test('stopping the warm-up leaves the queue without a completion report',async()=>{
  const events=[],engine={warmPipeline:()=>new Promise(()=>{})};
  const warmup=new PipelineWarmup(engine,[recipe(1),recipe(2)],{concurrency:1,report:event=>events.push(event)});
  warmup.start();warmup.stop();
  assert.equal(warmup.queue.length,0);assert.deepEqual(events,[]);
});

// A WebGPU device that records what the engine creates.
function fakeGPU(){
  globalThis.GPUBufferUsage={UNIFORM:1,COPY_DST:2,COPY_SRC:4,MAP_WRITE:8,VERTEX:16,INDEX:32};
  const created={modules:0,pipelines:[]};
  const device={features:new Set(),limits:{minUniformBufferOffsetAlignment:256},lost:new Promise(()=>{}),
    createBuffer:()=>({destroy(){}}),
    createShaderModule:({label})=>{created.modules++;return {label,getCompilationInfo:async()=>({messages:[]})};},
    createBindGroupLayout:({entries})=>({entries}),createPipelineLayout:({bindGroupLayouts})=>({bindGroupLayouts}),
    createBindGroup:descriptor=>({descriptor}),
    createRenderPipelineAsync:descriptor=>new Promise((resolve,reject)=>created.pipelines.push({descriptor,resolve,reject}))};
  return {device,created};
}
const catalog={programs:{model:{defines:['USE_SHADOW'],variants:{'{"USE_SHADOW":"1"}':
  {code:{vertex:'vertex',fragment:'fragment'},uniforms:[],textures:[],inputs:[{stream:0,location:0}]}}}}};
const depth=[1,1,1,0,255,255,0,[],[]],blend=[1,6,7,0,1,7,0,[0,0,0,0],15],raster=[0,2,0,0,0,0];
function engineWith(device){
  const engine=new WebGPUEngine({device,diagnostics:{format:'bgra8unorm'}},null,catalog);
  engine.asyncPipelines=true;
  const calls=[];engine.pass=Object.fromEntries(['setPipeline','setBlendConstant','setStencilReference','setVertexBuffer','draw'].map(name=>[name,(...args)=>calls.push([name,...args])]));
  engine.attachments={format:'bgra8unorm',depthFormat:'depth24plus-stencil8',samples:1};
  engine.vertices.set(0,{buffer:{buffer:'vertices'},offset:0});
  return {engine,calls};
}
function prepare(engine){
  const shader=engine.call('createShader',['model',{USE_SHADOW:'1'}]);
  engine.currentPipeline=engine.get(engine.call('createPipeline',[shader,depth,blend,raster]));
  engine.currentLayout=engine.get(engine.call('createLayout',[[0,24,0,12,0,0],[1,23,12,20,0,0]]));
}
// Modules of different engines are different objects; compare their labels.
const portable=descriptor=>JSON.parse(JSON.stringify(descriptor,(key,value)=>key==='module'?value.label:key==='layout'?'layout':value));

test('engine objects with equal state share shader modules and one compiled pipeline',async()=>{
  const {device,created}=fakeGPU(),{engine,calls}=engineWith(device);
  prepare(engine);
  assert.throws(()=>engine.draw(false,[0,3,0,1]),PipelinePending);
  assert.equal(created.pipelines.length,1);
  created.pipelines[0].resolve('gpu pipeline');await tick();
  engine.draw(false,[0,3,0,1]);
  assert.deepEqual(calls.find(call=>call[0]==='setPipeline'),['setPipeline','gpu pipeline']);
  prepare(engine);engine.draw(false,[0,3,0,1]);
  assert.equal(created.modules,2,'one vertex and one fragment module for the variant');
  assert.equal(created.pipelines.length,1,'recreated engine objects reuse the compiled pipeline');
  assert.equal(engine.stats.pipelineContentHits,1);assert.equal(engine.stats.pipelineCompiles,1);
  assert.deepEqual(created.pipelines[0].descriptor.vertex.buffers,[{arrayStride:12,stepMode:'vertex',attributes:[{shaderLocation:0,offset:0,format:'float32x3'}]}],
    'the original stream filter keeps only inputs of the variant');
});

test('a stored recipe compiles before the first draw and is not stored again',async()=>{
  const first=fakeGPU(),{engine:recorder}=engineWith(first.device),stored=[];
  recorder.onPipelineRecipe=key=>stored.push(key);
  prepare(recorder);assert.throws(()=>recorder.draw(false,[0,3,0,1]),PipelinePending);
  assert.equal(stored.length,1);
  const second=fakeGPU(),{engine,calls}=engineWith(second.device);
  engine.onPipelineRecipe=key=>stored.push(key);
  const warm=engine.warmPipeline(stored[0],JSON.parse(stored[0]));
  assert.equal(engine.warmPipeline(stored[0],JSON.parse(stored[0])),null,'a recipe compiles once');
  second.created.pipelines[0].resolve('warm pipeline');await warm;
  prepare(engine);engine.draw(false,[0,3,0,1]);
  assert.deepEqual(calls.find(call=>call[0]==='setPipeline'),['setPipeline','warm pipeline']);
  assert.equal(second.created.pipelines.length,1);assert.equal(stored.length,1);
  assert.equal(engine.stats.pipelineWarmHits,1);assert.equal(engine.stats.pipelineWarmCompiles,1);
  assert.deepEqual(portable(second.created.pipelines[0].descriptor),portable(first.created.pipelines[0].descriptor),
    'the stored recipe rebuilds the same descriptor');
});

test('a variant created again does not ask its shared modules for their compilation again',async()=>{
  // Chrome 156 never answered a second getCompilationInfo() on such a module.
  const {device}=fakeGPU(),queries=[];
  device.createShaderModule=({label})=>({label,getCompilationInfo(){
    queries.push(label);return queries.filter(query=>query===label).length===1?Promise.resolve({messages:[]}):new Promise(()=>{});
  }});
  const {engine}=engineWith(device);
  const first=await engine.callAsync('createShader',['model',{USE_SHADOW:'1'}],new Uint8Array());
  const timeout=new Promise((_,reject)=>setTimeout(()=>reject(new Error('createShader waited for a second query')),200));
  const second=await Promise.race([engine.callAsync('createShader',['model',{USE_SHADOW:'1'}],new Uint8Array()),timeout]);
  assert.notEqual(first,second);assert.deepEqual(queries,['model vertex','model fragment']);
});

test('a compilation error of the variant still fails createShader',async()=>{
  const {device}=fakeGPU();
  device.createShaderModule=({label})=>({label,getCompilationInfo:async()=>({messages:label.endsWith('fragment')?[{type:'error',message:'bad fragment'}]:[]})});
  const {engine}=engineWith(device);
  await assert.rejects(engine.callAsync('createShader',['model',{USE_SHADOW:'1'}],new Uint8Array()),/bad fragment/);
});

test('a failed compilation is forgotten, so the next draw compiles again',async()=>{
  const {device,created}=fakeGPU(),{engine}=engineWith(device);
  prepare(engine);
  let pending;try{engine.draw(false,[0,3,0,1]);}catch(error){pending=error.promise;}
  created.pipelines[0].reject(new Error('device lost'));
  await assert.rejects(pending,/device lost/);
  assert.throws(()=>engine.draw(false,[0,3,0,1]),PipelinePending);
  assert.equal(created.pipelines.length,2);
});
