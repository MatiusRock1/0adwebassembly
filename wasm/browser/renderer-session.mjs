// Browser-side ownership and diagnostics. This is not an engine backend.
export function describeLimits(limits) {
  const result = {};
  // WebIDL attributes normally live on the prototype, not as own properties.
  for (const name in limits) {
    if (typeof limits[name] === 'number') result[name] = limits[name];
  }
  return result;
}

export async function openRendererSession({ canvas, backend, powerPreference = 'default',
  environment = globalThis, report = () => {}, requiredFeatures = [], optionalFeatures = [], requiredLimits = {}, owner = 'main-thread' }) {
  if (!['webgl', 'webgpu'].includes(backend)) throw new Error(`Backend desconocido: ${backend}.`);
  if (!['default', 'high-performance', 'low-power'].includes(powerPreference))
    throw new Error(`Preferencia de GPU desconocida: ${powerPreference}.`);
  if (!environment.isSecureContext) throw new Error('El renderer requiere HTTPS o localhost.');
  if (!environment.crossOriginIsolated || typeof environment.SharedArrayBuffer === 'undefined')
    throw new Error('El servidor debe habilitar COOP/COEP para los hilos WASM.');

  if (backend === 'webgl') {
    const gl = canvas.getContext('webgl2', { powerPreference, alpha: false,
      antialias: false, depth: true, stencil: true });
    if (!gl) throw new Error('WebGL 2 no está disponible.');
    const debug = gl.getExtension('WEBGL_debug_renderer_info');
    const diagnostics = { backend, powerPreference, owner,
      renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
      version: gl.getParameter(gl.VERSION) };
    report({ type: 'ready', ...diagnostics });
    return { diagnostics, gl, dispose: async () => {} };
  }

  const gpu = environment.navigator?.gpu;
  if (!gpu) throw new Error('WebGPU no está disponible. Selecciona WebGL y reinicia.');
  const adapter = await gpu.requestAdapter(powerPreference === 'default' ? {} : { powerPreference });
  if (!adapter) throw new Error('No se encontró un adaptador WebGPU.');
  for (const feature of requiredFeatures) {
    if (!adapter.features.has(feature)) throw new Error(`Falta la función WebGPU: ${feature}.`);
  }
  const enabledFeatures=[...new Set([...requiredFeatures,...optionalFeatures.filter(feature=>adapter.features.has(feature))])];
  const device = await adapter.requestDevice({ requiredFeatures:enabledFeatures, requiredLimits });
  let context;
  let disposed = false;
  let lost = false;
  const info = adapter.info ?? {};
  const diagnostics = { backend, powerPreference, owner,
    adapter: Object.fromEntries(['vendor', 'architecture', 'device', 'description']
      .map(name => [name, info[name] ?? ''])),
    adapterFeatures: [...adapter.features].sort(), adapterLimits: describeLimits(adapter.limits),
    deviceFeatures: [...device.features].sort(), deviceLimits: describeLimits(device.limits),
    unavailableOptionalFeatures:optionalFeatures.filter(feature=>!adapter.features.has(feature)),
    fallbackAdapter: adapter.isFallbackAdapter ?? null };
  const onError = event => report({ type: 'uncaptured-error', backend,
    name: event.error?.constructor?.name, message: event.error?.message ?? String(event.error) });
  device.addEventListener('uncapturederror', onError);
  device.lost.then(info => {
    lost = true;
    report({ type: 'device-lost', backend, reason: info.reason,
      message: info.message, expected: disposed });
  });
  try {
    context = canvas.getContext('webgpu');
    if (!context) throw new Error('No se pudo crear el contexto WebGPU. Recarga para cambiar de backend.');
    diagnostics.format = gpu.getPreferredCanvasFormat();
    context.configure({ device, format: diagnostics.format, alphaMode: 'opaque', usage: 0x10 | 0x01 | 0x02 });
    report({ type: 'ready', ...diagnostics });
  } catch (error) {
    disposed = true;
    device.removeEventListener('uncapturederror', onError);
    context?.unconfigure();
    device.destroy();
    throw error;
  }
  return { device, context, diagnostics,
    // Always unwind the scope, including when submission throws.
    async validationScope(work) {
      if (disposed || lost) throw new Error('El dispositivo WebGPU ya no está disponible.');
      device.pushErrorScope('validation');
      try { return await work(); }
      finally {
        const error = await device.popErrorScope();
        if (error) {
          report({ type: 'validation-error', backend, message: error.message });
          throw new Error(error.message);
        }
      }
    },
    async dispose() {
      if (disposed) return;
      disposed = true;
      try { if (!lost) await device.queue.onSubmittedWorkDone(); }
      finally {
        device.removeEventListener('uncapturederror', onError);
        context.unconfigure();
        device.destroy();
      }
    }
  };
}
