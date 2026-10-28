// Original ZIP bytes, fetched and persisted by content hash. The engine still
// parses/decompresses the original archives; only their storage backend changes.
export class ArchiveBlocks {
  constructor({manifest,baseURL,fetcher=fetch,storage=null,maxMemoryBytes=64*1024*1024,report=()=>{}}) {
    this.manifest=manifest;this.baseURL=baseURL;this.fetcher=fetcher;this.storage=storage;
    this.maxMemoryBytes=maxMemoryBytes;this.report=report;this.cache=new Map();this.pending=new Map();
    this.stats={residentBytes:0,peakResidentBytes:0,networkBytes:0,networkBlocks:0,persistentHits:0,memoryHits:0,reads:0,readBytes:0};
  }
  async verify(bytes,expected){
    const digest=await crypto.subtle.digest('SHA-256',bytes);
    const actual=Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');
    return actual===expected;
  }
  async block(archive,index) {
    const spec=this.manifest.archives[archive];
    if(!spec || !Number.isSafeInteger(index)||index<0||index>=spec.blocks.length)throw new Error('Invalid archive block');
    const key=spec.blocks[index];
    const resident=this.cache.get(key);
    if(resident){this.cache.delete(key);this.cache.set(key,resident);this.stats.memoryHits++;return resident;}
    if(this.pending.has(key))return this.pending.get(key);
    const work=this.loadBlock(archive,index,spec,key);
    this.pending.set(key,work);
    try{return await work;}finally{this.pending.delete(key);}
  }
  async loadBlock(archive,index,spec,key){
    const start=index*this.manifest.blockBytes,length=Math.min(this.manifest.blockBytes,spec.bytes-start);
    let bytes;
    try{
      const cached=await this.storage?.get(key);
      if(cached?.byteLength===length && await this.verify(cached,key)){
        bytes=new Uint8Array(cached);this.stats.persistentHits++;
      }
    }catch(error){this.report({type:'archive-cache-warning',message:error.message});}
    if(!bytes){
      const response=await this.fetcher(new URL(`${archive}.zip`,this.baseURL),{headers:{Range:`bytes=${start}-${start+length-1}`}});
      if(response.status!==206 || response.headers.get('Content-Range')!==`bytes ${start}-${start+length-1}/${spec.bytes}`){
        await response.body?.cancel();throw new Error('Archive server must support exact bounded HTTP ranges');
      }
      const data=await response.arrayBuffer();
      if(data.byteLength!==length || !await this.verify(data,key))throw new Error('Original archive block integrity mismatch');
      bytes=new Uint8Array(data);this.stats.networkBlocks++;this.stats.networkBytes+=length;
      try{await this.storage?.put(key,data);}catch(error){this.report({type:'archive-cache-warning',message:error.message});}
    }
    if(bytes.byteLength>this.maxMemoryBytes)throw new Error('Archive block exceeds memory budget');
    while(this.stats.residentBytes+bytes.byteLength>this.maxMemoryBytes){
      const oldest=this.cache.keys().next().value;
      this.stats.residentBytes-=this.cache.get(oldest).byteLength;this.cache.delete(oldest);
    }
    this.cache.set(key,bytes);this.stats.residentBytes+=bytes.byteLength;
    this.stats.peakResidentBytes=Math.max(this.stats.peakResidentBytes,this.stats.residentBytes);
    return bytes;
  }
  async read(archive,position,destination){
    const spec=this.manifest.archives[archive];
    if(!spec || !Number.isSafeInteger(position)||position<0)throw new Error('Invalid archive read');
    const length=Math.max(0,Math.min(destination.byteLength,spec.bytes-position));
    let copied=0;
    while(copied<length){
      const at=position+copied,index=Math.floor(at/this.manifest.blockBytes),offset=at%this.manifest.blockBytes;
      const bytes=await this.block(archive,index),count=Math.min(length-copied,bytes.byteLength-offset);
      destination.set(bytes.subarray(offset,offset+count),copied);copied+=count;
    }
    this.stats.reads++;this.stats.readBytes+=copied;return copied;
  }
  clear(){this.cache.clear();this.stats.residentBytes=0;}
}

export async function openArchiveDatabase(factory=indexedDB) {
  const database=await new Promise((resolve,reject)=>{
    const request=factory.open('0ad-original-archive-blocks-v1',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('blocks');
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
    request.onblocked=()=>reject(new Error('Archive cache database upgrade is blocked'));
  });
  database.onversionchange=()=>database.close();
  function transaction(mode,key,value){
    return new Promise((resolve,reject)=>{
      const tx=database.transaction('blocks',mode),store=tx.objectStore('blocks');
      const request=mode==='readonly'?store.get(key):store.put(value,key);
      tx.oncomplete=()=>resolve(request.result);tx.onabort=()=>reject(tx.error||request.error||new Error('Archive cache transaction aborted'));
      tx.onerror=()=>{};
    });
  }
  return {get:key=>transaction('readonly',key),put:(key,value)=>transaction('readwrite',key,value),close:()=>database.close()};
}
