export function validateSharedRequest({buffer,offset,length,ready,result}) {
  if(!(buffer instanceof SharedArrayBuffer))throw new Error('Transport requires shared WASM memory');
  for(const value of [offset,length,ready])if(!Number.isSafeInteger(value)||value<0)throw new Error('Invalid shared range');
  if(offset+length>buffer.byteLength || ready===0 || ready%4 || ready+4>buffer.byteLength)
    throw new Error('Shared request outside WASM memory');
  if(result!==undefined && (!Number.isSafeInteger(result)||result<=0||result%4||result+4>buffer.byteLength||result===ready))
    throw new Error('Invalid shared result');
}

export function completeSharedRequest(request,success,value=0) {
  const words=new Int32Array(request.buffer);
  if(success && request.result!==undefined)Atomics.store(words,request.result>>>2,value|0);
  Atomics.store(words,request.ready>>>2,success?1:2);
  Atomics.notify(words,request.ready>>>2);
}
