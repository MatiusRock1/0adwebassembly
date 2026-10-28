// These semantic cases also run on the unmodified switch interpreter as an
// oracle. They exercise IC invalidation and fallback as well as common cases;
// passing them alone does not prove individual CacheIR handler coverage.
{"undefined-result-and-prototype-invalidation", R"JS((()=>{
  const prototype={};
  const objects=Array.from({length:8},(_,i)=>{
    const object=Object.create(prototype);object['shape'+i]=i;return object;
  });
  function read(object){return object.optional;}
  for(let i=0;i<16384;i++)if(read(objects[i%8])!==undefined)return false;
  prototype.optional=19;
  for(const object of objects)if(read(object)!==19)return false;
  delete prototype.optional;
  for(const object of objects)if(read(object)!==undefined)return false;
  Object.defineProperty(prototype,'optional',{get(){collectSlice();return 31;},configurable:true});
  for(const object of objects)if(read(object)!==31)return false;
  objects[0].optional; // Keep the getter hot before shadowing it.
  Object.defineProperty(objects[0],'optional',{value:undefined,configurable:true});
  if(read(objects[0])!==undefined || read(objects[1])!==31)return false;
  const proxy=new Proxy(objects[1],{get(target,key,receiver){
    if(key==='optional'){collect();return 47;}return Reflect.get(target,key,receiver);
  }});
  return read(proxy)===47 && read(objects[0])===undefined;
})())JS"},
{"polymorphic-shapes-with-GC-and-accessors", R"JS((()=>{
  const objects=Array.from({length:8},(_,i)=>{const object={x:i};object['shape'+i]=i;return object;});
  function read(object){return object.x;}
  let total=0;
  for(let i=0;i<16384;i++)total+=read(objects[i%8]);
  if(total!==57344)return false;
  for(let round=0;round<16;round++){
    collectSlice();
    for(let i=0;i<8;i++){
      const object=objects[i];
      Object.defineProperty(object,'x',{value:i+10,writable:true,configurable:true,enumerable:true});
      if(read(object)!==i+10)return false;
      delete object.x;
      Object.setPrototypeOf(object,null);
      if(read(object)!==undefined)return false;
      Object.setPrototypeOf(object,{x:i+100});
      if(read(object)!==i+100)return false;
      Object.defineProperty(object,'x',{get(){collectSlice();return i+200;},configurable:true});
      if(read(object)!==i+200)return false;
    }
  }
  collect();
  return objects.every((object,i)=>read(object)===i+200);
})())JS"},
{"dense-holes-sparse-indices-and-prototype-getters", R"JS((()=>{
  function read(array,index){return array[index];}
  for(let round=0;round<32;round++){
    const prototype=Object.create(Array.prototype);
    prototype[-1]=23;prototype[7]=17;
    const array=[2,,6];Object.setPrototypeOf(array,prototype);
    for(let i=0;i<128;i++){
      if(read(array,1)!==undefined || read(array,2)!==6 || read(array,7)!==17 ||
         read(array,-1)!==23 || read(array,-0)!==2 || read(array,2147483647)!==undefined ||
         read(array,-2147483648)!==undefined)return false;
    }
    array[1]=11;
    if(read(array,1)!==11)return false;
    delete array[1];
    if(read(array,1)!==undefined)return false;
    Object.defineProperty(prototype,'1',{get(){collectSlice();return 37;},configurable:true});
    if(read(array,1)!==37)return false;
    Object.defineProperty(array,'1',{value:41,configurable:true});
    if(read(array,1)!==41)return false;
    delete array[1];
    if(read(array,1)!==37)return false;
    collectSlice();
  }
  return true;
})())JS"},
