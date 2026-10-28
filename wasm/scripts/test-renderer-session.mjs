import test from 'node:test';
import assert from 'node:assert/strict';
import { openRendererSession } from '../browser/renderer-session.mjs';

function fixture() {
  const calls = [];
  let lose;
  const limits = Object.create({ maxTextureDimension2D: 8192 });
  const device = { features: new Set(), limits,
    lost: new Promise(resolve => { lose = resolve; }),
    addEventListener() {}, removeEventListener() {},
    queue: { async onSubmittedWorkDone() { calls.push('drain'); } },
    destroy() { calls.push('destroy'); },
    pushErrorScope() { calls.push('push'); },
    async popErrorScope() { calls.push('pop'); return device.validationError; }
  };
  const adapter = { info: { vendor: 'test' }, features: new Set(), limits,
    async requestDevice(options) { calls.push(['device', options]); return device; } };
  const context = { configure() { calls.push('configure'); }, unconfigure() { calls.push('unconfigure'); } };
  const canvas = { getContext(kind) { calls.push(kind); return context; } };
  const environment = { isSecureContext: true, crossOriginIsolated: true, SharedArrayBuffer,
    navigator: { gpu: { async requestAdapter(options) { calls.push(['adapter', options]); return adapter; },
      getPreferredCanvasFormat() { return 'bgra8unorm'; } } } };
  const reports = [];
  return { canvas, environment, device, calls, lose, reports,
    options: { canvas, environment, backend: 'webgpu', report: value => reports.push(value) } };
}

test('WebGPU owns its canvas, records prototype limits and drains before destruction', async () => {
  const f = fixture();
  const session = await openRendererSession({ ...f.options, powerPreference: 'high-performance' });
  assert.deepEqual(f.calls[0], ['adapter', { powerPreference: 'high-performance' }]);
  assert.equal(session.diagnostics.deviceLimits.maxTextureDimension2D, 8192);
  assert.equal(f.calls.includes('webgl2'), false);
  await session.dispose();
  await session.dispose();
  assert.deepEqual(f.calls.slice(-3), ['drain', 'unconfigure', 'destroy']);
  assert.equal(f.calls.filter(call => call === 'destroy').length, 1);
});

test('missing API, isolation or required feature never fall back to GL', async () => {
  for (const failure of ['api', 'isolation', 'feature']) {
    const f = fixture();
    if (failure === 'api') delete f.environment.navigator.gpu;
    if (failure === 'isolation') f.environment.crossOriginIsolated = false;
    await assert.rejects(openRendererSession({ ...f.options,
      requiredFeatures: failure === 'feature' ? ['texture-compression-bc'] : [] }));
    assert.equal(f.calls.some(call => typeof call === 'string'), false);
  }
});

test('canvas configuration failure destroys the requested device', async () => {
  const f = fixture();
  f.canvas.getContext = () => ({ configure() { throw new Error('configure failed'); },
    unconfigure() { f.calls.push('unconfigure'); } });
  await assert.rejects(openRendererSession(f.options), /configure failed/);
  assert.deepEqual(f.calls.slice(-2), ['unconfigure', 'destroy']);
});

test('validation scopes unwind on thrown work and surface validation errors', async () => {
  const f = fixture();
  const session = await openRendererSession(f.options);
  await assert.rejects(session.validationScope(() => { throw new Error('submission failed'); }), /submission failed/);
  assert.deepEqual(f.calls.slice(-2), ['push', 'pop']);
  f.device.validationError = { message: 'invalid binding' };
  await assert.rejects(session.validationScope(() => {}), /invalid binding/);
  assert.equal(f.reports.at(-1).type, 'validation-error');
  await session.dispose();
});

test('device loss is reported and prevents further work', async () => {
  const f = fixture();
  const session = await openRendererSession(f.options);
  f.lose({ reason: 'unknown', message: 'test loss' });
  await Promise.resolve();
  assert.equal(f.reports.at(-1).expected, false);
  await assert.rejects(session.validationScope(() => {}), /dispositivo/);
  await session.dispose();
  assert.equal(f.calls.includes('drain'), false);
});

test('rejected queue completion still releases the device and canvas', async () => {
  const f = fixture();
  const session = await openRendererSession(f.options);
  f.device.queue.onSubmittedWorkDone = async () => { throw new Error('queue lost'); };
  await assert.rejects(session.dispose(), /queue lost/);
  assert.deepEqual(f.calls.slice(-2), ['unconfigure', 'destroy']);
});

test('WebGL selection creates only GL and reports the effective renderer', async () => {
  const f = fixture();
  const requests = [];
  f.canvas.getContext = kind => {
    requests.push(kind);
    return { VERSION: 1, getExtension: () => ({ UNMASKED_RENDERER_WEBGL: 2 }),
      getParameter: name => name === 1 ? 'WebGL 2.0' : 'reported GPU' };
  };
  const session = await openRendererSession({ ...f.options, backend: 'webgl' });
  assert.deepEqual(requests, ['webgl2']);
  assert.equal(session.diagnostics.renderer, 'reported GPU');
  assert.deepEqual(f.calls, []);
});

test('optional capabilities are requested only when available and absence is recorded',async()=>{
  const f=fixture();
  const adapter=await f.environment.navigator.gpu.requestAdapter({});
  f.calls.length=0;adapter.features.add('float32-filterable');
  const session=await openRendererSession({...f.options,optionalFeatures:['float32-filterable','timestamp-query']});
  assert.deepEqual(f.calls.find(c=>Array.isArray(c)&&c[0]==='device')[1].requiredFeatures,['float32-filterable']);
  assert.deepEqual(session.diagnostics.unavailableOptionalFeatures,['timestamp-query']);
  await session.dispose();
});
