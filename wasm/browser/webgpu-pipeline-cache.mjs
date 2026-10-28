// Pipelines that earlier sessions compiled, so that the render worker can
// compile them in the background before the engine first draws with them.
// Only descriptor recipes are stored: program, variant and fixed-function state.
const DATABASE='0ad-webgpu-pipelines',STORE='recipes',VERSION=1;
export const PIPELINE_CACHE_LIMIT=2048;

// A new shader catalog, GPU or canvas format starts a separate list.
export function pipelineCacheKey(catalog,diagnostics){
  const adapter=diagnostics?.adapter??{};
  return [catalog?.provenance?.buildFingerprint??'unversioned',adapter.vendor,adapter.architecture,
    adapter.device,adapter.description,diagnostics?.format].map(value=>value??'').join('|');
}

function request(operation){
  return new Promise((resolve,reject)=>{operation.onsuccess=()=>resolve(operation.result);operation.onerror=()=>reject(operation.error);});
}

// IndexedDB failures only lose the warm list; they never stop the renderer.
export class PipelineStore {
  constructor({key,indexedDB=globalThis.indexedDB,report=()=>{},delayMs=2000,limit=PIPELINE_CACHE_LIMIT}={}){
    this.key=key;this.indexedDB=indexedDB;this.report=report;this.delayMs=delayMs;this.limit=limit;
    this.recipes=new Map();this.timer=null;this.saving=Promise.resolve();this.closed=false;
    this.stats={loaded:0,added:0,removed:0,saves:0,errors:0};
  }
  open(){
    if(!this.indexedDB)return Promise.reject(new Error('IndexedDB is unavailable'));
    return this.database??=new Promise((resolve,reject)=>{
      const opening=this.indexedDB.open(DATABASE,VERSION);
      opening.onupgradeneeded=()=>opening.result.createObjectStore(STORE);
      opening.onsuccess=()=>resolve(opening.result);opening.onerror=()=>reject(opening.error);
    });
  }
  fail(error){this.stats.errors++;this.report({type:'pipeline-cache-error',message:error?.message??String(error)});}
  // Recipes added before the stored list arrives stay after it, in use order.
  async load(){
    let stored=[];
    try{
      const database=await this.open();
      const value=await request(database.transaction(STORE,'readonly').objectStore(STORE).get(this.key));
      if(value?.version===VERSION&&Array.isArray(value.recipes))stored=value.recipes;
    }catch(error){this.fail(error);}
    const added=this.recipes;this.recipes=new Map();
    for(const recipe of stored)this.recipes.set(JSON.stringify(recipe),recipe);
    this.stats.loaded=this.recipes.size;
    for(const [key,recipe] of added)this.recipes.set(key,recipe);
    return stored;
  }
  // The key is the recipe's JSON; storing its parse keeps no engine object alive.
  add(key){
    if(this.closed||this.recipes.has(key)||this.recipes.size>=this.limit)return;
    this.recipes.set(key,JSON.parse(key));this.stats.added++;this.schedule();
  }
  remove(key){if(this.recipes.delete(key)){this.stats.removed++;this.schedule();}}
  schedule(){
    if(this.timer!==null||this.closed)return;
    this.timer=setTimeout(()=>{this.timer=null;this.save();},this.delayMs);
  }
  save(){
    const value={version:VERSION,recipes:[...this.recipes.values()]};
    return this.saving=this.saving.then(async()=>{
      try{
        const database=await this.open(),transaction=database.transaction(STORE,'readwrite');
        transaction.objectStore(STORE).put(value,this.key);
        await new Promise((resolve,reject)=>{transaction.oncomplete=resolve;transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error);});
        this.stats.saves++;
      }catch(error){this.fail(error);}
    });
  }
  async close(){
    if(this.closed)return;
    if(this.timer!==null){clearTimeout(this.timer);this.timer=null;await this.save();}
    this.closed=true;await this.saving;
    try{if(this.database)(await this.database).close();}catch{}
  }
}

// Compile stored recipes a few at a time, in their original use order. A draw
// that needs a recipe still queued compiles it at once; the queue then skips it.
export class PipelineWarmup {
  constructor(engine,recipes,{concurrency=4,onFailure=()=>{},report=()=>{},now=()=>performance.now()}={}){
    this.engine=engine;this.queue=[...recipes];this.concurrency=concurrency;this.onFailure=onFailure;
    this.report=report;this.now=now;this.active=0;this.stopped=false;
    this.stats={queued:this.queue.length,compiled:0,skipped:0,failed:0,started:null,finishedMilliseconds:null};
    this.done=new Promise(resolve=>{this.resolve=resolve;});
  }
  start(){this.stats.started=this.now();this.pump();return this.done;}
  pump(){
    while(!this.stopped&&this.active<this.concurrency&&this.queue.length){
      const recipe=this.queue.shift(),key=JSON.stringify(recipe);
      let warm;
      try{warm=this.engine.warmPipeline(key,recipe);}
      catch(error){this.failed(key,error);continue;}
      if(!warm){this.stats.skipped++;continue;}
      this.active++;
      warm.then(()=>{this.stats.compiled++;},error=>this.failed(key,error))
        .finally(()=>{this.active--;this.pump();});
    }
    if(!this.active&&(this.stopped||!this.queue.length)&&this.stats.finishedMilliseconds===null){
      this.stats.finishedMilliseconds=this.now()-this.stats.started;
      if(!this.stopped)this.report({type:'pipeline-warmup',...this.stats});
      this.resolve(this.stats);
    }
  }
  failed(key,error){
    this.stats.failed++;this.onFailure(key);
    if(this.stats.failed<=4)this.report({type:'pipeline-warmup-skipped',message:error?.message??String(error)});
  }
  stop(){this.stopped=true;this.queue=[];this.pump();}
}
