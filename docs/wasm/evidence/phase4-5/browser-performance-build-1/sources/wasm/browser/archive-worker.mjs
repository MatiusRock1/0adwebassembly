import {ArchiveBlocks,openArchiveDatabase} from './archive-blocks.mjs';
import {completeSharedRequest,validateSharedRequest} from './shared-request.mjs';

let blocks,database,queue=Promise.resolve();
const report=event=>postMessage({type:'event',event});
async function consume(message){
  if(message.type==='init'){
    try{database=await openArchiveDatabase();}
    catch(error){report({type:'archive-cache-warning',message:error.message});}
    blocks=new ArchiveBlocks({manifest:message.manifest,baseURL:message.baseURL,storage:database,report});
    return {persistent:Boolean(database),maxMemoryBytes:blocks.maxMemoryBytes};
  }
  if(message.type==='read'){
    let validated=false;
    try{
      validateSharedRequest(message);validated=true;
      const bytes=await blocks.read(message.archive,message.position,new Uint8Array(message.buffer,message.offset,message.length));
      completeSharedRequest(message,true,bytes);
    }catch(error){
      if(validated)completeSharedRequest(message,false);
      postMessage({type:'fatal',message:error.stack||String(error)});
    }
    return;
  }
  if(message.type==='snapshot')return {...blocks.stats,persistent:Boolean(database),maxMemoryBytes:blocks.maxMemoryBytes};
  if(message.type==='dispose'){blocks.clear();database?.close();return {disposed:true};}
  throw new Error('Unknown archive worker message');
}
self.addEventListener('message',({data})=>{
  // One in-flight block read keeps memory bounded even with several C++ file
  // readers. The caller waits in its pthread, never in the browser window.
  queue=queue.then(()=>consume(data)).then(value=>{
    if(data.id)postMessage({id:data.id,value});
  },error=>{
    if(data.id)postMessage({id:data.id,error:error.stack||String(error)});
    else postMessage({type:'fatal',message:error.stack||String(error)});
  });
});
