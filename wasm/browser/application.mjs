import createApplication from './pyrogenesis-application.mjs';
import { openRendererSession } from './renderer-session.mjs';
import { WebGPUEngine } from './webgpu-engine.mjs';
import { installFullscreenPointer } from './application-pointer.mjs';
import { installApplicationFailureBoundary } from './application-failure.mjs';
import {openRenderWorker} from './webgpu-worker-bridge.mjs';
import {openArchiveService,installArchiveNodes,installPersistentConfig} from './application-archives.mjs';
import {GRAPHICS_MODES,LOW_GRAPHICS_SETTINGS,classifyGPU,selectGraphicsProfile,graphicsConfig,readWebGLRenderer,detectOS,gpuGuide} from './application-graphics.mjs';

const canvas = document.querySelector('#canvas');
const status = document.querySelector('#status');
const log = document.querySelector('#log');
const query = new URL(location.href).searchParams;
// ?assets= overrides the archive directory a deployment writes into the page.
const archiveBaseURL = new URL(query.get('assets') ||
  document.querySelector('meta[name="archive-base"]')?.content || './', location.href).href;
// A deployment may host each archive at its own URL. These win over ?assets=,
// so stale links that still carry an old archive directory keep working.
const archiveURLs = Object.fromEntries(['public', 'mod'].flatMap(name => {
  const url = document.querySelector(`meta[name="archive-${name}"]`)?.content;
  return url ? [[name, new URL(url, location.href).href]] : [];
}));
const gpuPreference = document.querySelector('#gpu-preference');
const gpuInfo = document.querySelector('#gpu-info');
const gpuGuidePanel = document.querySelector('#gpu-guide');
const backendSelector = document.querySelector('#renderer-backend');
const graphicsQuality = document.querySelector('#graphics-quality');
try {
  const saved = localStorage.getItem('0ad-gpu-preference');
  if (['default', 'high-performance'].includes(saved)) gpuPreference.value = saved;
  const backend = localStorage.getItem('0ad-renderer-backend');
  if (['webgl', 'webgpu'].includes(backend)) backendSelector.value = backend;
  const quality = localStorage.getItem('0ad-graphics-quality');
  if (GRAPHICS_MODES.includes(quality)) graphicsQuality.value = quality;
} catch { /* Storage may be unavailable; the selector still works. */ }
// ?renderer=webgpu preselects the experimental backend; WebGL 2 stays the default.
if (query.get('renderer') === 'webgpu') backendSelector.value = 'webgpu';
// ?graphics=auto|low|original overrides the saved choice for this page load.
if (GRAPHICS_MODES.includes(query.get('graphics'))) graphicsQuality.value = query.get('graphics');
gpuPreference.addEventListener('change', () => {
  try { localStorage.setItem('0ad-gpu-preference', gpuPreference.value); } catch { }
  probeGPUGuide();
});
backendSelector.addEventListener('change', () => {
  try { localStorage.setItem('0ad-renderer-backend', backendSelector.value); } catch { }
});
graphicsQuality.addEventListener('change', () => {
  try { localStorage.setItem('0ad-graphics-quality', graphicsQuality.value); } catch { }
});
const GPU_CATEGORIES = { software: 'renderizado por software', integrated: 'GPU integrada',
  entry: 'GPU dedicada de gama de entrada', capable: 'GPU con potencia suficiente', unknown: 'GPU no identificada' };
function describeGraphics({ mode, profile, gpu }) {
  const quality = profile === 'low' ? 'baja' : 'original';
  return mode === 'auto' ? `calidad gráfica automática: ${quality} (${GPU_CATEGORIES[gpu.category]})`
    : `calidad gráfica: ${quality} (elegida)`;
}
const GPU_GUIDE_TITLES = {
  dedicated: name => `El navegador está usando la gráfica integrada${name ? ` (${name})` : ''}. ` +
    'Si tu equipo tiene además una gráfica dedicada, así puedes hacer que la use.',
  acceleration: () => 'El navegador está dibujando sin aceleración por hardware y el juego irá muy lento. Cómo activarla.'
};
function showGPUGuide(gpu) {
  const os = detectOS(), guide = gpuGuide(gpu, os);
  gpuGuidePanel.hidden = !guide;
  if (!guide) return;
  gpuGuidePanel.querySelector(':scope > summary').textContent = GPU_GUIDE_TITLES[guide](gpu.name);
  for (const part of gpuGuidePanel.querySelectorAll('[data-guide]')) part.hidden = part.dataset.guide !== guide;
  for (const section of gpuGuidePanel.querySelectorAll('[data-os]')) section.open = section.dataset.os === os;
}
// Before the game starts, so the player can switch GPUs before the download.
function probeGPUGuide() {
  showGPUGuide(classifyGPU({ renderer: readWebGLRenderer(gpuPreference.value) }));
}
probeGPUGuide();
// Browsers keep audio suspended until a user gesture; resume on every one.
for (const type of ['pointerdown', 'keydown'])
  window.addEventListener(type, () => application?.resumeOriginalAudio?.().catch(() => {}), true);
const lines = [];
let application;
const fullscreenPointer = installFullscreenPointer({ canvas, surface: document.querySelector('#game-surface'),
  getApplication: () => window.applicationResult ? null : application, report: message => { status.textContent = message; } });
let rendererSession;
let archiveService,persistentConfig,failureBoundary;
window.applicationResult = null;
function record(message) {
  lines.push(String(message));
  if (lines.length > 300) lines.shift();
  log.textContent = lines.join('\n');
  console.log(message);
}
canvas.addEventListener('contextmenu', event => event.preventDefault());
canvas.addEventListener('pointerdown', () => canvas.focus());
canvas.addEventListener('keydown', event => {
  if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.code)) event.preventDefault();
});

// Keep each archive outside WASM memory. The original ZIP VFS reads these
// immutable bytes through MEMFS, in bounded chunks without a multi-GiB copy.
async function installArchive(module, mod) {
  const response = await fetch(archiveURLs[mod] || new URL(`${mod}.zip`, archiveBaseURL));
  if (!response.ok || !response.body) throw new Error(`No se pudo cargar ${mod}.zip (${response.status}).`);
  const reader = response.body.getReader();
  const chunks = [];
  const offsets = [];
  let bytes = 0;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    offsets.push(bytes);
    chunks.push(value);
    bytes += value.length;
    status.textContent = `Cargando recursos originales: ${mod}, ${(bytes / 1048576).toFixed(0)} MiB.`;
    showDownload(bytes);
  }
  const directory = `/data/mods/${mod}`;
  module.FS.mkdirTree(directory);
  const path = `${directory}/${mod}.zip`;
  module.FS.writeFile(path, new Uint8Array(0));
  const node = module.FS.lookupPath(path).node;
  node.usedBytes = bytes;
  node.stream_ops = { ...node.stream_ops, read(stream, destination, offset, length, position) {
    if (position >= bytes) return 0;
    const wanted = Math.min(length, bytes - position);
    let copied = 0;
    // Binary search the starting network chunk, then copy only the requested
    // file range. VFS decompression and caches remain original engine code.
    let low = 0;
    let high = offsets.length;
    while (low + 1 < high) {
      const middle = (low + high) >>> 1;
      if (offsets[middle] <= position) low = middle; else high = middle;
    }
    let index = low;
    while (copied < wanted) {
      const chunkOffset = position + copied - offsets[index];
      const count = Math.min(wanted - copied, chunks[index].length - chunkOffset);
      destination.set(chunks[index].subarray(chunkOffset, chunkOffset + count), offset + copied);
      copied += count;
      index++;
    }
    return copied;
  }, write() { throw new module.FS.ErrnoError(69); } };
}

const loading = document.querySelector('#loading');
const loadingText = document.querySelector('#loading-text');
let engineReady = false;
function showLoading(message) { loading.hidden = false; loadingText.textContent = message; }
function showDownload(bytes) {
  const message = `Descargando recursos originales: ${(bytes / 1048576).toFixed(0)} MiB. Solo ocurre la primera vez o tras una actualización.`;
  // Once the engine draws, later downloads (e.g. a match) must not cover it.
  if (engineReady) status.textContent = message; else showLoading(message);
}

async function installData(module,manifest,localConfig) {
  for (const file of manifest.files) {
    const payload = await fetch(file.url);
    if (!payload.ok) throw new Error(`Falta ${file.url}.`);
    const parent = file.path.slice(0, file.path.lastIndexOf('/'));
    module.FS.mkdirTree(parent);
    module.FS.writeFile(file.path, new Uint8Array(await payload.arrayBuffer()), { canOwn: true });
  }
  if(manifest.runtimeFeatures?.persistentArchives){
    const response=await fetch('archive-blocks.json');
    if(!response.ok)throw new Error('Falta el manifiesto de bloques originales.');
    const blocks=await response.json();
    // Without a persistence grant the browser may evict the ~2 GB block cache.
    try{await navigator.storage?.persist?.();}catch{}
    archiveService=await openArchiveService(blocks,{baseURL:archiveBaseURL,urls:archiveURLs,
      report:event=>event.type==='archive-progress'?showDownload(event.networkBytes):record(JSON.stringify(event)),
      onFailure:error=>failureBoundary?.abort(error.message,module)});
    module.archiveService=archiveService;installArchiveNodes(module,blocks);
    window.archiveDiagnostics=archiveService.diagnostics;
  }else{
    await installArchive(module, 'mod');
    await installArchive(module, 'public');
  }
  const saved = localStorage.getItem('0ad-phase4-user-config');
  if (saved !== null) module.FS.writeFile('/data/config/user.cfg', saved);
  // Defaults of this machine (the graphics profile); user.cfg still overrides them.
  if (localConfig) module.FS.writeFile('/data/config/local.cfg', localConfig);
  if(manifest.runtimeFeatures?.persistentConfig)
    persistentConfig=await installPersistentConfig(module,event=>record(JSON.stringify(event)));
  module.persistentConfig=persistentConfig;
  const originalClose = module.FS.close;
  module.FS.close = stream => {
    const config = stream.path === '/data/config/user.cfg' && (stream.flags & 3) !== 0;
    const result = originalClose(stream);
    if (config) {
      try { localStorage.setItem('0ad-phase4-user-config', module.FS.readFile('/data/config/user.cfg', { encoding: 'utf8' })); }
      catch (error) { record(`No se pudieron persistir los ajustes: ${error.message}`); }
      persistentConfig?.save();
    }
    return result;
  };
}

document.querySelector('#start').addEventListener('click', async () => {
  document.querySelector('#start').disabled = true;
  showLoading('Preparando 0 A.D.…');
  gpuPreference.disabled = true;
  backendSelector.disabled = true;
  graphicsQuality.disabled = true;
  window.applicationResult = null;
  try {
    const dataResponse=await fetch('application-data.json');
    if(!dataResponse.ok)throw new Error('Falta el manifiesto de datos originales.');
    const dataManifest=await dataResponse.json();
    if(dataManifest.runtimeFeatures?.asyncSuspension==='jspi' &&
       (typeof WebAssembly.Suspending!=='function' || typeof WebAssembly.promising!=='function'))
      throw new Error('Este build requiere un navegador compatible con promesas WebAssembly.');
    window.applicationFeatures=dataManifest.runtimeFeatures??{};
    // Select the backend and its offline resources before binding the canvas.
    const webgpu = backendSelector.value === 'webgpu';
    let shaderCatalog;
    if(webgpu) {
      const response = await fetch('webgpu-shaders.json');
      if(!response.ok)throw new Error('Falta el paquete offline de shaders WebGPU.');
      shaderCatalog = await response.json();
    }
    const rendererOptions={ canvas, backend: backendSelector.value,
      requiredFeatures: webgpu ? ['texture-compression-bc'] : [],
      optionalFeatures: webgpu ? ['float32-filterable','float32-blendable','depth32float-stencil8','dual-source-blending','rg11b10ufloat-renderable'] : [],
      powerPreference: gpuPreference.value, report: event => record(JSON.stringify(event)) };
    let deviceLost = false;
    const reportRenderer=event => {
      if(event.type !== 'engine-frame')record(JSON.stringify(event));
      if(event.type === 'engine-device-lost' && !event.expected) {
        deviceLost = true;
        status.textContent = 'Se perdió el dispositivo WebGPU. Reinicia la página para continuar; los ajustes guardados se conservan.';
        application?.ccall('Phase4RequestClose', null, [], []);
        if(event.reason==='render-worker')failureBoundary?.abort(event.message,application);
      }
    };
    let webgpuBackend;
    if(webgpu && dataManifest.runtimeFeatures?.renderWorker){
      // ?commandRing=0 keeps the window relay of engine commands and
      // ?pipelineCache=0 skips the warm pipeline list, for comparisons.
      rendererSession=await openRenderWorker({...rendererOptions,catalog:shaderCatalog,report:reportRenderer,
        commandRing:query.get('commandRing')!=='0',pipelineCache:query.get('pipelineCache')!=='0'});
      webgpuBackend=rendererSession.bridge;
    }else{
      rendererSession=await openRendererSession(rendererOptions);
      if(webgpu)webgpuBackend=new WebGPUEngine(rendererSession,canvas,shaderCatalog,reportRenderer);
    }
    window.webgpuBackend = webgpuBackend;
    failureBoundary = installApplicationFailureBoundary({
      eventTarget: window, runtimeURL: new URL('./pyrogenesis-application.mjs', import.meta.url).href,
      getApplication: () => application,
      releasePointer: async () => {
        fullscreenPointer.release();
        if (document.fullscreenElement) await document.exitFullscreen();
      },
      disposeRenderer: () => Promise.all([webgpuBackend?.dispose(),archiveService?.dispose(),persistentConfig?.flush()]),
      onFailure: (reason, cleanup) => {
        window.applicationResult = { error: reason };
        window.applicationCleanup = cleanup;
        status.textContent = `Error del motor: ${reason}. Recarga la página para continuar.`;
        for (const id of ['fullscreen','close']) document.getElementById(id).disabled = true;
      },
      report: error => record(`Abort teardown: ${error.message}`)
    });
    window.rendererDiagnostics = rendererSession.diagnostics;
    const diagnostics = rendererSession.diagnostics;
    // WebGPU reports no GPU model; a short-lived WebGL context names it.
    const gpu = classifyGPU(webgpu ? { renderer: readWebGLRenderer(gpuPreference.value),
      adapter: diagnostics.adapter, fallbackAdapter: diagnostics.fallbackAdapter } : { renderer: diagnostics.renderer });
    const graphicsProfile = selectGraphicsProfile(graphicsQuality.value, gpu);
    window.graphicsProfile = { mode: graphicsQuality.value, profile: graphicsProfile, gpu,
      settings: graphicsProfile === 'low' ? LOW_GRAPHICS_SETTINGS : {} };
    record(JSON.stringify({ type: 'graphics-profile', ...window.graphicsProfile }));
    showGPUGuide(gpu);
    const adapterName = webgpu && `${diagnostics.adapter.vendor} ${diagnostics.adapter.architecture}`;
    const backendInfo = webgpu ? `WebGPU · ${gpu.renderer ? `${gpu.name} (${adapterName})` : adapterName}` : diagnostics.renderer
      ? `WebGL 2 · GPU utilizada: ${diagnostics.renderer}`
      : 'WebGL 2 · El navegador no permite identificar la GPU utilizada.';
    gpuInfo.textContent = `${backendInfo} · ${describeGraphics(window.graphicsProfile)}`;
    gpuInfo.title = 'Para cambiar la preferencia de gráfica o la calidad, recarga la página antes de iniciar el juego. Los ajustes guardados en Opciones del juego tienen prioridad.';
    application = await createApplication({
      canvas,
      webgpuBackend,
      arguments: ['-writableRoot', '-mod=public', '-conf=windowed:true', '-conf=xres:1280', '-conf=yres:720', '-conf=vsync:true', `-conf=rendererbackend:${webgpu?'webgpu':'gl'}`, '-conf=userreport.enabledversion:0',
        ...(query.get('aiworker') ? [`-conf=aiworker.mode:${query.get('aiworker')}`] : []),
        ...(query.get('automation')==='1' && query.get('functional-frame-frequency')==='60' ? ['-fixed-frame-frequency=60'] : [])],
      print: record,
      printErr: record,
      preRun: [module => {
        module.ENV.HOME = '/data';
        module.ENV.ICU_DATA = '/data/icu';
        if (query.get('automation') === '1') module.ENV.PHASE4_AUTOMATION = '1';
        if (query.get('traceVFS') === '1') module.ENV.PHASE4_TRACE_VFS = '1';
        module.addRunDependency('original-data');
        const localConfig = graphicsProfile === 'low' ? graphicsConfig(LOW_GRAPHICS_SETTINGS) : null;
        installData(module,dataManifest,localConfig).then(() => module.removeRunDependency('original-data')).catch(error => {
          record(error.message);
          status.textContent = error.message;
          module.abort(error.message);
        });
      }],
      onExit: code => {
        failureBoundary.dispose();
        fullscreenPointer.release();
        window.applicationCleanup=Promise.all([webgpuBackend?.dispose(),archiveService?.dispose(),persistentConfig?.flush()]);
        window.applicationResult = { code };
        if (!deviceLost) status.textContent = `Juego cerrado (${code}).`;
        document.querySelector('#fullscreen').disabled = true;
        document.querySelector('#close').disabled = true;
        // The engine's threads, WASM memory and canvas context cannot be
        // reinitialised in place; reload once cleanup has flushed the settings.
        if (!deviceLost && query.get('automation') !== '1')
          window.applicationCleanup.finally(() => location.reload());
      },
      onAbort: function(reason) {
        // Emscripten invokes this as Module.onAbort. The factory promise may
        // still be pending during archive/startup errors.
        failureBoundary.abort(reason, this);
      }
    });
    window.application = application;
    document.querySelector('#fullscreen').disabled = false;
    document.querySelector('#close').disabled = false;
    status.textContent = 'Inicializando los menús originales…';
    const readyStatus = setInterval(() => {
      if (window.applicationResult) { loading.hidden = true; clearInterval(readyStatus); return; }
      if (application.applicationState?.frame > 0) {
        loading.hidden = true;
        engineReady = true;
        status.textContent = '0 A.D. en ejecución.';
        clearInterval(readyStatus);
      }
    }, 250);
    canvas.focus();
  } catch (error) {
    loading.hidden = true;
    status.textContent = error.message;
    record(error.stack || error.message);
    window.applicationResult = { error: error.message };
    if (!rendererSession) {
      // No context was created: changing the selection is safe without reload.
      document.querySelector('#start').disabled = false;
      gpuPreference.disabled = false;
      backendSelector.disabled = false;
      graphicsQuality.disabled = false;
    }
  }
});

document.querySelector('#fullscreen').addEventListener('click', async () => {
  try { await fullscreenPointer.enter(); canvas.focus(); }
  catch (error) { status.textContent = `No se pudo entrar en pantalla completa: ${error.message}`; }
});
document.addEventListener('fullscreenchange', () => {
  if (!application || window.applicationResult) return;
  const width = document.fullscreenElement ? 1920 : 1280;
  const height = document.fullscreenElement ? 1080 : 720;
  application.ccall('Phase4Resize', null, ['number', 'number'], [width, height]);
});
document.querySelector('#close').addEventListener('click', () => application?.ccall('Phase4RequestClose', null, [], []));

if (query.get('automation') === '1') window.evaluateOriginalGUI = async code => {
  if (!application?.ccall('Phase4QueueScript', 'number', ['string'], [code])) throw new Error('El motor no aceptó la solicitud de prueba.');
  const deadline = performance.now() + 30000;
  while (performance.now() < deadline) {
    if(window.applicationResult)throw new Error(window.applicationResult.error || 'El motor ya se cerró.');
    const result = application.ccall('Phase4ScriptResult', 'string', [], []);
    if (result) {
      application.ccall('Phase4ClearScriptResult', null, [], []);
      if (result === 'SCRIPT_EVALUATION_FAILED') throw new Error(result);
      return result;
    }
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  throw new Error('El motor no respondió a la prueba de GUI.');
};
