// Reusable mapped COPY_SRC buffers. A buffer is remapped only after its copies
// have been submitted; until mapAsync completes it cannot serve another frame.
// Saturating the bounded pool uses the original queue.writeBuffer path.
export class UploadBelt {
  constructor(device,{chunkBytes=16*1024*1024,maxBytes=64*1024*1024,onError=()=>{}}={}) {
    this.device=device;this.chunkBytes=chunkBytes;this.maxBytes=maxBytes;this.onError=onError;
    this.chunks=[];this.active=[];this.reserved=0;this.encoder=null;this.disposed=false;
    this.stats={mappedBytes:0,fallbackBytes:0,createdBuffers:0,reusedBuffers:0,mapFailures:0};
  }
  stage(destination,bytes) {
    if(this.disposed)throw new Error('Upload belt is disposed');
    if(!(bytes instanceof Uint8Array)||bytes.length%4)throw new Error('Unaligned upload belt bytes');
    if(!bytes.length)return;
    let chunk=this.active.at(-1);
    if(!chunk||chunk.size-chunk.cursor<bytes.length) {
      chunk=this.chunks.find(c=>c.state==='mapped'&&c.size>=bytes.length);
      if(chunk)this.stats.reusedBuffers++;
      else {
        const size=Math.max(this.chunkBytes,Math.ceil(bytes.length/4)*4);
        if(this.reserved+size<=this.maxBytes) {
          const buffer=this.device.createBuffer({label:'0ad mapped upload belt',size,
            usage:GPUBufferUsage.MAP_WRITE|GPUBufferUsage.COPY_SRC,mappedAtCreation:true});
          chunk={buffer,size,bytes:new Uint8Array(buffer.getMappedRange()),state:'mapped',cursor:0};
          this.chunks.push(chunk);this.reserved+=size;this.stats.createdBuffers++;
        }
      }
      if(chunk){chunk.state='recording';chunk.cursor=0;this.active.push(chunk);}
    }
    if(!chunk) {
      this.device.queue.writeBuffer(destination,0,bytes);this.stats.fallbackBytes+=bytes.length;return;
    }
    chunk.bytes.set(bytes,chunk.cursor);
    this.encoder??=this.device.createCommandEncoder({label:'0ad uploads before frame'});
    this.encoder.copyBufferToBuffer(chunk.buffer,chunk.cursor,destination,0,bytes.length);
    chunk.cursor+=bytes.length;this.stats.mappedBytes+=bytes.length;
  }
  beforeFrame() {
    if(!this.encoder)return null;
    for(const chunk of this.active){chunk.buffer.unmap();chunk.bytes=null;chunk.state='submitted';}
    const commands=this.encoder.finish();this.encoder=null;return commands;
  }
  afterSubmit() {
    const active=this.active;this.active=[];
    const pending=[];
    for(const chunk of active) {
      chunk.state='mapping';
      pending.push(chunk.buffer.mapAsync(GPUMapMode.WRITE).then(()=>{
        if(this.disposed)return;
        chunk.bytes=new Uint8Array(chunk.buffer.getMappedRange());chunk.cursor=0;chunk.state='mapped';
      }).catch(error=>{
        if(this.disposed)return;
        chunk.state='failed';chunk.buffer.destroy();
        this.reserved-=chunk.size;this.chunks.splice(this.chunks.indexOf(chunk),1);
        this.stats.mapFailures++;this.onError(error);
      }));
    }
    return pending;
  }
  dispose() {
    if(this.disposed)return;this.disposed=true;
    for(const chunk of this.chunks)chunk.buffer.destroy();
    this.chunks=[];this.active=[];this.encoder=null;this.reserved=0;
  }
}
