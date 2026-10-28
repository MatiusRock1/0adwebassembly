import test from 'node:test';
import assert from 'node:assert/strict';
import {ArchiveBlocks} from '../browser/archive-blocks.mjs';
import {validateSharedRequest,completeSharedRequest} from '../browser/shared-request.mjs';
import {WebGPUEngine} from '../browser/webgpu-engine.mjs';
import {PipelinePending} from '../browser/webgpu-pipeline-pending.mjs';

async function archiveFixture({storage=null,maxMemoryBytes=8,corrupt=false,status=206}={}){
  const source=Uint8Array.from({length:19},(_,i)=>i*11),hashes=[];
  for(let i=0;i<source.length;i+=4){const hash=await crypto.subtle.digest('SHA-256',source.slice(i,i+4));hashes.push(Buffer.from(hash).toString('hex'));}
  const manifest={blockBytes:4,archives:{public:{bytes:source.length,blocks:hashes}}},requests=[];
  const fetcher=async(url,{headers})=>{
    const [,a,b]=/^bytes=(\d+)-(\d+)$/.exec(headers.Range),start=Number(a),end=Number(b);
    requests.push([start,end]);const bytes=source.slice(start,end+1);if(corrupt)bytes[0]^=255;
    return {status,headers:new Headers({'Content-Range':`bytes ${start}-${end}/${source.length}`}),arrayBuffer:async()=>bytes.buffer,body:{cancel:async()=>{}}};
  };
  return {source,requests,manifest,blocks:new ArchiveBlocks({manifest,baseURL:'https://game.test/',fetcher,storage,maxMemoryBytes})};
}

test('archive reads retain exact bytes across block boundaries and clamp EOF',async()=>{
  const {source,blocks,requests}=await archiveFixture();
  const destination=new Uint8Array(9);assert.equal(await blocks.read('public',3,destination),9);
  assert.deepEqual(destination,source.slice(3,12));assert.deepEqual(requests,[[0,3],[4,7],[8,11]]);
  const tail=new Uint8Array(8).fill(199);assert.equal(await blocks.read('public',17,tail),2);
  assert.deepEqual([...tail],[...source.slice(17),199,199,199,199,199,199]);
  assert.equal(await blocks.read('public',99,tail),0);
  assert.ok(blocks.stats.peakResidentBytes<=8);
});
test('persistent archive blocks survive cache eviction and an offline restart',async()=>{
  const saved=new Map(),storage={get:async key=>saved.get(key),put:async(key,bytes)=>saved.set(key,bytes.slice(0))};
  const first=await archiveFixture({storage,maxMemoryBytes:4});
  const output=new Uint8Array(19);await first.blocks.read('public',0,output);
  assert.deepEqual(output,first.source);assert.equal(saved.size,5);
  const next=new ArchiveBlocks({manifest:first.manifest,baseURL:'https://game.test/',storage,maxMemoryBytes:4,
    fetcher:async()=>{throw new Error('offline');}});
  assert.equal(await next.read('public',0,output),19);assert.deepEqual(output,first.source);
  assert.equal(next.stats.persistentHits,5);assert.equal(next.stats.networkBytes,0);
  assert.ok(next.stats.peakResidentBytes<=4);next.clear();assert.equal(next.stats.residentBytes,0);
});
test('corrupt persistent bytes are replaced only with hash-verified original bytes',async()=>{
  const storage={get:async()=>new Uint8Array(4).fill(255).buffer,put:async()=>{}};
  const {blocks,source}=await archiveFixture({storage});
  assert.deepEqual(await blocks.block('public',0),source.slice(0,4));assert.equal(blocks.stats.persistentHits,0);
});
test('corrupt network bytes and non-range servers fail before populating cache',async()=>{
  for(const options of [{corrupt:true},{status:200}]){
    const {blocks}=await archiveFixture(options);await assert.rejects(blocks.block('public',0));
    assert.equal(blocks.stats.residentBytes,0);
  }
});
test('transient archive failures are retried and final failures name the response',async()=>{
  const fixture=await archiveFixture(),answers=[new TypeError('network'),503,429],seen=[],events=[];
  const fetcher=async(url,init)=>{
    seen.push(init.cache);const answer=answers.shift();
    if(answer instanceof Error)throw answer;
    if(answer)return {status:answer,headers:new Headers(),body:{cancel:async()=>{}}};
    return fixture.blocks.fetcher(url,init);
  };
  const blocks=new ArchiveBlocks({manifest:fixture.manifest,baseURL:'https://game.test/',fetcher,retryDelayMs:0,report:event=>events.push(event)});
  assert.deepEqual(await blocks.block('public',0),fixture.source.slice(0,4));
  assert.deepEqual(seen,['no-store','no-store','no-store','no-store']);
  assert.equal(blocks.stats.networkRetries,3);assert.deepEqual(events.filter(e=>e.type==='archive-retry').map(e=>e.reason),['network','HTTP 503','HTTP 429']);
  const failing=new ArchiveBlocks({manifest:fixture.manifest,baseURL:'https://game.test/',retryDelayMs:0,
    fetcher:async()=>({status:503,headers:new Headers(),body:{cancel:async()=>{}}})});
  await assert.rejects(failing.block('public',0),/HTTP 503 with Content-Range missing/);assert.equal(failing.stats.networkRetries,3);
  const hidden=new ArchiveBlocks({manifest:fixture.manifest,baseURL:'https://game.test/',retryDelayMs:0,
    fetcher:async()=>({status:206,headers:new Headers(),body:{cancel:async()=>{}}})});
  await assert.rejects(hidden.block('public',0),/HTTP 206 with Content-Range missing \(or not exposed by CORS\)/);
  assert.equal(hidden.stats.networkRetries,0);
});
test('parallel demand for the same block is deduplicated',async()=>{
  const {blocks,requests}=await archiveFixture();
  const [a,b]=await Promise.all([blocks.block('public',2),blocks.block('public',2)]);
  assert.equal(a,b);assert.equal(requests.length,1);
});
test('default fetch retains its global receiver as required by browser workers',async()=>{
  const fixture=await archiveFixture(),original=globalThis.fetch;
  globalThis.fetch=function(...args){assert.equal(this,globalThis);return fixture.blocks.fetcher(...args);};
  try{
    const blocks=new ArchiveBlocks({manifest:fixture.manifest,baseURL:'https://game.test/'});
    assert.deepEqual(await blocks.block('public',0),fixture.source.slice(0,4));
  }finally{globalThis.fetch=original;}
});
test('archive memory cache uses LRU and rejects invalid ranges',async()=>{
  const {blocks,requests}=await archiveFixture();
  await blocks.block('public',0);await blocks.block('public',1);await blocks.block('public',0);
  await blocks.block('public',2);await blocks.block('public',1);
  assert.equal(requests.length,4);assert.equal(blocks.stats.memoryHits,1);
  for(const [archive,position] of [['missing',0],['public',-1],['public',1.1]])
    await assert.rejects(blocks.read(archive,position,new Uint8Array(1)));
});
test('shared requests publish values before acknowledgement and reject malformed addresses',()=>{
  const buffer=new SharedArrayBuffer(128),request={buffer,offset:32,length:16,ready:4,result:8};
  validateSharedRequest(request);completeSharedRequest(request,true,-17);
  assert.equal(Atomics.load(new Int32Array(buffer),1),1);assert.equal(Atomics.load(new Int32Array(buffer),2),-17);
  completeSharedRequest(request,false);assert.equal(Atomics.load(new Int32Array(buffer),1),2);
  for(const changes of [{buffer:new ArrayBuffer(128)},{ready:3},{offset:127},{length:-1},{result:4},{result:128}])
    assert.throws(()=>validateSharedRequest({...request,...changes}));
});

test('async pipelines resume binary streams at the pending draw without repeating uploads',async()=>{
  const events=[],pipelines=new Map([[1,{id:1}],[2,{id:2}]]);
  let release;
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    asyncPipelines:true,stats:{commandBatches:0},get:id=>pipelines.get(id),
    device:{createRenderPipelineAsync:descriptor=>new Promise(resolve=>{release=()=>resolve(descriptor);})},
    uploadBufferRange(id,offset,bytes){events.push(['upload',id,...bytes]);},
    draw(indexed,words,start){
      const id=this.currentPipeline.id,entry=this.pipelineEntry('p'+id,()=>({id}));
      if(!entry.pipeline)throw new PipelinePending(entry.promise);
      events.push(['draw',id,indexed,words[start+4]|0]);
    },endFramebuffer(){events.push(['end']);}
  });
  const words=[12,9,0,0,4,0,1,9,0,3,0,1,0xffffffff,0,2,9,0,3,0,1,7];
  const packet=new Uint8Array(4+words.length*4);packet.set([5,6,7,8]);new Uint32Array(packet.buffer,4).set(words);
  const pending=engine.callAsync('commands',[['binaryCommands',[4,words.length]],['endFramebuffer',[]]],packet);
  assert.deepEqual(events,[['upload',9,5,6,7,8]]);release();await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(events,[['upload',9,5,6,7,8],['draw',1,true,-1]]);release();await pending;
  assert.deepEqual(events,[['upload',9,5,6,7,8],['draw',1,true,-1],['draw',2,true,7],['end']]);
  assert.equal(engine.stats.commandBatches,1);
});
test('failed asynchronous compilation stops before the draw or later commands',async()=>{
  const events=[];
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    asyncPipelines:true,stats:{commandBatches:0},device:{createRenderPipelineAsync:()=>Promise.reject(new Error('shader error'))},
    draw(){const entry=this.pipelineEntry('bad',()=>({}));if(!entry.pipeline)throw new PipelinePending(entry.promise);events.push('installed');},
    endFramebuffer(){events.push('end');}
  });
  await assert.rejects(engine.callAsync('commands',[['draw',[]],['endFramebuffer',[]]],new Uint8Array()),/shader error/);
  assert.deepEqual(events,[]);
});
