import assert from 'node:assert/strict';
import {RenderBundleCache} from '../experiments/render-bundles/webgpu-bundles.mjs';

let serial=1,checks=0;
const object=extra=>({id:serial++,...extra});
const descriptor={colorFormats:['rgba8unorm'],sampleCount:1};
class Encoder {
  constructor(descriptor){this.descriptor=descriptor;this.commands=[];}
  setPipeline(...args){this.commands.push(['setPipeline',args]);}
  setVertexBuffer(...args){this.commands.push(['setVertexBuffer',args]);}
  setIndexBuffer(...args){this.commands.push(['setIndexBuffer',args]);}
  setBindGroup(slot,group,offsets=[]){this.commands.push(['setBindGroup',[slot,group,Array.from(offsets)]]);}
  draw(...args){this.commands.push(['draw',args]);}
  drawIndexed(...args){this.commands.push(['drawIndexed',args]);}
  finish(){return {descriptor:this.descriptor,commands:this.commands};}
}
const device={createRenderBundleEncoder:d=>new Encoder(d)};
class Pass {
  constructor(d=descriptor){
    this.descriptor=d;this.groups=new Map();this.vertices=new Map();this.draws=[];
    this.viewport=[0,0,4,4,0,1];this.scissor=[0,0,4,4];this.blend=[0,0,0,0];this.stencil=0;this.labels=[];
  }
  setPipeline(p){this.pipeline=p;}
  setBindGroup(slot,group,offsets=[]){this.groups.set(slot,{group,offsets:Array.from(offsets)});}
  setVertexBuffer(slot,buffer,offset=0,size){this.vertices.set(slot,{buffer,offset,size});}
  setIndexBuffer(buffer,format,offset=0,size){this.index={buffer,format,offset,size};}
  draw(...args){this.snapshot(false,args);}
  drawIndexed(...args){this.snapshot(true,args);}
  snapshot(indexed,args){
    assert(this.pipeline,'A bundle must restore its pipeline after executeBundles');
    const groups=this.pipeline.groups.map(slot=>{
      const v=this.groups.get(slot);assert(v,'Missing restored bind group');
      return [slot,v.group?.id??null,v.offsets.slice(),v.group?.buffer?.value];
    });
    const vertices=this.pipeline.vertices.map(slot=>{
      const v=this.vertices.get(slot);assert(v,'Missing restored vertex buffer');return [slot,v.buffer.id,v.offset,v.size];
    });
    if(indexed)assert(this.index,'Missing restored index buffer');
    this.draws.push({pipeline:this.pipeline.id,groups,vertices,args,indexed,
      index:indexed?[this.index.buffer.id,this.index.format,this.index.offset,this.index.size]:null,
      viewport:this.viewport.slice(),scissor:this.scissor.slice(),blend:this.blend.slice(),stencil:this.stencil,labels:this.labels.slice()});
  }
  executeBundles(bundles){
    for(const bundle of bundles){
      assert.deepEqual(bundle.descriptor,this.descriptor,'Attachment compatibility must be part of the key');
      // Bundles start without inherited bindings and clear the pass bindings.
      this.pipeline=null;this.groups.clear();this.vertices.clear();this.index=null;
      for(const [name,args] of bundle.commands)this[name](...args);
    }
    this.pipeline=null;this.groups.clear();this.vertices.clear();this.index=null;
  }
  setViewport(...args){this.viewport=args;}
  setScissorRect(...args){this.scissor=args;}
  setBlendConstant(color){this.blend=Array.from(color);}
  setStencilReference(value){this.stencil=value;}
  pushDebugGroup(label){this.labels.push(label);}
  popDebugGroup(){this.labels.pop();}
  insertDebugMarker(){}
  end(){assert.equal(this.labels.length,0);}
}

const uniform=object({value:0}),group=object({buffer:uniform}),vertex=object(),index=object();
const pipeline=object({groups:[0],vertices:[0]}),alternate=object({groups:[0],vertices:[0]});
const bind=(pass,offset=0,p=pipeline,g=group,v=vertex,ix=index)=>{
  pass.setPipeline(p);pass.setBindGroup(0,g,[offset]);pass.setVertexBuffer(0,v,12,96);pass.setIndexBuffer(ix,'uint16',4,24);
};
const draw=(pass,n=8,base=-1)=>{for(let i=0;i<n;i++)pass.drawIndexed(3,2,1,base,5);};
function compare(name,body,{frames=4,options={},descriptors=null}={}){
  const cache=new RenderBundleCache(device,options);
  for(let frame=0;frame<frames;frame++){
    uniform.value=frame+10;
    const d=descriptors?.[frame]||descriptor,expected=new Pass(d),actual=new Pass(d);
    body(expected,frame);expected.end();
    const wrapped=cache.begin(actual,d,4,4);body(wrapped,frame);wrapped.end();
    assert.deepEqual(actual.draws,expected.draws,name+' frame '+frame);
    assert(cache.stats.bundleCacheBytes<=cache.maxBytes);
    assert(cache.stats.bundleCacheEntries<=cache.maxEntries);
  }
  checks++;return cache;
}

let cache=compare('live uniform values and negative baseVertex',p=>{bind(p);draw(p);});
assert(cache.stats.bundleCacheHits>0);assert.equal(cache.stats.bundleCacheCreates,1);
compare('dynamic offsets', (p,f)=>{bind(p,f%2?256:0);draw(p);},{frames:8});
compare('pipeline identities',(p,f)=>{bind(p,0,f%2?pipeline:alternate);draw(p);},{frames:8});
const otherGroup=object({buffer:object({value:73})}),otherVertex=object(),otherIndex=object();
compare('resource identities',(p,f)=>{bind(p,0,pipeline,f%2?group:otherGroup,f%2?vertex:otherVertex,f%2?index:otherIndex);draw(p);},{frames:8});
compare('vertex/index range and draw arguments',(p,f)=>{
  bind(p);p.setVertexBuffer(0,vertex,f%2?24:12,48);p.setIndexBuffer(index,'uint32',f%2?8:4,12);draw(p,8,f%2?-2:0);
},{frames:8});
cache=compare('bundle/direct/bundle restores unchanged logical bindings',p=>{
  bind(p);draw(p);p.setScissorRect(0,0,2,4);draw(p,2);p.setScissorRect(0,0,4,4);draw(p);
});
assert(cache.stats.bundleCacheHits>0&&cache.stats.bundleCacheDirectDraws>0);
compare('blend and stencil fallback',p=>{
  bind(p);draw(p);p.setBlendConstant([.1,.2,.3,.4]);p.setStencilReference(7);draw(p);
  p.setBlendConstant([0,0,0,0]);p.setStencilReference(0);draw(p);
});
compare('viewport and debug barriers',p=>{
  bind(p);p.pushDebugGroup('original');draw(p);p.setViewport(1,0,2,4,0,1);draw(p);
  p.setViewport(0,0,4,4,0,1);p.insertDebugMarker('original marker');draw(p);p.popDebugGroup();
});
compare('offset array ownership',p=>{
  bind(p);const offsets=[0];p.setBindGroup(0,group,offsets);offsets[0]=256;draw(p);
});
compare('bounded segments restore bindings',p=>{bind(p);draw(p,1600);},{options:{maxSegmentNumbers:4096}});
cache=compare('LRU eviction preserves outputs',(p,f)=>{bind(p,f*256);draw(p);},{frames:12,options:{maxBytes:1024,maxEntries:2}});
cache.clear();assert.equal(cache.stats.bundleCacheBytes,0);assert.equal(cache.stats.bundleCacheEntries,0);
compare('attachment compatibility',p=>{bind(p);draw(p);},{frames:8,
  descriptors:Array.from({length:8},(_,i)=>i%2?descriptor:{colorFormats:['bgra8unorm'],sampleCount:1})});
compare('mixed indexed and non-indexed draw arguments',p=>{
  bind(p);for(let i=0;i<8;i++){p.draw(12,3,2,4);p.drawIndexed(9,2,3,-7,5);}
});
compare('no draws does not invent work',p=>{bind(p);});
console.log(JSON.stringify({passed:true,checks,diagnosticOnly:true,performanceAcceptance:false,
  scope:'Semantic draw snapshots against direct encoding, including native binding reset, live buffer data, ownership, dynamic barriers, ranges, LRU and segment limits.'}));
