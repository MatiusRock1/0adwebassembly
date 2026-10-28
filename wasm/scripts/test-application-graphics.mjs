import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyGPU,gpuDisplayName,selectGraphicsProfile,graphicsConfig,readWebGLRenderer,detectOS,gpuGuide,LOW_GRAPHICS_SETTINGS}
  from '../browser/application-graphics.mjs';

const angle=(vendor,name)=>`ANGLE (${vendor}, ${name} Direct3D11 vs_5_0 ps_5_0, D3D11)`;
// Strings reported by Chrome on the test laptop (docs/wasm/evidence) and typical others.
const AMD_APU=angle('AMD','AMD Radeon(TM) Graphics (0x00001638)');
const RTX_3060=angle('NVIDIA','NVIDIA GeForce RTX 3060 Laptop GPU (0x00002520)');

test('the test laptop: integrated Radeon is weak, RTX 3060 is not',()=>{
  const amd=classifyGPU({renderer:AMD_APU});
  assert.deepEqual([amd.category,amd.weak,amd.name],['integrated',true,'AMD Radeon(TM) Graphics']);
  const nvidia=classifyGPU({renderer:RTX_3060});
  assert.deepEqual([nvidia.category,nvidia.weak,nvidia.name],['capable',false,'NVIDIA GeForce RTX 3060 Laptop GPU']);
});

test('renderer strings by category',()=>{
  const expected={
    software:['ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)',
      angle('Microsoft','Microsoft Basic Render Driver'),'ANGLE (Mesa, llvmpipe (LLVM 15.0.7, 256 bits), OpenGL 4.5)'],
    integrated:[angle('Intel','Intel(R) UHD Graphics 620 (0x00003EA0)'),angle('Intel','Intel(R) Iris(R) Xe Graphics (0x00009A49)'),
      angle('Intel','Intel(R) Arc(TM) Graphics (0x00007D55)'),angle('Intel','Intel(R) Arc(TM) 140V GPU (16GB) (0x000064A0)'),
      angle('AMD','AMD Radeon(TM) Vega 8 Graphics (0x000015DD)'),angle('AMD','AMD Radeon(TM) RX Vega 10 Graphics (0x000015D8)'),
      angle('AMD','AMD Radeon(TM) R7 Graphics (0x00009874)'),angle('AMD','AMD Radeon 780M Graphics (0x000015BF)'),
      angle('AMD','AMD Radeon(TM) 610M (0x0000164E)'),'ANGLE (AMD, AMD Radeon Graphics (renoir, LLVM 15.0.7, DRM 3.49, 6.1.0), OpenGL 4.6)',
      'ANGLE (Intel, Mesa Intel(R) UHD Graphics 620 (KBL GT2), OpenGL 4.6)','ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)',
      angle('Qualcomm','Qualcomm(R) Adreno(TM) X1-85 GPU (0x0000370A)')],
    entry:[angle('NVIDIA','NVIDIA GeForce MX450 (0x00001F9D)'),angle('NVIDIA','NVIDIA GeForce GT 1030 (0x00001D01)'),
      angle('NVIDIA','NVIDIA GeForce 940MX (0x0000134D)'),angle('NVIDIA','NVIDIA GeForce GTX 1050 Ti (0x00001C8C)'),
      angle('NVIDIA','NVIDIA GeForce GTX 960M (0x0000139B)'),angle('NVIDIA','NVIDIA GeForce RTX 2050 (0x000025AD)'),
      angle('NVIDIA','NVIDIA RTX A500 Laptop GPU (0x000025BB)'),angle('NVIDIA','NVIDIA T500 (0x00001FB9)'),
      angle('NVIDIA','NVIDIA Quadro P620 (0x00001CB6)'),'ANGLE (NVIDIA Corporation, NVIDIA GeForce GTX 1050/PCIe/SSE2, OpenGL 4.5.0 NVIDIA 470.86)',
      angle('AMD','AMD Radeon(TM) 530 (0x00006660)'),angle('AMD','Radeon RX 550 Series (0x0000699F)'),angle('AMD','AMD Radeon RX 560X (0x000067EF)'),
      angle('AMD','AMD Radeon R7 M260 (0x00006900)'),angle('Intel','Intel(R) Arc(TM) A380 Graphics (0x000056A5)')],
    capable:[RTX_3060,angle('NVIDIA','NVIDIA GeForce GTX 1060 6GB (0x00001C03)'),angle('NVIDIA','NVIDIA GeForce GTX 1650 (0x00001F82)'),
      angle('NVIDIA','NVIDIA GeForce GTX 970 (0x000013C2)'),angle('NVIDIA','NVIDIA T1000 (0x00001FB0)'),
      angle('NVIDIA','NVIDIA Quadro P2000 (0x00001C30)'),angle('AMD','AMD Radeon RX 6600 (0x000073FF)'),
      angle('AMD','Radeon (TM) RX 470 Graphics (0x000067DF)'),angle('AMD','AMD Radeon RX 5500 XT (0x00007340)'),
      angle('AMD','AMD Radeon(TM) 8060S Graphics (0x00001586)'),angle('Intel','Intel(R) Arc(TM) A770 Graphics (0x000056A0)'),
      angle('Intel','Intel(R) Arc(TM) B580 Graphics (0x0000E20B)'),'ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)'],
    unknown:['WebKit WebGL','']
  };
  for(const [category,renderers] of Object.entries(expected))
    for(const renderer of renderers)assert.equal(classifyGPU({renderer}).category,category,renderer);
  assert.equal(classifyGPU().category,'unknown');
});

test('WebGPU uses the WebGL name only for the same vendor',()=>{
  const same=classifyGPU({renderer:AMD_APU,adapter:{vendor:'amd',architecture:'gcn-5'}});
  assert.deepEqual([same.category,same.source,same.name],['integrated','webgl-renderer','AMD Radeon(TM) Graphics']);
  // WebGL on the integrated GPU, WebGPU on another adapter: nothing is known about it.
  const other=classifyGPU({renderer:AMD_APU,adapter:{vendor:'nvidia',architecture:'ampere'}});
  assert.deepEqual([other.category,other.weak,other.source,other.name,other.renderer],['unknown',false,'webgpu-adapter','nvidia ampere',null]);
  assert.equal(classifyGPU({adapter:{vendor:'intel',architecture:'gen-12lp'}}).category,'integrated');
  assert.equal(classifyGPU({adapter:{vendor:'amd',architecture:'gcn-5'}}).category,'unknown');
  assert.equal(classifyGPU({renderer:RTX_3060,adapter:{vendor:'nvidia',architecture:'ampere'},fallbackAdapter:true}).category,'software');
  assert.equal(classifyGPU({adapter:{vendor:'google',architecture:'swiftshader'}}).category,'software');
});

test('display names drop the ANGLE backend details',()=>{
  assert.equal(gpuDisplayName(AMD_APU),'AMD Radeon(TM) Graphics');
  assert.equal(gpuDisplayName('ANGLE (Intel, Mesa Intel(R) UHD Graphics 620 (KBL GT2), OpenGL 4.6)'),'Mesa Intel(R) UHD Graphics 620 (KBL GT2)');
  assert.equal(gpuDisplayName('ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)'),'Apple M1');
  assert.equal(gpuDisplayName(null),null);
});

test('only automatic mode follows the GPU',()=>{
  const weak=classifyGPU({renderer:AMD_APU}),strong=classifyGPU({renderer:RTX_3060}),unknown=classifyGPU();
  assert.deepEqual(['auto','low','original'].map(mode=>selectGraphicsProfile(mode,weak)),['low','low','original']);
  assert.deepEqual(['auto','low','original'].map(mode=>selectGraphicsProfile(mode,strong)),['original','low','original']);
  assert.equal(selectGraphicsProfile('auto',unknown),'original');
});

test('the guide opens the steps of the player\'s operating system',()=>{
  const os=(platform,userAgent='')=>detectOS({navigator:{platform,userAgent}});
  assert.equal(detectOS({navigator:{userAgentData:{platform:'Windows'}}}),'windows');
  assert.equal(os('Win32','Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),'windows');
  assert.equal(os('MacIntel','Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'),'macos');
  assert.equal(os('Linux x86_64','Mozilla/5.0 (X11; Linux x86_64)'),'linux');
  assert.equal(os('Linux armv81','Mozilla/5.0 (Linux; Android 14; Pixel 8)'),'other');
  assert.equal(os('Linux x86_64','Mozilla/5.0 (X11; CrOS x86_64 14541.0.0)'),'other');
  assert.equal(os('iPhone','Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)'),'other');
  assert.equal(detectOS({}),'other');
});

test('the guide: the integrated GPU of a computer, or software rendering',()=>{
  const amd=classifyGPU({renderer:AMD_APU});
  assert.deepEqual(['windows','macos','linux','other'].map(os=>gpuGuide(amd,os)),['dedicated','dedicated','dedicated',null]);
  assert.equal(gpuGuide(classifyGPU({renderer:RTX_3060}),'windows'),null);
  // An entry-level GPU is already the dedicated one.
  assert.equal(gpuGuide(classifyGPU({renderer:angle('NVIDIA','NVIDIA GeForce MX450 (0x00001F9D)')}),'windows'),null);
  // The only GPU of the device.
  assert.equal(gpuGuide(classifyGPU({renderer:'ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)'}),'macos'),null);
  assert.equal(gpuGuide(classifyGPU({renderer:angle('Qualcomm','Qualcomm(R) Adreno(TM) X1-85 GPU (0x0000370A)')}),'windows'),null);
  assert.equal(gpuGuide(classifyGPU({adapter:{vendor:'intel',architecture:'gen-12lp'}}),'linux'),'dedicated');
  assert.equal(gpuGuide(classifyGPU({renderer:angle('Microsoft','Microsoft Basic Render Driver')}),'other'),'acceleration');
  assert.equal(gpuGuide(classifyGPU(),'windows'),null);
});

test('local.cfg holds the low option of each setting in config syntax',()=>{
  const text=graphicsConfig(LOW_GRAPHICS_SETTINGS);
  for(const line of ['textures.quality = 0','shadowquality = -1','shadowpcf = false','waterreflection = false',
    'postproc = false','antialiasing = "disabled"','max_actor_quality = 100','materialmgr.quality = 0'])
    assert.ok(text.split('\n').includes(line),line);
  assert.ok(!/^\s*shadows\s*=/m.test(text),'shadows stay enabled at low quality');
  assert.ok(text.endsWith('\n'));
});

test('the WebGL probe reads the unmasked renderer and releases its context',()=>{
  const calls=[];
  const gl={getExtension(name){calls.push(name);
      return name==='WEBGL_debug_renderer_info'?{UNMASKED_RENDERER_WEBGL:0x9246}:{loseContext(){calls.push('lost');}};},
    getParameter(name){return name===0x9246?AMD_APU:null;}};
  const environment={document:{createElement:()=>({getContext:(kind,options)=>{calls.push([kind,options]);return gl;}})}};
  assert.equal(readWebGLRenderer('high-performance',environment),AMD_APU);
  assert.deepEqual(calls,[['webgl2',{powerPreference:'high-performance'}],'WEBGL_debug_renderer_info','WEBGL_lose_context','lost']);
  assert.equal(readWebGLRenderer('default',{document:{createElement:()=>({getContext:()=>null})}}),null);
  assert.equal(readWebGLRenderer('default',{}),null);
});
