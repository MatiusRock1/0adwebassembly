import test from 'node:test';
import assert from 'node:assert/strict';
import {UploadBelt} from '../browser/webgpu-upload.mjs';
import {WebGPUEngine} from '../browser/webgpu-engine.mjs';

function fakeDevice() {
  globalThis.GPUBufferUsage={MAP_WRITE:1,COPY_SRC:2};globalThis.GPUMapMode={WRITE:2};
  const events=[],buffers=[];
  const device={events,buffers,createBuffer({size}){
    const buffer={data:new Uint8Array(size),mapped:true,destroyed:false,
      getMappedRange(){assert.ok(this.mapped);return this.data.buffer;},
      unmap(){this.mapped=false;events.push('unmap');},
      mapAsync(){return new Promise((resolve,reject)=>{this.remap=()=>{this.mapped=true;resolve();};this.reject=reject;});},
      destroy(){this.destroyed=true;}};
    buffers.push(buffer);return buffer;
  },createCommandEncoder(){const work=[];return {
    copyBufferToBuffer(src,from,dst,to,size){work.push(()=>{assert.equal(src.mapped,false);dst.data.set(src.data.subarray(from,from+size),to);events.push('copy');});},
    finish(){return ()=>work.forEach(fn=>fn());}
  };},queue:{writeBuffer(dst,offset,bytes){dst.data.set(bytes,offset);events.push('fallback');},
    submit(commands){for(const command of commands)command();events.push('submit');}}};
  return device;
}
function submit(belt,device,frame=()=>{}) {
  const uploads=belt.beforeFrame();device.queue.submit(uploads?[uploads,frame]:[frame]);
  return belt.afterSubmit();
}

test('mapped copies own exact byte snapshots and execute before the frame',async()=>{
  const device=fakeDevice(),belt=new UploadBelt(device,{chunkBytes:16,maxBytes:16});
  const a={data:new Uint8Array(8)},b={data:new Uint8Array(8)};
  const source=new Uint8Array(new SharedArrayBuffer(12),4,8);source.set([0,255,17,33,4,5,6,7]);
  belt.stage(a,source);belt.stage(b,new Uint8Array([8,9,10,11]));source.fill(99);
  const pending=submit(belt,device,()=>{
    assert.deepEqual([...a.data],[0,255,17,33,4,5,6,7]);assert.deepEqual([...b.data],[8,9,10,11,0,0,0,0]);
    device.events.push('frame');
  });
  assert.deepEqual(device.events,['unmap','copy','copy','frame','submit']);
  assert.equal(belt.reserved,16);device.buffers[0].remap();await Promise.all(pending);
  belt.dispose();assert.equal(device.buffers[0].destroyed,true);
});

test('pending maps respect the memory cap and fall back without reusing in-flight data',async()=>{
  const device=fakeDevice(),belt=new UploadBelt(device,{chunkBytes:8,maxBytes:8}),dst={data:new Uint8Array(8)};
  belt.stage(dst,new Uint8Array([1,2,3,4,5,6,7,8]));const pending=submit(belt,device);
  belt.stage(dst,new Uint8Array([9,10,11,12]));submit(belt,device);
  assert.deepEqual([...dst.data],[9,10,11,12,5,6,7,8]);
  assert.equal(belt.stats.createdBuffers,1);assert.equal(belt.stats.fallbackBytes,4);assert.equal(belt.reserved,8);
  device.buffers[0].remap();await Promise.all(pending);
  belt.stage(dst,new Uint8Array([13,14,15,16]));const next=submit(belt,device);
  assert.equal(belt.stats.reusedBuffers,1);assert.deepEqual([...dst.data].slice(0,4),[13,14,15,16]);
  device.buffers[0].remap();await Promise.all(next);belt.dispose();
});

test('failed mapping frees its budget and disposal ignores late completions',async()=>{
  const errors=[],device=fakeDevice(),belt=new UploadBelt(device,{chunkBytes:8,maxBytes:8,onError:e=>errors.push(e.message)}),dst={data:new Uint8Array(8)};
  belt.stage(dst,new Uint8Array(8));let pending=submit(belt,device);
  device.buffers[0].reject(new Error('lost'));await Promise.all(pending);
  assert.equal(belt.reserved,0);assert.equal(device.buffers[0].destroyed,true);assert.deepEqual(errors,['lost']);
  belt.stage(dst,new Uint8Array(8));pending=submit(belt,device);belt.dispose();belt.dispose();
  device.buffers[1].remap();await Promise.all(pending);assert.equal(belt.chunks.length,0);assert.equal(belt.reserved,0);
  assert.throws(()=>belt.stage(dst,new Uint8Array(4)),/disposed/);
});

test('alignment is enforced before recording a copy',()=>{
  const device=fakeDevice(),belt=new UploadBelt(device,{chunkBytes:8,maxBytes:8});
  assert.throws(()=>belt.stage({},new Uint8Array(3)),/Unaligned/);
  assert.equal(device.buffers.length,0);belt.dispose();
});

test('engine submission uploads uniform and transient arenas before original commands',async()=>{
  const device=fakeDevice(),belt=new UploadBelt(device,{chunkBytes:16,maxBytes:16});
  const uniform={data:new Uint8Array(4)},vertex={data:new Uint8Array(4)};
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{device,uploadBelt:belt,
    uniformBuffer:uniform,uniformHost:new Uint8Array([1,2,3,4]),uniformCursor:4,
    transientArenas:{vertex:[{buffer:vertex,bytes:new Uint8Array([5,6,7,8]),cursor:4}]},
    encoder:{finish:()=>()=>{assert.deepEqual([...uniform.data],[1,2,3,4]);assert.deepEqual([...vertex.data],[5,6,7,8]);}},
    retired:new Set(),objects:new Map(),stats:{submissions:0},report(){}});
  engine.submit();assert.equal(engine.stats.submissions,1);assert.equal(engine.uniformCursor,0);
  assert.equal(engine.transientArenas.vertex[0].cursor,0);device.buffers[0].remap();await Promise.resolve();belt.dispose();
});
