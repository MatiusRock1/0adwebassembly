import test from 'node:test';
import assert from 'node:assert/strict';
import { WebGPUEngine } from '../browser/webgpu-engine.mjs';

function textureFixture(format,decompress=false) {
  globalThis.GPUBufferUsage={COPY_SRC:8};
  const events=[],allocated=[],texture={name:'original texture'};
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    objects:new Map([[41,{texture,format,decompress}]]),nextId:100,
    stats:{commandBatches:0,uploadBytes:0},retired:new Set(),
    device:{createBuffer({size}){const bytes=new Uint8Array(size),buffer={bytes,getMappedRange:()=>bytes.buffer,unmap(){}};allocated.push(buffer);return buffer;}},
    endFramebuffer(){},encoderForWork(){return {copyBufferToTexture(source,target,extent){
      events.push({kind:'upload',bytes:[...source.buffer.bytes],pitch:source.bytesPerRow,rows:source.rowsPerImage,mip:target.mipLevel,origin:target.origin,extent});
    }};},draw(){events.push({kind:'draw'});}
  });
  return {engine,events,allocated};
}

test('binary texture uploads preserve old staging bytes, formats, subresources and draw order',()=>{
  for(const [index,format,width,height,size,decompress] of [
    [1,'r8unorm',3,2,6,false],[5,'rgba8unorm',3,2,24,false],
    [4,'rgba8unorm',3,2,18,false],[10,'rgba8unorm',3,2,6,false],[11,'rgba8unorm',3,2,6,false],
    [32,'bc1-rgba-unorm',4,4,8,false],[32,'rgba8unorm',1,1,8,true]]){
    const old=textureFixture(format,decompress),next=textureFixture(format,decompress);
    const first=Uint8Array.from({length:size},(_,i)=>i*17+3),second=first.map(x=>x+31);
    const args=[41,index,0,0,width,height,1,2];
    const a=old.engine.call('stageTexture',args,first),b=old.engine.call('stageTexture',args,second);
    old.engine.call('commands',[['uploadTexture',[a]],['draw',[0,3,0,1]],['uploadTexture',[b]],['draw',[0,3,0,1]]],new Uint8Array());
    const secondOffset=Math.ceil(size/4)*4,codeOffset=Math.ceil((secondOffset+size)/4)*4;
    const words=[13,...args,0,size,8,0,3,0,1,13,...args,secondOffset,size,8,0,3,0,1];
    const packet=new Uint8Array(codeOffset+words.length*4);packet.set(first);packet.set(second,secondOffset);
    new Uint32Array(packet.buffer,codeOffset,words.length).set(words);
    first.fill(0);second.fill(0);
    next.engine.call('commands',[['binaryCommands',[codeOffset,words.length]]],packet);packet.fill(255);
    assert.deepEqual(next.events,old.events);
    assert.deepEqual(next.events.map(x=>x.kind),['upload','draw','upload','draw']);
    assert.equal(next.allocated.length,2);assert.equal(next.engine.retired.size,2);
    assert.equal(next.engine.stats.uploadBytes,old.engine.stats.uploadBytes);
  }
});

test('invalid binary texture payloads fail before allocating or recording GPU work',()=>{
  const {engine,allocated,events}=textureFixture('r8unorm');
  const packet=new Uint8Array(64),words=[13,41,1,0,0,3,2,0,0,63,6];
  new Uint32Array(packet.buffer,0,words.length).set(words);
  assert.throws(()=>engine.call('commands',[['binaryCommands',[0,words.length]]],packet),/Invalid binary/);
  assert.deepEqual(allocated,[]);assert.deepEqual(events,[]);
});

test('binary uniforms preserve float32 values, draw order and std140 matrix stride',()=>{
  const source=new Uint8Array(new SharedArrayBuffer(80),8,64);
  const values=new Float32Array(source.buffer,source.byteOffset,16);
  values.set([1e-12,-0,Math.fround(1/3),1e20,5,6,7,8]);
  const block=new Uint8Array(48),draws=[];
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    stats:{commandBatches:0},bindings:new Map([[9,{type:'uniform',shader:{uniformBlocks:new Map([[0,block]])},block:{binding:0},member:{offset:0,matrixStride:16,rows:2,columns:2}}]]),
    draw(){draws.push([...new Float32Array(block.buffer)]);}
  });
  engine.call('commands',[
    ['uniformDataRange',[9,0,4]],['draw',[0,1,0,1]],
    ['uniformDataRange',[9,16,4]],['draw',[0,1,0,1]]
  ],source);
  assert.deepEqual(draws[0],[values[0],-0,0,0,values[2],values[3],0,0,0,0,0,0]);
  assert.deepEqual(draws[1],[5,6,0,0,7,8,0,0,0,0,0,0]);
  source.fill(0);
  assert.deepEqual([...new Float32Array(block.buffer)],draws[1],'uniform block owns consumed values after the batch returns');
});

test('binary vertex and index ranges retain exact bytes and original slot/offset',()=>{
  const bytes=new Uint8Array([99,99,1,2,3,4,5,6,99]);
  const uploads=[];
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    vertices:new Map(),stats:{commandBatches:0},
    uploadTransient(kind,data){uploads.push({kind,bytes:[...data]});return {buffer:{buffer:kind},offset:12};}
  });
  engine.call('commands',[['vertexDataRange',[3,2,3]],['indexDataRange',[5,3]]],bytes);
  assert.deepEqual(uploads,[{kind:'vertex',bytes:[1,2,3]},{kind:'index',bytes:[4,5,6]}]);
  assert.equal(engine.vertices.get(3).offset,12);
  assert.deepEqual(engine.indexBuffer,{buffer:'index',offset:12});
});

test('invalid binary ranges fail before any out-of-bounds upload',()=>{
  const engine=Object.create(WebGPUEngine.prototype),bytes=new Uint8Array(16);
  for(const [offset,size] of [[-1,1],[0,-1],[17,0],[15,2],[0,NaN],[.5,1],[0,Infinity]])
    assert.throws(()=>engine.commandDataRange(bytes,offset,size),/Invalid binary/);
  assert.throws(()=>engine.command('uniformDataRange',[0,1,1],bytes),/Unaligned/);
  assert.equal(engine.commandDataRange(bytes,16,0).length,0);
});

test('arena uploads precede submission, retain each draw and safely reuse the next frame',()=>{
  globalThis.GPUBufferUsage={COPY_DST:1,VERTEX:2,INDEX:4};
  const events=[],offsets=[];
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    uniformCapacity:1024,uniformCursor:0,uniformHost:new Uint8Array(1024),uniformBuffer:'uniform',
    device:{limits:{minUniformBufferOffsetAlignment:256},createBuffer:()=> 'vertex',
      queue:{writeBuffer(buffer,offset,bytes){events.push({buffer,offset,bytes:[...bytes]});},submit(){events.push('submit');}}},
    transientArenas:{vertex:[],index:[]},encoder:{finish:()=> 'commands'},
    retired:new Set(),objects:new Map(),stats:{submissions:0,uploadBytes:0},report(){}
  });
  const bytes=new Uint8Array([1,2,3,4]),shader={group0:{},variant:{uniforms:[{binding:0}],textures:[]},uniformBlocks:new Map([[0,bytes]])};
  const pass={setBindGroup(group,binding,values){offsets.push([...values]);}};
  engine.bindShader(pass,shader);bytes.set([5,6,7,8]);engine.bindShader(pass,shader);
  const vertices=new Uint8Array([9,10,11]);engine.uploadTransient('vertex',vertices);vertices.fill(0);
  assert.deepEqual(events,[],'no per-draw queue writes');
  engine.submit();
  assert.deepEqual(offsets,[[0],[256]]);
  assert.deepEqual(events[0].bytes.slice(0,4),[1,2,3,4]);
  assert.deepEqual(events[0].bytes.slice(256),[5,6,7,8]);
  assert.deepEqual(events[1],{buffer:'vertex',offset:0,bytes:[9,10,11,0]});
  assert.equal(events[2],'submit');
  assert.equal(engine.uniformCursor,0);
  engine.encoder={finish:()=> 'next'};bytes.set([12,13,14,15]);engine.bindShader(pass,shader);engine.submit();
  assert.deepEqual(events[3],{buffer:'uniform',offset:0,bytes:[12,13,14,15]});
  assert.equal(events[4],'submit');
});

test('binary command stream preserves interleaved state, uniforms and signed base vertex',()=>{
  const data=new Uint8Array(256),floats=new Float32Array(data.buffer,0,8);
  floats.set([1,2,3,4,5,6,7,8]);
  const words=[0,41,4,9,0,4,9,0,3,0,1,0xffffffff];
  new Uint32Array(data.buffer,64,words.length).set(words);
  const block=new Uint8Array(16),draws=[];
  const pipeline={name:'original'};
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    stats:{commandBatches:0},get(id){assert.equal(id,41);return pipeline;},
    bindings:new Map([[9,{type:'uniform',shader:{uniformBlocks:new Map([[0,block]])},block:{binding:0},member:{offset:0}}]]),
    draw(indexed,values,offset=0){const args=Array.from(values).slice(offset,offset+5);if(indexed)args[4]|=0;draws.push({indexed,values:args,uniform:[...new Float32Array(block.buffer)],pipeline:this.currentPipeline});}
  });
  engine.call('commands',[
    ['binaryCommands',[64,words.length]],
    ['uniformDataRange',[9,16,4]],['drawIndexed',[3,6,0,1,2]]
  ],data);
  assert.deepEqual(draws,[
    {indexed:true,values:[0,3,0,1,-1],uniform:[1,2,3,4],pipeline},
    {indexed:true,values:[3,6,0,1,2],uniform:[5,6,7,8],pipeline}
  ]);
  new Uint32Array(data.buffer,64,1)[0]=99;
  assert.throws(()=>engine.command('binaryCommands',[64,1],data),/opcode or length/);
  new Uint32Array(data.buffer,64,1)[0]=9;
  assert.throws(()=>engine.command('binaryCommands',[64,2],data),/opcode or length/);
});

test('packed matrices and padded arrays retain original std140 offsets',()=>{
  const block=new Uint8Array(192),shader={uniformBlocks:new Map([[0,block]])};
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{bindings:new Map([
    [1,{type:'uniform',shader,block:{binding:0},member:{offset:16,columns:4,rows:4,matrixStride:16}}],
    [2,{type:'uniform',shader,block:{binding:0},member:{offset:80,columns:1,rows:3,arrayStride:16}}],
    [3,{type:'uniform',shader,block:{binding:0},member:{offset:112,columns:2,rows:2,matrixStride:16,arrayStride:32}}]
  ])});
  const values=Float32Array.from({length:20},(_,i)=>i+1);
  engine.setUniform(1,values,2,16);
  engine.setUniform(2,values,0,6);
  engine.setUniform(3,values,6,8);
  const result=[...new Float32Array(block.buffer)];
  assert.deepEqual(result.slice(4,20),[...values.slice(2,18)]);
  assert.deepEqual(result.slice(20,28),[1,2,3,0,4,5,6,0]);
  assert.deepEqual(result.slice(28,44),[7,8,0,0,9,10,0,0,11,12,0,0,13,14,0,0]);
});

test('unchanged blocks reuse immutable snapshots only within the current submission',()=>{
  const bytes=new Uint8Array(16),shader={group0:{},variant:{uniforms:[{binding:0}],textures:[]},uniformBlocks:new Map([[0,bytes]]),uniformSnapshots:new Map()};
  const bound=[];
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    uniformCursor:0,uniformHost:new Uint8Array(1024),uniformCapacity:1024,
    device:{limits:{minUniformBufferOffsetAlignment:256}},
    bindings:new Map([[1,{type:'uniform',shader,block:{binding:0},member:{offset:0}}]])
  });
  const pass={setBindGroup:(_index,_group,offsets)=>bound.push([...offsets])};
  engine.setUniform(1,[1,2,3,4]);engine.bindShader(pass,shader);engine.bindShader(pass,shader);
  assert.equal(engine.uniformCursor,16);assert.deepEqual(bound,[[0]]);
  engine.setUniform(1,[5,6,7,8]);engine.bindShader(pass,shader);
  assert.deepEqual(bound,[[0],[256]]);
  assert.deepEqual([...new Float32Array(engine.uniformHost.buffer,0,4)],[1,2,3,4]);
  assert.deepEqual([...new Float32Array(engine.uniformHost.buffer,256,4)],[5,6,7,8]);
  engine.uniformCursor=0;engine.uniformEpoch=1;engine.bindShader(pass,shader);
  assert.equal(engine.uniformCursor,16);assert.deepEqual(bound.at(-1),[0]);
  assert.deepEqual([...new Float32Array(engine.uniformHost.buffer,0,4)],[5,6,7,8]);
});

test('batched buffer uploads keep draw-time ordering and exact snapshots in a reusable staging arena',()=>{
  globalThis.GPUBufferUsage={COPY_DST:1,COPY_SRC:2,VERTEX:4,INDEX:8};
  const events=[],created=[];
  const target={size:10,buffer:'target'},framebuffer={};
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    pass:{},target:framebuffer,objects:new Map([[5,target]]),transientArenas:{vertex:[],index:[]},retired:new Set(),
    stats:{uploadBytes:0,submissions:0},uniformCursor:0,
    device:{createBuffer(descriptor){created.push(descriptor);return 'staging';},queue:{writeBuffer(buffer,offset,bytes){events.push(['write',buffer,offset,[...bytes]]);},submit(){events.push(['submit']);}}},
    encoder:{copyBufferToBuffer:(...args)=>events.push(['copy',...args]),finish:()=> 'commands'},
    endFramebuffer(){events.push(['end']);this.pass=null;},
    beginFramebuffer(target,load){events.push(['resume',target,load]);this.pass={};},report(){}
  });
  const data=new Uint8Array(128);data.set([1,2,3,4,5,6,0,0]);
  const words=[12,5,0,0,4,12,5,8,4,4];new Uint32Array(data.buffer,32,words.length).set(words);
  engine.binaryCommands(data,32,words.length);data.fill(0);
  assert.equal(created.length,1);assert.equal(created[0].usage,3);
  assert.deepEqual(events.filter(e=>e[0]==='copy'),[['copy','staging',0,'target',0,4],['copy','staging',4,'target',8,4]]);
  assert.deepEqual(events.slice(0,3),[['end'],['copy','staging',0,'target',0,4],['resume',framebuffer,true]]);
  engine.pass=null;engine.submit();
  assert.deepEqual(events.at(-2),['write','staging',0,[1,2,3,4,5,6,0,0]]);assert.deepEqual(events.at(-1),['submit']);
  engine.encoder={copyBufferToBuffer:(...args)=>events.push(['copy',...args]),finish:()=> 'next'};
  engine.uploadBufferRange(5,0,new Uint8Array([9,10,11,12]));assert.equal(created.length,1);
  assert.equal(events.at(-1)[2],0,'arena reused only after prior submission');
  for(const [offset,bytes] of [[-4,4],[1,4],[0,3],[12,4]])assert.throws(()=>engine.uploadBufferRange(5,offset,new Uint8Array(bytes)),/Invalid aligned/);
});
