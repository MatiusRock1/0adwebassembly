import {validateSharedRequest,completeSharedRequest} from './shared-request.mjs';

export async function openArchiveService(manifest,{report=()=>{},onFailure=()=>{}}={}){
  const worker=new Worker(new URL('./archive-worker.mjs',import.meta.url),{type:'module',name:'0ad-archive-cache'});
  let nextId=1,closed=false,completion;
  const pending=new Map();
  function fail(error){
    if(closed)return;closed=true;worker.terminate();
    for(const request of pending.values()){clearTimeout(request.timer);request.reject(error);}pending.clear();
    onFailure(error);
  }
  function rpc(type,args={}){
    if(closed)return Promise.reject(new Error('Archive worker is closed'));
    const id=nextId++;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{pending.delete(id);fail(new Error('Archive worker timed out'));reject(new Error('Archive worker timed out'));},30000);
      pending.set(id,{resolve,reject,timer});worker.postMessage({type,id,...args});
    });
  }
  worker.addEventListener('error',event=>{event.preventDefault();fail(new Error(event.message||'Archive worker failed'));});
  worker.addEventListener('messageerror',()=>fail(new Error('Archive worker message could not be decoded')));
  worker.addEventListener('message',({data})=>{
    if(data.type==='fatal'){fail(new Error(data.message));return;}
    if(data.type==='event'){report(data.event);return;}
    const request=pending.get(data.id);if(!request)return;
    pending.delete(data.id);clearTimeout(request.timer);
    if(data.error)request.reject(new Error(data.error));else request.resolve(data.value);
  });
  try{
    const diagnostics=await rpc('init',{manifest,baseURL:location.href});
    return {diagnostics,
      readShared(archive,position,buffer,offset,length,ready,result){
        const request={type:'read',archive,position,buffer,offset,length,ready,result};
        validateSharedRequest(request);
        if(closed){completeSharedRequest(request,false);return;}
        try{worker.postMessage(request);}catch(error){completeSharedRequest(request,false);fail(error);}
      },
      snapshot:()=>rpc('snapshot'),
      dispose:()=>completion??=(async()=>{try{if(!closed)await rpc('dispose');}finally{closed=true;worker.terminate();}})()
    };
  }catch(error){fail(error);throw error;}
}

export function installArchiveNodes(module,manifest){
  for(const [name,spec] of Object.entries(manifest.archives)){
    const directory=`/data/mods/${name}`;module.FS.mkdirTree(directory);
    const path=`${directory}/${name}.zip`;module.FS.writeFile(path,new Uint8Array(0));
    const node=module.FS.lookupPath(path).node;
    node.usedBytes=spec.bytes;node.phase45Archive=name;
    node.stream_ops={...node.stream_ops,
      read(){throw new module.FS.ErrnoError(29);},
      write(){throw new module.FS.ErrnoError(69);}};
  }
}

export async function installPersistentConfig(module,report=()=>{}){
  if(!module.IDBFS)throw new Error('IDBFS support is missing from the combined build');
  const directory='/persistent-config';module.FS.mkdirTree(directory);
  module.FS.mount(module.IDBFS,{},directory);
  const sync=populate=>new Promise((resolve,reject)=>module.FS.syncfs(populate,error=>error?reject(error):resolve()));
  let available=true;
  try{
    await sync(true);
    if(module.FS.analyzePath(`${directory}/user.cfg`).exists)
      module.FS.writeFile('/data/config/user.cfg',module.FS.readFile(`${directory}/user.cfg`));
  }catch(error){available=false;report({type:'config-cache-warning',message:error.message});}
  let pending=Promise.resolve();
  return {get available(){return available;},
    save(){
      if(!available)return;
      module.FS.writeFile(`${directory}/user.cfg`,module.FS.readFile('/data/config/user.cfg'));
      pending=pending.then(()=>sync(false)).catch(error=>{available=false;report({type:'config-cache-warning',message:error.message});});
    },
    flush:()=>pending
  };
}
