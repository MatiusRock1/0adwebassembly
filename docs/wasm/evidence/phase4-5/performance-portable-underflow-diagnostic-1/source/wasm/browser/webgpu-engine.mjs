// WebGPU implementation for source/renderer/backend/webgpu. GPU objects belong
// to the window; the engine pthread sends batches, never fabricated GL calls.
import {adaptBorderSampling,borderConstants} from './webgpu-border.mjs';
import {UploadBelt} from './webgpu-upload.mjs';
import {CommandDispatcher} from './webgpu-dispatch.mjs';
const formats = [null,'r8unorm','rg8unorm','rg8uint',null,'rgba8unorm','rgba8unorm-srgb','rgba8uint','bgra8unorm','bgra8unorm-srgb',
  'rgba8unorm','rgba8unorm','r16unorm','r16uint','r16sint','r16float','rg16unorm','rg16uint','rg16sint','rg16float',null,'rgba16float',
  'r32float','rg32float',null,'rgba32float','rg11b10ufloat','depth16unorm','depth24plus','depth24plus-stencil8','depth32float','depth32float-stencil8',
  'bc1-rgba-unorm','bc1-rgba-unorm-srgb','bc1-rgba-unorm','bc1-rgba-unorm-srgb','bc2-rgba-unorm','bc2-rgba-unorm-srgb','bc3-rgba-unorm','bc3-rgba-unorm-srgb'];
const vertexFormats = {1:'unorm8',2:'unorm8x2',3:'uint8x2',5:'unorm8x4',7:'uint8x4',12:'unorm16',13:'uint16',14:'sint16',15:'float16',
  16:'unorm16x2',17:'uint16x2',18:'sint16x2',19:'float16x2',21:'float16x4',22:'float32',23:'float32x2',24:'float32x3',25:'float32x4'};
const comparisons = ['never','less','equal','less-equal','greater','not-equal','greater-equal','always'];
const stencilOps = ['keep','zero','replace','increment-clamp','decrement-clamp','invert','increment-wrap','decrement-wrap'];
const blendFactors = ['zero','one','src','one-minus-src','dst','one-minus-dst','src-alpha','one-minus-src-alpha','dst-alpha','one-minus-dst-alpha',
  'constant','one-minus-constant','constant','one-minus-constant','src-alpha-saturated','src1','one-minus-src1','src1-alpha','one-minus-src1-alpha'];
const blendOps = ['add','subtract','reverse-subtract','min','max'];
const align = (n,a) => Math.ceil(n/a)*a;
const binaryCommandSizes = [1,1,3,1,3,2,2,2,4,5,3,2,4];

// Original small DXT textures (including the 1x1 default normal) are legal in
// GL but WebGPU requires block-aligned base dimensions. Decode those resources
// from their BC palette into RGBA8 storage (rounded to 8-bit channel precision);
// the original files, logical dimensions and mip chain remain unchanged.
export function decodeBC(data,width,height,formatIndex) {
  const bc1=formatIndex>=32 && formatIndex<=35,bc2=formatIndex===36||formatIndex===37;
  const blockBytes=bc1?8:16,columns=Math.ceil(width/4),rows=Math.ceil(height/4);
  if(data.length<columns*rows*blockBytes)throw new Error('Truncated original BC texture upload');
  const result=new Uint8Array(width*height*4),view=new DataView(data.buffer,data.byteOffset,data.byteLength);
  const color565=n=>[(n>>>11)*255/31,((n>>>5)&63)*255/63,(n&31)*255/31];
  for(let by=0;by<rows;by++)for(let bx=0;bx<columns;bx++){
    const offset=(by*columns+bx)*blockBytes,colorOffset=offset+(bc1?0:8);
    const c0=view.getUint16(colorOffset,true),c1=view.getUint16(colorOffset+2,true);
    const palette=[color565(c0),color565(c1)];
    if(c0>c1||!bc1){palette.push(palette[0].map((v,i)=>(2*v+palette[1][i])/3));palette.push(palette[0].map((v,i)=>(v+2*palette[1][i])/3));}
    else{palette.push(palette[0].map((v,i)=>(v+palette[1][i])/2));palette.push([0,0,0]);}
    const codes=view.getUint32(colorOffset+4,true),alpha=[data[offset],data[offset+1]];
    if(!bc1&&!bc2){if(alpha[0]>alpha[1])for(let i=1;i<=6;i++)alpha.push(((7-i)*alpha[0]+i*alpha[1])/7);
      else{for(let i=1;i<=4;i++)alpha.push(((5-i)*alpha[0]+i*alpha[1])/5);alpha.push(0,255);}}
    for(let y=0;y<4;y++)for(let x=0;x<4;x++){
      const px=bx*4+x,py=by*4+y;if(px>=width||py>=height)continue;
      const pixel=y*4+x,index=(codes>>>(pixel*2))&3,destination=(py*width+px)*4;
      for(let c=0;c<3;c++)result[destination+c]=Math.round(palette[index][c]);
      let a=255;
      if(bc1){if(formatIndex>=34 && c0<=c1 && index===3)a=0;}
      else if(bc2)a=((data[offset+(pixel>>>1)]>>>((pixel&1)*4))&15)*17;
      else{const bit=pixel*3,byte=offset+2+(bit>>>3),index=((data[byte]|((data[byte+1]||0)<<8))>>>(bit&7))&7;a=Math.round(alpha[index]);}
      result[destination+3]=a;
    }
  }
  return result;
}

export class WebGPUEngine {
  constructor(session, canvas, catalog, report = () => {}) {
    this.session = session; this.device = session.device; this.canvas = canvas; this.context = session.context;
    this.catalog = catalog; this.report = report; this.objects = new Map(); this.nextId = 1;
    this.bindings = new Map(); this.nextBinding = 1; this.retired = new Set(); this.pipelines = new Map();
    this.uniformCapacity = 16*1024*1024; this.uniformCursor = 0;
    this.uniformHost = new Uint8Array(this.uniformCapacity);
    this.uniformBuffer = this.device.createBuffer({label:'0ad frame uniform arena',size:this.uniformCapacity,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});
    this.live = true; this.encoder = null; this.pass = null; this.target = null; this.currentPipeline = null;
    this.vertices = new Map(); this.indexBuffer = null; this.currentLayout = null;
    this.viewportRect = null; this.scissorRect = null; this.labels = [];
    this.stats = {frames:0,draws:0,submissions:0,pipelineCompiles:0,commandBatches:0,uploadBytes:0};
    this.transientArenas={vertex:[],index:[]};
    this.uploadBelt=new UploadBelt(this.device,{onError:error=>{if(this.live&&!this.disposed)this.report({type:'engine-upload-map-error',message:error.message});}});
    this.commandDispatcher=new CommandDispatcher();
    session.device.lost.then(info => { this.live = false;this.publishLiveState();report({type:'engine-device-lost',reason:info.reason,message:info.message,expected:Boolean(this.disposed)}); });
  }
  put(object) { const id=this.nextId++; this.objects.set(id,object); return id; }
  get(id) { const object=this.objects.get(id); if(!object) throw new Error(`Unknown WebGPU engine object ${id}`); return object; }
  encoderForWork() { return this.encoder ||= this.device.createCommandEncoder({label:'0ad frame'}); }
  signal(address,success=true) {
    const words = new Int32Array(this.heap().buffer);
    Atomics.store(words,address>>>2,success?1:2);Atomics.notify(words,address>>>2);
  }
  publishLiveState(live=this.live){
    if(this.liveAddress)Atomics.store(new Int32Array(this.heap().buffer),this.liveAddress>>>2,Number(live));
  }
  call(method,args,data) {
    if (method === 'commands') { this.stats.commandBatches++; for(const [name,values] of args) this.command(name,values,data); return 1; }
    if (method === 'valid') return Number(this.live);
    if (method === 'observeLive') {
      const address=args[0];
      if(!Number.isSafeInteger(address) || address<=0 || address%4 || address+4>this.heap().byteLength)throw new Error('Invalid shared device health address');
      if(args[1]){this.liveAddress=address;this.publishLiveState();}
      else if(this.liveAddress===address){this.publishLiveState(false);this.liveAddress=0;}
      return 1;
    }
    if (method === 'feature') return Number(this.device.features.has(args[0]));
    if (method === 'limit') return this.device.limits[args[0]];
    if (method === 'formatSupported' || method === 'attachmentSupported') {
      const format=formats[args[0]];
      if(!format) return 0;
      if(format.startsWith('bc')) return method==='formatSupported' && this.device.features.has('texture-compression-bc') ? 1 : 0;
      if(format==='depth32float-stencil8') return Number(this.device.features.has('depth32float-stencil8'));
      if(method==='attachmentSupported' && format==='rg11b10ufloat')return Number(this.device.features.has('rg11b10ufloat-renderable'));
      if(method==='formatSupported' && ['r32float','rg32float','rgba32float'].includes(format))return Number(this.device.features.has('float32-filterable'));
      // Norm16 is optional and cannot be assumed on the baseline API.
      if(['r16unorm','rg16unorm'].includes(format))return 0;
      return 1;
    }
    if (method === 'release') {
      this.retired.add(args[0]);
      for(const id of this.objects.get(args[0])?.skinningScratch?.values()??[])this.retired.add(id);
      return 1;
    }
    if (method === 'resize') { this.resize(...args); return 1; }
    if (method === 'acquire') { this.resize(...args); return Number(this.live); }
    if (method === 'backbuffer') return this.put({kind:'framebuffer',backbuffer:true,cl:args[0],cs:args[1],dl:args[2],ds:args[3],clear:[0,0,0,1],width:this.canvas.width,height:this.canvas.height});
    if (method === 'present') {
      // Canvas textures expire at the browser's presentation boundary. Engine
      // recording spans several proxy tasks, so render into an owned image,
      // then acquire/copy/submit the browser texture in this single task.
      this.encoderForWork().copyTextureToTexture({texture:this.presentationTexture},{texture:this.context.getCurrentTexture()},[this.width,this.height,1]);
      this.submit(); this.stats.frames++; return 1;
    }
    if (method === 'idle') {
      if(!this.live){this.signal(args[0]);return 1;}
      this.submit();const address=args[0];this.device.queue.onSubmittedWorkDone().then(()=>this.signal(address),error=>{this.report({type:'idle-error',message:error.message});this.signal(address,false);});return 1;
    }
    if (method === 'createBuffer') {
      const [label,type,size,usage]=args;
      let flags=GPUBufferUsage.COPY_DST|GPUBufferUsage.COPY_SRC;
      flags|=[GPUBufferUsage.VERTEX,GPUBufferUsage.INDEX,0,GPUBufferUsage.UNIFORM][type];
      if(usage&8)flags|=GPUBufferUsage.STORAGE;
      return this.put({kind:'buffer',buffer:this.device.createBuffer({label,size:align(size,4),usage:flags}),size,type});
    }
    if (method === 'uploadBuffer') {this.device.queue.writeBuffer(this.get(args[0]).buffer,args[1],data);this.stats.uploadBytes+=data.byteLength;return 1;}
    if (method === 'stageBuffer') {
      const buffer=this.device.createBuffer({label:'0ad upload staging',size:align(data.byteLength,4),usage:GPUBufferUsage.COPY_SRC,mappedAtCreation:true});
      new Uint8Array(buffer.getMappedRange()).set(data);buffer.unmap();this.stats.uploadBytes+=data.byteLength;
      return this.put({kind:'staging',buffer,size:align(data.byteLength,4)});
    }
    if (method === 'createTexture') return this.createTexture(args);
    if (method === 'uploadTexture') return this.uploadTexture(args,data);
    if (method === 'stageTexture') return this.uploadTexture(args,data,true);
    if (method === 'createFramebuffer') {
      const [label,color,depth,cl,cs,dl,ds,clear]=args;const t=this.get(color||depth);
      return this.put({kind:'framebuffer',label,color,depth,cl,cs,dl,ds,clear,width:t.width,height:t.height});
    }
    if (method === 'createLayout') return this.put({kind:'layout',attributes:args});
    if (method === 'createShader') return this.createShader(...args);
    if (method === 'binding') { const shader=this.get(args[0]); return shader.bindingSlots.get(args[1]) ?? -1; }
    if (method === 'createPipeline') return this.put({kind:'pipeline',shader:this.get(args[0]),depth:args[1],blend:args[2],raster:args[3]});
    if (method === 'createComputePipeline') return this.put({kind:'computePipeline',shader:this.get(args[0])});
    if (method === 'readback') {this.readback(args);return 1;}
    throw new Error(`Unknown WebGPU engine method ${method}`);
  }
  resize(width,height) {
    if(width<=0 || height<=0)throw new Error('Invalid WebGPU surface dimensions');
    if(this.width===width && this.height===height)return;
    this.submit();
    if(this.depthTexture){const old=this.depthTexture;const color=this.presentationTexture;const release=()=>{old.destroy();color?.destroy();};this.device.queue.onSubmittedWorkDone().then(release,release);}
    this.canvas.width=width;this.canvas.height=height;this.width=width;this.height=height;
    this.depthTexture=this.device.createTexture({label:'0ad presentation depth-stencil',size:[width,height],format:'depth24plus-stencil8',usage:GPUTextureUsage.RENDER_ATTACHMENT});
    this.presentationTexture=this.device.createTexture({label:'0ad owned presentation image',size:[width,height],format:this.session.diagnostics.format,usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC|GPUTextureUsage.COPY_DST|GPUTextureUsage.TEXTURE_BINDING});
    this.currentTexture=null;
  }
  createTexture([label,type,usage,formatIndex,width,height,s,mipLevelCount,sampleCount]) {
    const sourceFormat=formats[formatIndex];if(!sourceFormat)throw new Error(`Unsupported texture format ${formatIndex}`);
    const decompress=sourceFormat.startsWith('bc') && (width%4!==0||height%4!==0);
    const format=decompress?(sourceFormat.endsWith('srgb')?'rgba8unorm-srgb':'rgba8unorm'):sourceFormat;
    let flags=0;
    if(usage&1)flags|=GPUTextureUsage.COPY_SRC;if(usage&2)flags|=GPUTextureUsage.COPY_DST;
    if(usage&4)flags|=GPUTextureUsage.TEXTURE_BINDING;if(usage&24)flags|=GPUTextureUsage.RENDER_ATTACHMENT;
    if(usage&32)flags|=GPUTextureUsage.STORAGE_BINDING;
    if(sampleCount===2){sampleCount=4;this.report({type:'sample-count-mapping',requested:2,effective:4});}
    const texture=this.device.createTexture({label,size:[width,height,type===2?6:1],format,mipLevelCount,sampleCount,usage:flags});
    const modes=['repeat','mirror-repeat','clamp-to-edge','clamp-to-edge'];
    if(s.slice(3,6).includes(3)){
      const key=JSON.stringify(s.slice(3,6));this.reportedSamplerMappings??=new Set();
      if(!this.reportedSamplerMappings.has(key)){
        this.reportedSamplerMappings.add(key);
        this.report({type:'sampler-address-emulation',label,requested:s.slice(3,6),effective:'portable border filtering in the original shader sampling path'});
      }
    }
    const samplerDesc={magFilter:s[0]?'linear':'nearest',minFilter:s[1]?'linear':'nearest',mipmapFilter:s[2]?'linear':'nearest',
      addressModeU:modes[s[3]],addressModeV:modes[s[4]],addressModeW:modes[s[5]],
      maxAnisotropy:Math.max(1,Math.min(16,s[6])),lodMaxClamp:mipLevelCount-1};
    if(samplerDesc.maxAnisotropy>1){samplerDesc.magFilter='linear';samplerDesc.minFilter='linear';samplerDesc.mipmapFilter='linear';}
    if(s[7])samplerDesc.compare=comparisons[s[8]];
    return this.put({kind:'texture',texture,width,height,format,formatIndex,decompress,sampleCount,mipLevelCount,type,
      samplerState:[...s],sampler:this.device.createSampler(samplerDesc),view:texture.createView({dimension:type===2?'cube':'2d',aspect:format.includes('stencil')?'depth-only':'all'})});
  }
  uploadTexture([id,formatIndex,x,y,width,height,mipLevel,layer],data,stage=false) {
    const t=this.get(id);let bytes=data;
    if(t.decompress)bytes=decodeBC(data,width,height,formatIndex);
    if([4,10,11].includes(formatIndex)) {
      const stride=formatIndex===4?3:1;bytes=new Uint8Array(width*height*4);
      for(let p=0;p<width*height;p++){
        if(formatIndex===10){bytes[p*4]=255;bytes[p*4+1]=255;bytes[p*4+2]=255;bytes[p*4+3]=data[p];}
        else {bytes[p*4]=data[p*stride];bytes[p*4+1]=data[p*stride+(stride===3?1:0)];bytes[p*4+2]=data[p*stride+(stride===3?2:0)];bytes[p*4+3]=255;}
      }
    }
    const compressed=t.format.startsWith('bc');
    const blockBytes=compressed?(t.format.startsWith('bc1')?8:16):0;
    const rows=compressed?Math.ceil(height/4):height;
    const bytesPerRow=compressed?Math.ceil(width/4)*blockBytes:bytes.byteLength/height;
    if(stage){
      const pitch=align(bytesPerRow,256);const buffer=this.device.createBuffer({size:pitch*rows,usage:GPUBufferUsage.COPY_SRC,mappedAtCreation:true});
      const mapped=new Uint8Array(buffer.getMappedRange());for(let row=0;row<rows;row++)mapped.set(bytes.subarray(row*bytesPerRow,(row+1)*bytesPerRow),row*pitch);buffer.unmap();
      this.stats.uploadBytes+=bytes.byteLength;
      return this.put({kind:'stagingTexture',buffer,texture:t.texture,mipLevel,origin:[x,y,layer],width:compressed?align(width,4):width,height:compressed?align(height,4):height,pitch,rows});
    }
    this.device.queue.writeTexture({texture:t.texture,mipLevel,origin:[x,y,layer]},bytes,{bytesPerRow,rowsPerImage:rows},[width,height,1]);
    this.stats.uploadBytes+=bytes.byteLength;return 1;
  }
  createShader(name,defines) {
    const program=this.catalog.programs[name];
    const relevant=program?.defines ?? [];
    const key=JSON.stringify(Object.fromEntries(relevant.filter(k=>defines[k]!==undefined).sort().map(k=>[k,defines[k]])));
    const variant=program?.variants[key];
    if(!variant){this.report({type:'missing-shader-variant',name,defines,key});throw new Error(`Missing offline WGSL variant ${name} ${key}`);}
    const shader={kind:'shader',name,variant,modules:{},bindingSlots:new Map(),uniforms:new Map(),textures:new Map(),storage:new Map(),groups:[],uniformBlocks:new Map(),uniformSnapshots:new Map()};
    shader.samplerStages={};
    for(const [stage,code] of Object.entries(variant.code)){
      const adapted=adaptBorderSampling(code,variant.textures,stage);
      shader.samplerStages[stage]=adapted.textures;
      shader.modules[stage]=this.device.createShaderModule({label:`${name} ${stage}`,code:adapted.code});
    }
    for(const block of variant.uniforms){shader.uniformBlocks.set(block.binding,new Uint8Array(align(block.size,16)));for(const member of block.members){const slot=this.nextBinding++;shader.bindingSlots.set(member.name,slot);this.bindings.set(slot,{shader,type:'uniform',block,member});}}
    for(const texture of variant.textures){const slot=this.nextBinding++;shader.bindingSlots.set(texture.name,slot);this.bindings.set(slot,{shader,type:'texture',texture});}
    for(const storage of variant.storage??[]){const slot=this.nextBinding++;shader.bindingSlots.set(storage.name,slot);this.bindings.set(slot,{shader,type:storage.type,storage});}
    const groups=[[],[],[]];
    for(const block of variant.uniforms)groups[0].push({binding:block.binding,visibility:block.visibility,buffer:{type:'uniform',hasDynamicOffset:true,minBindingSize:align(block.size,16)}});
    for(const texture of variant.textures){
      // WaterManager and PostprocManager bind their original nearest-filtered
      // depth attachments as ordinary sampler2D depthTex (not sampler2DShadow).
      // Such depth views support unfilterable-float, not filterable float.
      const ordinaryDepth=texture.name==='depthTex' && !texture.depth;
      groups[1].push({binding:texture.binding,visibility:texture.visibility,texture:{sampleType:texture.depth?'depth':ordinaryDepth?'unfilterable-float':'float',viewDimension:texture.cube?'cube':'2d'}});
      groups[1].push({binding:texture.binding+1,visibility:texture.visibility,sampler:{type:texture.depth?'comparison':ordinaryDepth?'non-filtering':'filtering'}});
    }
    for(const storage of variant.storage??[]){
      const entry={binding:storage.binding,visibility:storage.visibility};
      if(storage.type==='storageBuffer')entry.buffer={type:storage.readonly?'read-only-storage':'storage'};
      else entry.storageTexture={access:storage.readonly?'read-only':'write-only',format:storage.format};
      groups[storage.group].push(entry);
    }
    while(groups.length && groups.at(-1).length===0)groups.pop();
    shader.groups=groups.map(entries=>this.device.createBindGroupLayout({entries}));
    shader.pipelineLayout=this.device.createPipelineLayout({bindGroupLayouts:shader.groups});
    shader.group0=variant.uniforms.length?this.device.createBindGroup({layout:shader.groups[0],entries:variant.uniforms.map(block=>({binding:block.binding,resource:{buffer:this.uniformBuffer,offset:0,size:align(block.size,16)}}))}):null;
    shader.textureGroups=new Map();
    shader.storageGroups=new Map();
    return this.put(shader);
  }
  setUniform(slot,values,start=0,length=values.length){
    const b=this.bindings.get(slot);if(!b||b.type!=='uniform')throw new Error(`Invalid uniform binding ${slot}`);
    const member=b.member;
    const destination=b.destination??=new Float32Array(b.shader.uniformBlocks.get(b.block.binding).buffer);
    b.shader.uniformSnapshots?.delete(b.block.binding);
    const columns=member.columns||1,rows=member.rows||1,count=columns*rows;
    // Most original uniforms are scalars/vectors or packed mat4 values. A
    // contiguous typed copy also handles arrays whose std140 stride is packed.
    if((!member.matrixStride || member.matrixStride===rows*4) && (!member.arrayStride || member.arrayStride===count*4)){
      if(start===0 && length===values.length)destination.set(values,member.offset/4);
      else if(values.subarray)destination.set(values.subarray(start,start+length),member.offset/4);
      else for(let i=0;i<length;i++)destination[member.offset/4+i]=values[start+i];
    }else if(member.arrayStride){
      for(let i=0;i<length/count;i++)for(let c=0;c<columns;c++)for(let r=0;r<rows;r++)destination[(member.offset+i*member.arrayStride+c*(member.matrixStride||rows*4))/4+r]=values[start+i*count+c*rows+r];
    }else{
      for(let c=0;c<columns;c++)for(let r=0;r<rows;r++)destination[(member.offset+c*member.matrixStride)/4+r]=values[start+c*rows+r];
    }
  }
  setTexture(slot,id){
    const b=this.bindings.get(slot),shader=b.shader;
    if(shader.textures.get(b.texture.name)!==id){shader.samplerDirty=true;shader.lastTextureGroup=null;shader.textures.set(b.texture.name,id);}
  }
  binaryCommands(data,offset,length){
    const bytes=this.commandDataRange(data,offset,length*4);
    if(bytes.byteOffset%4)throw new Error('Unaligned binary command stream');
    const words=new Uint32Array(bytes.buffer,bytes.byteOffset,length);
    let floats;
    for(let cursor=0;cursor<words.length;){
      const op=words[cursor++],size=binaryCommandSizes[op];
      if(size===undefined || size>words.length-cursor)throw new Error('Invalid binary command opcode or length');
      // Decode directly from the immutable stream. No argument array/view or
      // recursive string dispatch is needed for each original backend command.
      switch(op){
      case 0:this.currentPipeline=this.get(words[cursor]);break;
      case 1:this.currentLayout=this.get(words[cursor]);break;
      case 2:this.vertices.set(words[cursor],{buffer:this.get(words[cursor+1]),offset:words[cursor+2]});break;
      case 3:this.indexBuffer=this.get(words[cursor]);break;
      case 4:{
        const address=this.validateCommandDataRange(data,words[cursor+1],words[cursor+2]*4);
        if(address%4)throw new Error('Unaligned binary uniform range');
        floats??=new Float32Array(data.buffer,0,Math.floor(data.buffer.byteLength/4));
        this.setUniform(words[cursor],floats,address/4,words[cursor+2]);break;}
      case 5:this.setTexture(words[cursor],words[cursor+1]);break;
      case 6:case 7:{const b=this.bindings.get(words[cursor]);b.shader.storage.set(b.storage.name,words[cursor+1]);break;}
      case 8:this.draw(false,words,cursor);break;
      case 9:this.draw(true,words,cursor);break;
      case 10:this.vertices.set(words[cursor],this.uploadTransient('vertex',this.commandDataRange(data,words[cursor+1],words[cursor+2])));break;
      case 11:{const binding=this.uploadTransient('index',this.commandDataRange(data,words[cursor],words[cursor+1]));this.indexBuffer={...binding.buffer,offset:binding.offset};break;}
      case 12:this.uploadBufferRange(words[cursor],words[cursor+1],this.commandDataRange(data,words[cursor+2],words[cursor+3]));break;
      }
      cursor+=size;
    }
  }
  command(name,a,data) {
    switch(name){
    case 'binaryCommands':{
      this.binaryCommands(data,a[0],a[1]);
      break;}
    case 'uploadBuffer':case 'uploadTexture':{
      const target=this.pass?this.target:null;this.endFramebuffer();
      if(name==='uploadBuffer'){const staged=this.get(a[2]);this.encoderForWork().copyBufferToBuffer(staged.buffer,0,this.get(a[0]).buffer,a[1],staged.size);this.retired.add(a[2]);}
      else{const staged=this.get(a[0]);this.encoderForWork().copyBufferToTexture({buffer:staged.buffer,bytesPerRow:staged.pitch,rowsPerImage:staged.rows},{texture:staged.texture,mipLevel:staged.mipLevel,origin:staged.origin},[staged.width,staged.height,1]);this.retired.add(a[0]);}
      if(target)this.beginFramebuffer(target,true);break;}
    case 'beginFramebuffer': this.beginFramebuffer(this.get(a[0]));break;
    case 'endFramebuffer': this.endFramebuffer();break;
    case 'pipeline': this.currentPipeline=this.get(a[0]);break;
    case 'computePipeline': this.currentCompute=this.get(a[0]);break;
    case 'layout':this.currentLayout=this.get(a[0]);break;
    case 'vertex':this.vertices.set(a[0],{buffer:this.get(a[1]),offset:a[2]});break;
    case 'index':this.indexBuffer=this.get(a[0]);break;
    case 'vertexData':{const binding=this.uploadTransient('vertex',a[1]);this.vertices.set(a[0],binding);break;}
    case 'indexData':{const binding=this.uploadTransient('index',a);this.indexBuffer={...binding.buffer,offset:binding.offset};break;}
    case 'vertexDataRange':{
      const binding=this.uploadTransient('vertex',this.commandDataRange(data,a[1],a[2]));
      this.vertices.set(a[0],binding);break;}
    case 'indexDataRange':{
      const binding=this.uploadTransient('index',this.commandDataRange(data,a[0],a[1]));
      this.indexBuffer={...binding.buffer,offset:binding.offset};break;}
    case 'uniformDataRange':{
      const bytes=this.commandDataRange(data,a[1],a[2]*4);
      if(bytes.byteOffset%4)throw new Error('Unaligned binary uniform range');
      this.setUniform(a[0],new Float32Array(bytes.buffer,bytes.byteOffset,a[2]));break;}
    case 'viewport':this.viewportRect=a;this.applyViewport();break;
    case 'scissor':this.scissorRect=a;this.applyScissor();break;
    case 'beginPass':case 'endPass':break;
    case 'uniform':this.setUniform(a[0],a[1]);break;
    case 'texture':this.setTexture(a[0],a[1]);break;
    case 'storageTexture':case 'storageBuffer':{const b=this.bindings.get(a[0]);b.shader.storage.set(b.storage.name,a[1]);break;}
    case 'draw':this.draw(false,a);break;
    case 'drawIndexed':this.draw(true,a);break;
    case 'clear':this.clear(...a);break;
    case 'blit':this.blit(...a);break;
    case 'resolve':this.resolve(...a);break;
    case 'beginCompute':this.endFramebuffer();this.computePass=this.encoderForWork().beginComputePass();for(const label of this.labels)this.computePass.pushDebugGroup(label);break;
    case 'endCompute':if(this.computePass){for(const label of this.labels)this.computePass.popDebugGroup();this.computePass.end();this.computePass=null;}break;
    case 'dispatch':{
      const pipeline=this.currentCompute;pipeline.compiled??=this.device.createComputePipeline({layout:pipeline.shader.pipelineLayout,compute:{module:pipeline.shader.modules.compute,entryPoint:'main'}});
      const shader=pipeline.shader,positions=shader.storage.get('OutputPositions'),normals=shader.storage.get('OutputNormalsTangents');
      let copies=[];
      if(shader.name==='glsl/compute_skinning' && positions===normals){
        // The original allocator packs both output arrays into one buffer.
        // WebGPU forbids writable binding aliasing even for disjoint writes.
        // Dispatch into reusable independent buffers, then copy only the exact
        // original vertex ranges back, retaining all other models' allocations.
        const target=this.get(positions);
        const uniform=shader.variant.uniforms.find(block=>block.members.some(m=>m.name==='offset'));
        const bytes=shader.uniformBlocks.get(uniform.binding),values=new Float32Array(bytes.buffer);
        const offsets=uniform.members.find(m=>m.name==='offset').offset/4;
        const count=values[uniform.members.find(m=>m.name==='vertexCount').offset/4];
        shader.skinningScratch??=new Map();
        for(const [name,index] of [['OutputPositions',2],['OutputNormalsTangents',3]]){
          const key=name+':'+target.size;let id=shader.skinningScratch.get(key);
          if(!id){id=this.put({kind:'buffer',buffer:this.device.createBuffer({label:'0ad skinning '+name,size:target.size,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC}),size:target.size});shader.skinningScratch.set(key,id);}
          const offset=values[offsets+index]*16,size=count*16;
          if(offset+size>target.size)throw new Error('Original skinning output exceeds allocation');
          shader.storage.set(name,id);copies.push({name,id,offset,size,target:positions});
        }
      }
      this.computePass.setPipeline(pipeline.compiled);this.bindShader(this.computePass,shader);this.computePass.dispatchWorkgroups(...a);
      if(copies.length){
        this.command('endCompute',[]);
        for(const copy of copies){this.encoderForWork().copyBufferToBuffer(this.get(copy.id).buffer,copy.offset,this.get(copy.target).buffer,copy.offset,copy.size);shader.storage.set(copy.name,copy.target);}
        this.command('beginCompute',[]);
      }
      break;}
    case 'pushLabel':{
      const pass=this.pass||this.computePass;if(pass)pass.pushDebugGroup(a[0]);else this.encoderForWork().insertDebugMarker(a[0]);this.labels.push(a[0]);break;}
    case 'popLabel':if(this.labels.length){const pass=this.pass||this.computePass;if(pass)pass.popDebugGroup();this.labels.pop();}break;
    default:throw new Error(`Unknown WebGPU command ${name}`);
    }
  }
  attachment(framebuffer) {
    const target=framebuffer.backbuffer?null:this.get(framebuffer.color||framebuffer.depth);
    const color=framebuffer.backbuffer?this.presentationTexture:framebuffer.color?this.get(framebuffer.color).texture:null;
    const depth=framebuffer.backbuffer?this.depthTexture:framebuffer.depth?this.get(framebuffer.depth).texture:null;
    return {color,depth,format:framebuffer.backbuffer?this.session.diagnostics.format:framebuffer.color?this.get(framebuffer.color).format:null,
      depthFormat:framebuffer.backbuffer?'depth24plus-stencil8':framebuffer.depth?this.get(framebuffer.depth).format:null,
      samples:target?.sampleCount||1};
  }
  beginFramebuffer(framebuffer,forceLoad=false,clearFlags=null) {
    if(this.pass)throw new Error('Nested framebuffer pass');this.target=framebuffer;
    const a=this.attachment(framebuffer);this.attachments=a;
    const descriptor={label:framebuffer.label,colorAttachments:[]};
    if(a.color)descriptor.colorAttachments=[{view:a.color.createView(),loadOp:clearFlags?.[0]||(!forceLoad&&framebuffer.cl===1)?'clear':'load',
      storeOp:'store',clearValue:framebuffer.clear}];
    if(a.depth){const stencil=a.depthFormat.includes('stencil');descriptor.depthStencilAttachment={view:a.depth.createView(),depthLoadOp:clearFlags?.[1]||(!forceLoad&&framebuffer.dl===1)?'clear':'load',depthStoreOp:'store',depthClearValue:1};
      if(stencil)Object.assign(descriptor.depthStencilAttachment,{stencilLoadOp:clearFlags?.[2]||(!forceLoad&&framebuffer.dl===1)?'clear':'load',stencilStoreOp:'store',stencilClearValue:0});}
    this.pass=this.encoderForWork().beginRenderPass(descriptor);for(const label of this.labels)this.pass.pushDebugGroup(label);this.applyViewport();this.applyScissor();
  }
  endFramebuffer() { if(this.pass){for(const label of this.labels)this.pass.popDebugGroup();this.pass.end();this.pass=null;} }
  applyViewport(){if(!this.pass)return;const [x,y,w,h]=this.viewportRect||[0,0,this.target.width,this.target.height];this.pass.setViewport(x,this.target.height-y-h,w,h,0,1);}
  applyScissor(){if(!this.pass)return;let [x,y,w,h]=this.scissorRect?.length?this.scissorRect:[0,0,this.target.width,this.target.height];y=this.target.height-y-h;
    const right=Math.min(this.target.width,x+w),bottom=Math.min(this.target.height,y+h);x=Math.min(this.target.width,Math.max(0,x));y=Math.min(this.target.height,Math.max(0,y));this.pass.setScissorRect(x,y,Math.max(0,right-x),Math.max(0,bottom-y));}
  clear(color,depth,stencil){const framebuffer=this.target;this.endFramebuffer();this.beginFramebuffer(framebuffer,true,[color,depth,stencil]);}
  passState(pass){
    this.passStates??=new WeakMap();
    let state=this.passStates.get(pass);
    if(!state){state={groups:new Map(),vertices:new Map()};this.passStates.set(pass,state);}
    return state;
  }
  bindGroup(pass,index,group,offsets=[]){
    const groups=this.passState(pass).groups,previous=groups.get(index);
    if(previous?.group===group && previous.offsets.length===offsets.length && offsets.every((value,i)=>value===previous.offsets[i]))return;
    pass.setBindGroup(index,group,offsets);groups.set(index,{group,offsets});
  }
  bindShader(pass,shader){
    if(shader.group0){
      const offsets=[];
      const epoch=this.uniformEpoch??0;
      for(const block of shader.variant.uniforms){
        const snapshot=shader.uniformSnapshots?.get(block.binding);
        if(snapshot?.epoch===epoch){offsets.push(snapshot.offset);continue;}
        const bytes=shader.uniformBlocks.get(block.binding);const offset=align(this.uniformCursor,this.device.limits.minUniformBufferOffsetAlignment);
        if(offset+bytes.length>this.uniformCapacity)throw new Error('Uniform arena exhausted; frame must be split safely');
        this.uniformHost.set(bytes,offset);offsets.push(offset);this.uniformCursor=offset+bytes.length;
        shader.uniformSnapshots?.set(block.binding,{epoch,offset});}
      this.bindGroup(pass,0,shader.group0,offsets);
    }else if(shader.groups.length)this.bindGroup(pass,0,shader.emptyGroup0??=this.device.createBindGroup({layout:shader.groups[0],entries:[]}));
    if(shader.variant.textures.length){
      if(!shader.lastTextureGroup){
      const key=shader.variant.textures.map(t=>shader.textures.get(t.name)||0).join(',');let group=shader.textureGroups.get(key);
      if(!group){const entries=[];for(const t of shader.variant.textures){const id=shader.textures.get(t.name);if(!id)throw new Error(`Shader ${shader.name} has no original texture binding ${t.name}`);const texture=this.get(id);entries.push({binding:t.binding,resource:texture.view},{binding:t.binding+1,resource:texture.sampler});}
        group=this.device.createBindGroup({layout:shader.groups[1],entries});shader.textureGroups.set(key,group);}
      shader.lastTextureGroup=group;
      }
      this.bindGroup(pass,1,shader.lastTextureGroup);
    }
    const storage=shader.variant.storage??[];
    if(storage.length){
      let same=Boolean(shader.lastStorageGroup);
      for(let i=0;same && i<storage.length;i++)same=shader.lastStorageIds[i]===shader.storage.get(storage[i].name);
      if(!same){
        const ids=storage.map(s=>shader.storage.get(s.name)),key=ids.join(',');
        const cache=shader.storageGroups??=new Map();let group=cache.get(key);
        if(!group){const entries=storage.map((s,i)=>({binding:s.binding,resource:s.type==='storageBuffer'?{buffer:this.get(ids[i]).buffer}:this.get(ids[i]).view}));
          group=this.device.createBindGroup({layout:shader.groups[storage[0].group],entries});cache.set(key,group);}
        shader.lastStorageIds=ids;shader.lastStorageGroup=group;
      }
      this.bindGroup(pass,storage[0].group,shader.lastStorageGroup);
    }
  }
  draw(indexed,a,offset=0) {
    if(!this.pass||!this.currentPipeline||!this.currentLayout)throw new Error('Incomplete WebGPU draw state');
    const p=this.currentPipeline,shader=p.shader,layout=this.currentLayout;
    if(shader.samplerDirty || !shader.samplerConstants){
      const findTexture=name=>{const id=shader.textures.get(name);return id?this.get(id):undefined;};
      shader.samplerConstants=Object.fromEntries(Object.entries(shader.samplerStages).map(([stage,names])=>[stage,borderConstants(names,findTexture)]));
      shader.samplerKey=JSON.stringify(shader.samplerConstants);shader.samplerDirty=false;
    }
    const samplerStages=shader.samplerConstants;
    const previous=this.lastPipelineLookup;
    let compiled=previous?.p===p && previous.layout===layout && previous.attachments===this.attachments && previous.samplerKey===shader.samplerKey?previous.compiled:null;
    if(!compiled){
    const key=JSON.stringify([this.objectsId(p),this.objectsId(layout),this.attachments.format,this.attachments.depthFormat,this.attachments.samples,shader.samplerKey]);
    compiled=this.pipelines.get(key);
    if(!compiled){
      const buffers=[];const maxSlot=Math.max(-1,...layout.attributes.map(attr=>attr[5]));
      for(let slot=0;slot<=maxSlot;slot++){
        const attributes=layout.attributes.filter(attr=>attr[5]===slot && shader.variant.inputs.some(input=>input.stream===attr[0]));
        if(!attributes.length){buffers.push(null);continue;}
        buffers.push({arrayStride:attributes[0][3],stepMode:attributes[0][4]?'instance':'vertex',attributes:attributes.map(attr=>({shaderLocation:shader.variant.inputs.find(input=>input.stream===attr[0]).location,offset:attr[2],format:vertexFormats[attr[1]]}))});
      }
      const [d,b,r]=[p.depth,p.blend,p.raster];
      if(r[0]!==0)throw new Error('WebGPU does not support polygon line mode in this pipeline');
      const descriptor={label:shader.name,layout:shader.pipelineLayout,vertex:{module:shader.modules.vertex,entryPoint:'main',buffers,constants:samplerStages.vertex},
        primitive:{topology:'triangle-list',frontFace:r[2]?'cw':'ccw',cullMode:['none','front','back'][r[1]]},multisample:{count:this.attachments.samples}};
      if(this.attachments.format){const target={format:this.attachments.format,writeMask:b[8]};
        if(b[0] && ['r32float','rg32float','rgba32float'].includes(target.format) && !this.device.features.has('float32-blendable'))throw new Error('Original float32 blending requires WebGPU float32-blendable');
        if(b[0])target.blend={color:{srcFactor:blendFactors[b[1]],dstFactor:blendFactors[b[2]],operation:blendOps[b[3]]},alpha:{srcFactor:blendFactors[b[4]],dstFactor:blendFactors[b[5]],operation:blendOps[b[6]]}};
        descriptor.fragment={module:shader.modules.fragment,entryPoint:'main',targets:[target],constants:samplerStages.fragment};}
      else if(shader.modules.fragmentDepth)
        descriptor.fragment={module:shader.modules.fragmentDepth,entryPoint:'main',targets:[],constants:samplerStages.fragmentDepth};
      if(this.attachments.depthFormat){descriptor.depthStencil={format:this.attachments.depthFormat,depthWriteEnabled:Boolean(d[2]),depthCompare:d[0]?comparisons[d[1]]:'always'};
        if(d[3]){const face=s=>({failOp:stencilOps[s[0]],passOp:stencilOps[s[1]],depthFailOp:stencilOps[s[2]],compare:comparisons[s[3]]});Object.assign(descriptor.depthStencil,{stencilReadMask:d[4],stencilWriteMask:d[5],stencilFront:face(d[7]),stencilBack:face(d[8])});}
        if(r[3])Object.assign(descriptor.depthStencil,{depthBias:Math.trunc(r[4]),depthBiasSlopeScale:r[5]});}
      compiled={pipeline:this.device.createRenderPipeline(descriptor),slots:buffers.map((b,i)=>b?i:-1).filter(i=>i>=0)};this.pipelines.set(key,compiled);this.stats.pipelineCompiles++;
    }
    this.lastPipelineLookup={p,layout,attachments:this.attachments,samplerKey:shader.samplerKey,compiled};
    }
    const state=this.passState(this.pass),blend=p.blend[7];
    if(state.pipeline!==compiled.pipeline){this.pass.setPipeline(compiled.pipeline);state.pipeline=compiled.pipeline;}
    if(!state.blend || blend.some((value,i)=>value!==state.blend[i])){this.pass.setBlendConstant(blend);state.blend=blend;}
    if(state.stencil!==p.depth[6]){this.pass.setStencilReference(p.depth[6]);state.stencil=p.depth[6];}
    for(const slot of compiled.slots){const v=this.vertices.get(slot);if(!v)throw new Error(`Missing vertex slot ${slot}`);
      const bound=state.vertices.get(slot);
      if(bound?.buffer!==v.buffer || bound.offset!==v.offset){this.pass.setVertexBuffer(slot,v.buffer.buffer,v.offset);state.vertices.set(slot,v);}}
    this.bindShader(this.pass,shader);
    if(indexed){const indexOffset=this.indexBuffer.offset||0;
      if(state.indexBuffer!==this.indexBuffer.buffer || state.indexOffset!==indexOffset){this.pass.setIndexBuffer(this.indexBuffer.buffer,'uint16',indexOffset);state.indexBuffer=this.indexBuffer.buffer;state.indexOffset=indexOffset;}
      this.pass.drawIndexed(a[offset+1],a[offset+3],a[offset],a[offset+4]|0,a[offset+2]);}
    else this.pass.draw(a[offset+1],a[offset+3],a[offset],a[offset+2]);
    this.stats.draws++;
  }
  validateCommandDataRange(data,offset,size){
    if(!(data instanceof Uint8Array) || !Number.isSafeInteger(offset) || !Number.isSafeInteger(size) || offset<0 || size<0 || offset>data.byteLength || size>data.byteLength-offset)
      throw new Error('Invalid binary command range');
    return data.byteOffset+offset;
  }
  commandDataRange(data,offset,size){
    this.validateCommandDataRange(data,offset,size);
    return data.subarray(offset,offset+size);
  }
  objectsId(object){if(!object.identity)object.identity=this.nextId++;return object.identity;}
  uploadBufferRange(id,offset,bytes){
    const target=this.get(id);
    const capacity=align(target.size,4);
    if(!Number.isSafeInteger(offset) || offset<0 || offset%4 || bytes.length%4 || offset>capacity || bytes.length>capacity-offset)throw new Error('Invalid aligned buffer upload range');
    const previous=this.pass?this.target:null;this.endFramebuffer();
    const staged=this.uploadTransient('upload',bytes);
    this.encoderForWork().copyBufferToBuffer(staged.buffer.buffer,staged.offset,target.buffer,offset,bytes.length);
    if(previous)this.beginFramebuffer(previous,true);
  }
  uploadTransient(kind,values){
    const sizeBytes=align(values.length,4);
    const arenas=this.transientArenas[kind]??=[];let arena=arenas.find(a=>a.size-a.cursor>=sizeBytes);
    if(!arena){const size=Math.max(1024*1024,align(sizeBytes,1024*1024));arena={buffer:this.device.createBuffer({label:`0ad transient ${kind} arena`,size,usage:GPUBufferUsage.COPY_DST|(kind==='vertex'?GPUBufferUsage.VERTEX:kind==='index'?GPUBufferUsage.INDEX:GPUBufferUsage.COPY_SRC)}),bytes:new Uint8Array(size),size,cursor:0};arenas.push(arena);}
    const offset=arena.cursor;arena.cursor+=sizeBytes;
    arena.bytes.set(values,offset);arena.bytes.fill(0,offset+values.length,arena.cursor);this.stats.uploadBytes+=sizeBytes;
    return {buffer:arena,offset};
  }
  blit(sourceId,destId,sr,dr,filter){
    const s=this.get(sourceId),d=this.get(destId);
    if(this.pass)throw new Error('Blit inside framebuffer pass');const sa=this.attachment(s),da=this.attachment(d);
    // Renderer adaptation of GL's color blit: sample the same rectangular
    // source with the requested nearest/linear filter, including format change.
    this.blitModule??=this.device.createShaderModule({label:'0ad framebuffer blit',code:`
      struct Bounds { origin: vec2f, extent: vec2f }
      @group(0) @binding(0) var image: texture_2d<f32>;
      @group(0) @binding(1) var imageSampler: sampler;
      @group(0) @binding(2) var<uniform> bounds: Bounds;
      struct Vertex { @builtin(position) position: vec4f, @location(0) uv: vec2f }
      @vertex fn vertexMain(@builtin(vertex_index) index: u32) -> Vertex {
        let points = array<vec2f,3>(vec2f(0,0),vec2f(2,0),vec2f(0,2));
        let p = points[index]; var result: Vertex;
        result.position = vec4f(p.x*2-1,1-p.y*2,0,1);
        result.uv = bounds.origin+p*bounds.extent; return result;
      }
      @fragment fn fragmentMain(v: Vertex) -> @location(0) vec4f {
        return textureSampleLevel(image,imageSampler,v.uv,0);
      }`});
    this.blitPipelines??=new Map();let pipeline=this.blitPipelines.get(da.format);
    if(!pipeline){pipeline=this.device.createRenderPipeline({layout:'auto',vertex:{module:this.blitModule,entryPoint:'vertexMain'},fragment:{module:this.blitModule,entryPoint:'fragmentMain',targets:[{format:da.format}]},primitive:{topology:'triangle-list'}});this.blitPipelines.set(da.format,pipeline);}
    const uniform=this.device.createBuffer({size:16,usage:GPUBufferUsage.UNIFORM,mappedAtCreation:true});
    new Float32Array(uniform.getMappedRange()).set([sr[0]/s.width,1-(sr[1]+sr[3])/s.height,sr[2]/s.width,sr[3]/s.height]);uniform.unmap();
    const sampler=this.device.createSampler({magFilter:filter?'linear':'nearest',minFilter:filter?'linear':'nearest'});
    const group=this.device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:sa.color.createView()},{binding:1,resource:sampler},{binding:2,resource:{buffer:uniform}}]});
    const pass=this.encoderForWork().beginRenderPass({colorAttachments:[{view:da.color.createView(),loadOp:'load',storeOp:'store'}]});
    pass.setPipeline(pipeline);pass.setBindGroup(0,group);pass.setViewport(dr[0],d.height-dr[1]-dr[3],dr[2],dr[3],0,1);pass.draw(3);pass.end();this.retired.add(this.put({buffer:uniform}));
  }
  resolve(sourceId,destId){
    const s=this.attachment(this.get(sourceId)),d=this.attachment(this.get(destId));if(this.pass)throw new Error('Resolve inside render pass');
    const pass=this.encoderForWork().beginRenderPass({colorAttachments:[{view:s.color.createView(),resolveTarget:d.color.createView(),loadOp:'load',storeOp:'store'}]});pass.end();
  }
  submit(){
    if(this.pass||this.computePass)throw new Error('Cannot submit an open WebGPU pass');
    if(this.encoder){
      // Each draw owns an immutable range until submission. Upload the full
      // arenas once before their command buffer, preserving both queue order
      // across frames and distinct uniform values within the current frame.
      const upload=(buffer,bytes)=>this.uploadBelt?this.uploadBelt.stage(buffer,bytes):this.device.queue.writeBuffer(buffer,0,bytes);
      if(this.uniformCursor)upload(this.uniformBuffer,this.uniformHost.subarray(0,this.uniformCursor));
      for(const arenas of Object.values(this.transientArenas))for(const arena of arenas)
        if(arena.cursor)upload(arena.buffer,arena.bytes.subarray(0,arena.cursor));
      const uploads=this.uploadBelt?.beforeFrame();
      this.device.queue.submit(uploads?[uploads,this.encoder.finish()]:[this.encoder.finish()]);
      this.uploadBelt?.afterSubmit();this.encoder=null;this.stats.submissions++;
    }
    this.uniformCursor=0;
    this.uniformEpoch=(this.uniformEpoch??0)+1;
    for(const arenas of Object.values(this.transientArenas))for(const arena of arenas)arena.cursor=0;
    const retired=[...this.retired];this.retired.clear();
    if(retired.length){const release=()=>{
      for(const id of retired){
        const object=this.objects.get(id);if(!object)continue;
        object.buffer?.destroy();if(object.kind==='texture')object.texture.destroy();
        if(object.kind==='texture')for(const shader of this.objects.values())if(shader.kind==='shader'){
          for(const key of shader.textureGroups.keys())if(key.split(',').some(value=>Number(value)===id))shader.textureGroups.delete(key);
          shader.lastTextureGroup=null;
        }
        if(object.kind==='texture' || object.kind==='buffer')for(const shader of this.objects.values())if(shader.kind==='shader'){
          for(const key of shader.storageGroups?.keys()??[])if(key.split(',').some(value=>Number(value)===id))shader.storageGroups.delete(key);
          shader.lastStorageGroup=null;shader.lastStorageIds=null;
        }
        if(object.kind==='shader')for(const slot of object.bindingSlots.values())this.bindings.delete(slot);
        if(object.identity)for(const key of this.pipelines.keys())if(JSON.parse(key).slice(0,2).includes(object.identity))this.pipelines.delete(key);
        this.objects.delete(id);
      }
    };this.device.queue.onSubmittedWorkDone().then(release,release);}
    this.report({type:'engine-frame',...this.stats,objects:this.objects.size});
  }
  readback([x,y,width,height,destination,signal]) {
    this.submit();const texture=this.presentationTexture;const pitch=align(width*4,256);
    const buffer=this.device.createBuffer({size:pitch*height,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
    const encoder=this.device.createCommandEncoder();encoder.copyTextureToBuffer({texture,origin:[x,this.height-y-height,0]},{buffer,bytesPerRow:pitch},[width,height,1]);this.device.queue.submit([encoder.finish()]);
    buffer.mapAsync(GPUMapMode.READ).then(()=>{const bytes=new Uint8Array(buffer.getMappedRange());const heap=this.heap();for(let row=0;row<height;row++)for(let col=0;col<width;col++)for(let c=0;c<3;c++)heap[destination+((height-1-row)*width+col)*3+c]=bytes[row*pitch+col*4+(this.session.diagnostics.format.startsWith('bgra')?2-c:c)];buffer.unmap();buffer.destroy();this.signal(signal);},error=>{buffer.destroy();this.report({type:'readback-error',message:error.message});this.signal(signal,false);});
  }
  async dispose(){
    if(this.disposed)return;this.disposed=true;
    this.commandDispatcher?.dispose();
    this.publishLiveState(false);this.liveAddress=0;
    try{if(this.live){this.submit();await this.device.queue.onSubmittedWorkDone();}}
    catch(error){this.report({type:'engine-drain-error',message:error.message});}
    finally{
      for(const object of this.objects.values()){object.buffer?.destroy();if(object.kind==='texture')object.texture.destroy();}
      this.objects.clear();this.bindings.clear();this.pipelines.clear();
      this.blitPipelines?.clear();this.blitModule=null;
      this.lastPipelineLookup=null;this.passStates=null;
      this.uploadBelt?.dispose();
      for(const arenas of Object.values(this.transientArenas))for(const arena of arenas)arena.buffer.destroy();
      this.uniformBuffer.destroy();this.depthTexture?.destroy();this.presentationTexture?.destroy();
      this.uniformHost=null;
      await this.session.dispose();
    }
  }
}
