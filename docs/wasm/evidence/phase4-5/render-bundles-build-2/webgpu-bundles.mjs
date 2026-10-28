// Experimental command reuse. A signature contains every encoded binding and
// draw argument; live uniform/vertex/texture contents stay in their GPU buffers.
// https://gpuweb.github.io/types/interfaces/GPURenderPassEncoder.html#executebundles
// executeBundles clears native bindings. Each segment therefore seeds ALL of
// its logical bindings, even when the engine's existing state cache skips them.
const sizes=[0,2,0,5,5,5,6];

function replay(encoder,data,length,references,scratch,state){
  for(let i=0;i<length;){
    const op=data[i++];
    switch(op){
    case 1:{const pipeline=references.get(data[i++]);
      if(!state||state.pipeline!==pipeline){encoder.setPipeline(pipeline);if(state)state.pipeline=pipeline;}break;}
    case 2:{const slot=data[i++],group=references.get(data[i++])??null,count=data[i++];
      const previous=state?.groups.get(slot);
      let same=previous?.group===group&&previous.count===count;
      for(let j=0;same&&j<count;j++)same=previous.offsets[j]===data[i+j];
      if(!same){
        if(scratch.offsets.length<count)scratch.offsets=new Uint32Array(count);
        for(let j=0;j<count;j++)scratch.offsets[j]=data[i+j];
        // The typed-array overload copies the specified range during encoding;
        // it avoids allocating an iterable view for every binding operation.
        encoder.setBindGroup(slot,group,scratch.offsets,0,count);
        if(state){
          const saved=previous||{offsets:new Uint32Array(count)};
          if(saved.offsets.length<count)saved.offsets=new Uint32Array(count);
          saved.group=group;saved.count=count;
          for(let j=0;j<count;j++)saved.offsets[j]=data[i+j];state.groups.set(slot,saved);
        }
      }
      i+=count;break;}
    case 3:{const slot=data[i++],buffer=references.get(data[i++]),offset=data[i++],size=data[i++];
      const previous=state?.vertices.get(slot);
      if(!state||previous?.buffer!==buffer||previous.offset!==offset||previous.size!==size){
        encoder.setVertexBuffer(slot,buffer,offset,size<0?undefined:size);
        if(state)state.vertices.set(slot,{buffer,offset,size});
      }break;}
    case 4:{const buffer=references.get(data[i++]),format=data[i++]===16?'uint16':'uint32',offset=data[i++],size=data[i++];
      const previous=state?.index;
      if(!state||previous?.buffer!==buffer||previous.format!==format||previous.offset!==offset||previous.size!==size){
        encoder.setIndexBuffer(buffer,format,offset,size<0?undefined:size);
        if(state)state.index={buffer,format,offset,size};
      }break;}
    case 5:encoder.draw(data[i],data[i+1],data[i+2],data[i+3]);i+=4;break;
    case 6:encoder.drawIndexed(data[i],data[i+1],data[i+2],data[i+3],data[i+4]);i+=5;break;
    default:throw new Error('Invalid recorded render opcode');
    }
  }
}

export class RenderBundleCache {
  constructor(device,{stats={},maxBytes=16*1024*1024,maxEntries=512,maxSegmentNumbers=131072,minDraws=8}={}){
    if(maxBytes<0||maxEntries<1||maxSegmentNumbers<4096||minDraws<1)throw new Error('Invalid bundle cache limits');
    this.device=device;this.stats=stats;this.maxBytes=maxBytes;this.maxEntries=maxEntries;
    this.maxSegmentNumbers=maxSegmentNumbers;this.minDraws=minDraws;
    this.ids=new WeakMap();this.nextId=1;this.buckets=new Map();this.lru=new Map();this.pool=[];
    this.replayScratch={offsets:new Uint32Array(16)};
    Object.assign(stats,{bundleCacheHits:0,bundleCacheCreates:0,bundleCacheDirectDraws:0,
      bundleCacheReusedDraws:0,bundleCacheCompiledDraws:0,bundleCacheEntries:0,bundleCacheBytes:0,
      bundleCacheEvictions:0,bundleCacheIneligibleDraws:0,bundleCacheShortDraws:0,bundleCacheProbationDraws:0});
  }
  id(object){
    if(object==null)return 0;
    let id=this.ids.get(object);if(!id){id=this.nextId++;this.ids.set(object,id);}return id;
  }
  begin(pass,descriptor,width,height){return new BundlePass(this,pass,descriptor,width,height);}
  take(){return this.pool.pop()||new Float64Array(Math.min(8192,this.maxSegmentNumbers));}
  release(data){if(this.pool.length<2)this.pool.push(data);}
  evict(){
    const entry=this.lru.keys().next().value;
    this.lru.delete(entry);
    const bucket=this.buckets.get(entry.key);bucket.splice(bucket.indexOf(entry),1);
    if(!bucket.length)this.buckets.delete(entry.key);
    this.stats.bundleCacheBytes-=entry.signature.byteLength;this.stats.bundleCacheEntries--;
    this.stats.bundleCacheEvictions++;
  }
  submit(pass,descriptor,context,data,length,references,draws,eligible,state){
    let entry;
    if(eligible&&draws>=this.minDraws&&length*8<=this.maxBytes){
      const words=new Uint32Array(data.buffer,data.byteOffset,length*2);
      let hash=2166136261;
      for(let i=0;i<words.length;i++)hash=Math.imul(hash^words[i],16777619);
      const key=context+':'+(hash>>>0),bucket=this.buckets.get(key);
      if(bucket)for(const candidate of bucket){
        if(candidate.signature.length!==words.length)continue;
        let equal=true;
        for(let i=0;i<words.length;i++)if(candidate.signature[i]!==words[i]){equal=false;break;}
        if(equal){entry=candidate;break;}
      }
      if(!entry){
        while(this.lru.size&&(this.lru.size>=this.maxEntries||this.stats.bundleCacheBytes+words.byteLength>this.maxBytes))this.evict();
        // Probation: first occurrence executes normally. Only a repeated exact
        // sequence creates a GPU bundle; changing frames do not allocate them.
        entry={key,signature:words.slice(),bundle:null};
        const list=this.buckets.get(key)||[];list.push(entry);this.buckets.set(key,list);
        this.stats.bundleCacheBytes+=words.byteLength;this.stats.bundleCacheEntries++;
        this.lru.set(entry,true);
        replay(pass,data,length,references,this.replayScratch,state);
        this.stats.bundleCacheDirectDraws+=draws;this.stats.bundleCacheProbationDraws+=draws;return;
      }
      this.lru.delete(entry);this.lru.set(entry,true);
      if(!entry.bundle){
        const encoder=this.device.createRenderBundleEncoder(descriptor);
        replay(encoder,data,length,references,this.replayScratch);entry.bundle=encoder.finish();
        this.stats.bundleCacheCreates++;this.stats.bundleCacheCompiledDraws+=draws;
      }else{this.stats.bundleCacheHits++;this.stats.bundleCacheReusedDraws+=draws;}
      pass.executeBundles([entry.bundle]);
      state.pipeline=null;state.vertices.clear();state.index=null;
      for(const value of state.groups.values()){value.group=undefined;value.count=-1;}
      return;
    }
    replay(pass,data,length,references,this.replayScratch,state);this.stats.bundleCacheDirectDraws+=draws;
    if(!eligible)this.stats.bundleCacheIneligibleDraws+=draws;
    else if(draws<this.minDraws)this.stats.bundleCacheShortDraws+=draws;
  }
  clear(){
    this.buckets.clear();this.lru.clear();this.pool.length=0;
    this.stats.bundleCacheEntries=0;this.stats.bundleCacheBytes=0;
  }
}

class BundlePass {
  constructor(cache,pass,descriptor,width,height){
    this.cache=cache;this.pass=pass;this.descriptor=descriptor;this.width=width;this.height=height;
    this.context=JSON.stringify([descriptor.colorFormats,descriptor.depthStencilFormat??null,
      descriptor.sampleCount??1,descriptor.depthReadOnly??false,descriptor.stencilReadOnly??false,width,height]);
    this.pipeline=null;this.groups=new Map();this.vertices=new Map();this.index=null;
    this.fullViewport=true;this.fullScissor=true;this.zeroBlend=true;this.zeroStencil=true;
    this.data=cache.take();this.used=0;this.draws=0;this.active=false;this.references=new Map();
    this.nativeState={pipeline:null,groups:new Map(),vertices:new Map(),index:null};
  }
  reference(object){const id=this.cache.id(object);if(id)this.references.set(id,object);return id;}
  reserve(count){
    if(this.used+count>this.cache.maxSegmentNumbers){this.flush();return false;}
    if(this.used+count>this.data.length){
      const next=new Float64Array(Math.min(this.cache.maxSegmentNumbers,Math.max(this.used+count,this.data.length*2)));
      next.set(this.data.subarray(0,this.used));this.data=next;
    }
    return true;
  }
  record(op,a,b,c,d,e){
    const count=sizes[op];if(!this.reserve(count))return;
    const data=this.data;let i=this.used;data[i++]=op;data[i++]=a;
    if(count>2){data[i++]=b;data[i++]=c;data[i++]=d;}
    if(count>5)data[i++]=e;
    this.used=i;
  }
  recordGroup(slot,value){
    if(!this.reserve(4+value.offsets.length))return;
    let i=this.used;this.data[i++]=2;this.data[i++]=slot;this.data[i++]=this.reference(value.group);
    this.data[i++]=value.offsets.length;for(const offset of value.offsets)this.data[i++]=offset;this.used=i;
  }
  seed(){
    if(this.active)return;
    this.active=true;this.used=0;this.draws=0;this.references.clear();
    if(this.pipeline)this.record(1,this.reference(this.pipeline));
    for(const [slot,value] of this.groups)this.recordGroup(slot,value);
    for(const [slot,value] of this.vertices)this.record(3,slot,this.reference(value.buffer),value.offset,value.size??-1);
    if(this.index)this.record(4,this.reference(this.index.buffer),this.index.format==='uint16'?16:32,this.index.offset,this.index.size??-1);
    if(!this.active)throw new Error('Logical render state exceeds bundle segment limit');
  }
  setPipeline(pipeline){this.pipeline=pipeline;if(this.active)this.record(1,this.reference(pipeline));}
  setBindGroup(slot,group,offsets=[]){
    const values=Array.isArray(offsets)||ArrayBuffer.isView(offsets)?offsets:Array.from(offsets);
    for(const value of values)if(!Number.isInteger(value)||value<0||value>0xffffffff)
      throw new RangeError('Dynamic binding offset is outside uint32');
    let value=this.groups.get(slot);if(!value){value={group:null,offsets:[]};this.groups.set(slot,value);}
    value.group=group;value.offsets.length=values.length;
    for(let i=0;i<values.length;i++)value.offsets[i]=values[i];
    if(this.active)this.recordGroup(slot,value);
  }
  setVertexBuffer(slot,buffer,offset=0,size){
    this.vertices.set(slot,{buffer,offset,size});if(this.active)this.record(3,slot,this.reference(buffer),offset,size??-1);
  }
  setIndexBuffer(buffer,format,offset=0,size){
    if(format!=='uint16'&&format!=='uint32')throw new Error('Invalid index format');
    this.index={buffer,format,offset,size};if(this.active)this.record(4,this.reference(buffer),format==='uint16'?16:32,offset,size??-1);
  }
  prepareDraw(count){
    this.seed();
    if(!this.reserve(count)){this.seed();if(!this.reserve(count))throw new Error('Bundle draw exceeds segment limit');}
  }
  draw(count,instances=1,first=0,instance=0){this.prepareDraw(5);this.record(5,count,instances,first,instance);this.draws++;}
  drawIndexed(count,instances=1,first=0,base=0,instance=0){this.prepareDraw(6);this.record(6,count,instances,first,base,instance);this.draws++;}
  flush(){
    if(!this.active)return;
    if(this.draws)this.cache.submit(this.pass,this.descriptor,this.context,this.data,this.used,this.references,
      this.draws,this.fullViewport&&this.fullScissor&&this.zeroBlend&&this.zeroStencil,this.nativeState);
    this.active=false;this.used=0;this.draws=0;this.references.clear();
  }
  // Conservative scope: bundles only use default dynamic state. Other draws
  // replay directly. All state/debug transitions remain ordered barriers.
  setViewport(x,y,width,height,minDepth,maxDepth){
    this.flush();this.fullViewport=x===0&&y===0&&width===this.width&&height===this.height&&minDepth===0&&maxDepth===1;
    this.pass.setViewport(x,y,width,height,minDepth,maxDepth);
  }
  setScissorRect(x,y,width,height){
    this.flush();this.fullScissor=x===0&&y===0&&width===this.width&&height===this.height;
    this.pass.setScissorRect(x,y,width,height);
  }
  setBlendConstant(color){
    this.flush();const values=Array.isArray(color)||ArrayBuffer.isView(color)?color:[color.r,color.g,color.b,color.a];
    this.zeroBlend=Array.from(values).every(v=>v===0);this.pass.setBlendConstant(color);
  }
  setStencilReference(reference){this.flush();this.zeroStencil=reference===0;this.pass.setStencilReference(reference);}
  pushDebugGroup(label){this.flush();this.pass.pushDebugGroup(label);}
  popDebugGroup(){this.flush();this.pass.popDebugGroup();}
  insertDebugMarker(label){this.flush();this.pass.insertDebugMarker(label);}
  end(){this.flush();this.pass.end();this.cache.release(this.data);this.data=null;this.references.clear();}
}
