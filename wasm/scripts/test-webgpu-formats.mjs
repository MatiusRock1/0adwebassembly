import test from 'node:test';
import assert from 'node:assert/strict';
import { WebGPUEngine } from '../browser/webgpu-engine.mjs';

test('optional sampled/renderable formats follow enabled device features',()=>{
  const engine=Object.assign(Object.create(WebGPUEngine.prototype),{device:{features:new Set()}});
  for(const format of [22,23,25])assert.equal(engine.call('formatSupported',[format]),0);
  assert.equal(engine.call('attachmentSupported',[26]),0);
  assert.equal(engine.call('formatSupported',[31]),0);
  assert.equal(engine.call('formatSupported',[32]),0);
  engine.device.features=new Set(['float32-filterable','rg11b10ufloat-renderable','depth32float-stencil8','texture-compression-bc']);
  for(const format of [22,23,25,31,32])assert.equal(engine.call('formatSupported',[format]),1);
  assert.equal(engine.call('attachmentSupported',[26]),1);
  assert.equal(engine.call('attachmentSupported',[32]),0,'Compressed textures are never render targets');
  assert.equal(engine.call('formatSupported',[12]),0,'Norm16 must not be advertised without implementation');
});
