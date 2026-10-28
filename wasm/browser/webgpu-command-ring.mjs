// Reader of the engine's shared command ring (Device.cpp, WASM_WEBGPU_SHARED_RING).
// The engine thread is the only producer and this render worker the only
// consumer. A record only borrows engine memory: each call's strings and bytes
// stay owned by C++ until the worker writes that call's ready flag.
export const RING_HEADER_BYTES=16,RING_RECORD_BYTES=48;
const decoder=new TextDecoder();

export class CommandRing {
  constructor(memory,address,capacity){
    this.memory=memory;this.address=address;this.capacity=capacity;this.closed=false;this.views();
    if(!Number.isSafeInteger(address)||address<=0||address%8||!Number.isSafeInteger(capacity)||capacity<=0||
       address+RING_HEADER_BYTES+capacity*RING_RECORD_BYTES>this.bytes.byteLength)throw new Error('Invalid shared command ring');
    const header=address>>>2;
    if(this.words[header+2]!==capacity||this.words[header+3]!==RING_RECORD_BYTES)throw new Error('Shared command ring layout changed');
    this.read=Atomics.load(this.signed,header+1)>>>0;
    this.stats={records:0,polls:0,maxBatch:0,waits:0};
  }
  // WASM memory may grow; a grown memory has a new, longer SharedArrayBuffer.
  views(){
    const buffer=this.memory.buffer;if(this.buffer===buffer)return;
    this.buffer=buffer;this.bytes=new Uint8Array(buffer);this.words=new Uint32Array(buffer);
    this.signed=new Int32Array(buffer);this.doubles=new Float64Array(buffer);
  }
  // Copy every published record out of the ring and free its slot for reuse.
  poll(){
    this.views();
    const header=this.address>>>2,head=Atomics.load(this.signed,header)>>>0,records=[];
    while(this.read!==head){
      const base=this.address+RING_HEADER_BYTES+(this.read%this.capacity)*RING_RECORD_BYTES,w=base>>>2,words=this.words;
      const sync=words[w+11]===1;
      records.push({method:this.text(words[w+2],words[w+3]),args:JSON.parse(this.text(words[w+4],words[w+5])),
        offset:words[w+6],length:words[w+7],sequence:sync?undefined:words[w+8],ready:words[w+9],
        result:sync?words[w+10]:undefined,publishedAt:this.doubles[base>>>3],ringIndex:(this.read+1)>>>0});
      this.read=(this.read+1)>>>0;
    }
    this.stats.polls++;
    if(records.length){
      this.stats.records+=records.length;this.stats.maxBatch=Math.max(this.stats.maxBatch,records.length);
      Atomics.store(this.signed,header+1,this.read|0);Atomics.notify(this.signed,header+1);
    }
    return records;
  }
  text(pointer,length){
    if(pointer+length>this.bytes.byteLength)throw new Error('Shared command ring text outside WASM memory');
    // TextDecoder rejects views of shared memory; decode a private copy.
    return decoder.decode(this.bytes.slice(pointer,pointer+length));
  }
  // Deliver records in publication order until close(). The timeout only lets
  // a closed ring stop; the engine wakes this waiter after every record.
  async run(deliver){
    const head=this.address>>>2;
    while(!this.closed){
      for(const record of this.poll())deliver(record);
      const observed=Atomics.load(this.signed,head);
      if((observed>>>0)!==this.read)continue;
      this.stats.waits++;
      const wait=Atomics.waitAsync(this.signed,head,observed,1000);
      if(wait.async)await wait.value;
    }
  }
  close(){this.closed=true;}
}
