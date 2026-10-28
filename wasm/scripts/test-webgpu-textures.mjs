import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeBC } from '../browser/webgpu-engine.mjs';

test('1x1 BC1 original texture retains its logical texel and dimensions',()=>{
  const block=new Uint8Array([0,248,224,7,0,0,0,0]);
  assert.deepEqual([...decodeBC(block,1,1,32)],[255,0,0,255]);
});
test('BC1 interpolation and cropped block rows preserve palette order',()=>{
  const block=new Uint8Array([0,248,224,7,0b11100100,0,0,0]);
  assert.deepEqual([...decodeBC(block,3,1,32)],[255,0,0,255,0,255,0,255,170,85,0,255]);
});
test('BC1 RGB and RGBA differ only in the transparent palette entry',()=>{
  const block=new Uint8Array([0,0,255,255,3,0,0,0]);
  assert.deepEqual([...decodeBC(block,1,1,32)],[0,0,0,255]);
  assert.deepEqual([...decodeBC(block,1,1,34)],[0,0,0,0]);
});
test('BC2 explicit alpha and BC3 endpoint/interpolated alpha are retained',()=>{
  const block=new Uint8Array(16);block[0]=0x08;block[8]=0;block[9]=248;block[10]=224;block[11]=7;
  assert.deepEqual([...decodeBC(block,1,1,36)],[255,0,0,136]);
  block[0]=255;block[1]=0;block[2]=2;
  assert.deepEqual([...decodeBC(block,1,1,38)],[255,0,0,219]);
  block[0]=0;block[1]=255;block[2]=6;
  assert.equal(decodeBC(block,1,1,38)[3],0);
  block[2]=7;assert.equal(decodeBC(block,1,1,38)[3],255);
});
test('truncated compressed resource data fails explicitly',()=>{
  assert.throws(()=>decodeBC(new Uint8Array(7),1,1,32),/Truncated/);
});
