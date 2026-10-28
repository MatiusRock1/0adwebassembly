import test from 'node:test';
import assert from 'node:assert/strict';
import { WebGPUEngine } from '../browser/webgpu-engine.mjs';

test('draw state cache omits redundant setters but applies changed buffers and new passes',()=>{
  function pass(){const calls=[];return {calls,...Object.fromEntries(['setPipeline','setBlendConstant','setStencilReference','setVertexBuffer','setIndexBuffer','drawIndexed'].map(name=>[name,(...args)=>calls.push({name,args})]))};}
  const shader={samplerConstants:{},samplerKey:'{}',samplerDirty:false,variant:{uniforms:[],textures:[]},groups:[]};
  const p={identity:42,shader,blend:[0,0,0,0,0,0,0,[0,0,0,0]],depth:[0,0,0,0,0,0,3]};
  const layout={identity:43},compiled={pipeline:{},slots:[0]},vertex={buffer:{buffer:{}},offset:0};
  const first=pass();
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    pass:first,currentPipeline:p,currentLayout:layout,attachments:{format:'rgba8unorm',depthFormat:null,samples:1},
    pipelines:new Map([[JSON.stringify([42,43,'rgba8unorm',null,1,'{}']),compiled]]),
    vertices:new Map([[0,vertex]]),indexBuffer:{buffer:{},offset:0},stats:{draws:0}
  });
  engine.draw(true,[0,3,0,1,0]);engine.draw(true,[3,3,0,1,0]);
  for(const name of ['setPipeline','setBlendConstant','setStencilReference','setVertexBuffer','setIndexBuffer'])
    assert.equal(first.calls.filter(call=>call.name===name).length,1,name);
  assert.equal(first.calls.filter(call=>call.name==='drawIndexed').length,2);
  engine.vertices.set(0,{...vertex,offset:16});engine.indexBuffer={...engine.indexBuffer,offset:32};
  p.blend[7]=[1,0,0,0];p.depth[6]=4;engine.draw(true,[0,6,0,1,-1]);
  for(const name of ['setBlendConstant','setStencilReference','setVertexBuffer','setIndexBuffer'])
    assert.equal(first.calls.filter(call=>call.name===name).length,2,name);
  assert.deepEqual(first.calls.at(-1).args,[6,1,0,-1,0]);
  engine.pass=pass();engine.draw(true,[0,3,0,1,0]);
  for(const name of ['setPipeline','setBlendConstant','setStencilReference','setVertexBuffer','setIndexBuffer'])
    assert.equal(engine.pass.calls.filter(call=>call.name===name).length,1,'new pass '+name);
  assert.equal(engine.stats.draws,4);
  const words=new Uint32Array([9,3,6,2,4,0xffffffff]);
  engine.command('binaryCommands',[0,words.length],new Uint8Array(words.buffer));
  assert.deepEqual(engine.pass.calls.at(-1).args,[6,4,3,-1,2],'binary draw decodes signed base vertex from its original stream offset');
});

test('texture and storage groups reuse exact resource tuples across draws and scratch changes',()=>{
  const created=[],bound=[];
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    device:{createBindGroup(descriptor){const group={descriptor};created.push(group);return group;}},
    objects:new Map([[1,{view:'v1',sampler:'s1',buffer:'b1'}],[2,{view:'v2',sampler:'s2',buffer:'b2'}],[3,{buffer:'b3'}]]),
    bindings:new Map(),
  });
  const shader={groups:[{},'textures','storage'],variant:{uniforms:[],textures:[{name:'tex',binding:0}],storage:[{name:'out',binding:0,group:2,type:'storageBuffer'}]},
    textures:new Map(),storage:new Map([['out',1]]),textureGroups:new Map()};
  engine.bindings.set(7,{shader,texture:{name:'tex'}});
  const pass={setBindGroup:(...args)=>bound.push(args)};
  engine.setTexture(7,1);engine.bindShader(pass,shader);engine.bindShader(pass,shader);
  assert.equal(created.length,3,'empty group plus texture and storage groups');
  assert.equal(bound.length,3,'unchanged groups are not rebound');
  engine.setTexture(7,2);shader.storage.set('out',3);engine.bindShader(pass,shader);
  assert.equal(created.length,5);
  engine.setTexture(7,1);shader.storage.set('out',1);engine.bindShader(pass,shader);
  assert.equal(created.length,5,'earlier exact tuples are reused');
  assert.equal(bound.at(-1)[1],created[2]);
});

test('bind group reuse is scoped to a pass and includes every dynamic offset',()=>{
  const engine=Object.create(WebGPUEngine.prototype),calls=[],group={};
  const a={setBindGroup:(...args)=>calls.push(['a',...args])},b={setBindGroup:(...args)=>calls.push(['b',...args])};
  engine.bindGroup(a,0,group,[0,256]);engine.bindGroup(a,0,group,[0,256]);
  engine.bindGroup(a,0,group,[256,256]);engine.bindGroup(b,0,group,[256,256]);
  assert.equal(calls.length,3);
  // Typed overload: (index, group, offsets, start, length).
  assert.deepEqual(calls.map(row=>[row[0],Array.from(row[3]).slice(row[4],row[4]+row[5])]),[['a',[0,256]],['a',[256,256]],['b',[256,256]]]);
});

test('reused dynamic offset storage never aliases the cached pass state',()=>{
  const engine=Object.create(WebGPUEngine.prototype),calls=[],group={};
  const pass={setBindGroup:(...args)=>calls.push(Array.from(args[2]??[]).slice(args[3],args[3]+args[4]))};
  const offsets=new Uint32Array(2);
  offsets.set([0,256]);engine.bindGroup(pass,0,group,offsets,2);
  offsets.set([512,256]);engine.bindGroup(pass,0,group,offsets,2);
  offsets.set([512,256]);engine.bindGroup(pass,0,group,offsets,2);
  assert.deepEqual(calls,[[0,256],[512,256]]);
});

test('pipeline lookup cache keeps distinct render targets and sampler keys apart',()=>{
  function pass(){const calls=[];return {calls,...Object.fromEntries(['setPipeline','setBlendConstant','setStencilReference','setVertexBuffer','drawIndexed','draw'].map(name=>[name,(...args)=>calls.push({name,args})]))};}
  const shader={samplerConstants:{},samplerKey:'{}',samplerDirty:false,variant:{uniforms:[],textures:[]},groups:[]};
  const p={identity:42,shader,blend:[0,0,0,0,0,0,0,[0,0,0,0]],depth:[0,0,0,0,0,0,3]};
  const layout={identity:43},vertex={buffer:{buffer:{}},offset:0};
  const color={pipeline:{name:'color'},slots:[0]},depth={pipeline:{name:'depth'},slots:[0]};
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{
    pass:pass(),currentPipeline:p,currentLayout:layout,attachments:{format:'rgba8unorm',depthFormat:null,samples:1},
    pipelines:new Map([[JSON.stringify([42,43,'rgba8unorm',null,1,'{}']),color],[JSON.stringify([42,43,null,'depth24plus',1,'{}']),depth]]),
    vertices:new Map([[0,vertex]]),stats:{draws:0}
  });
  engine.draw(false,[0,3,0,1]);
  engine.attachments={format:null,depthFormat:'depth24plus',samples:1};engine.draw(false,[0,3,0,1]);
  engine.attachments={format:'rgba8unorm',depthFormat:null,samples:1};engine.draw(false,[0,3,0,1]);
  assert.deepEqual(engine.pass.calls.filter(c=>c.name==='setPipeline').map(c=>c.args[0].name),['color','depth','color']);
});
