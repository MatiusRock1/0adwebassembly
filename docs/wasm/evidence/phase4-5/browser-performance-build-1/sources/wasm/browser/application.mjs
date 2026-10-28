import createApplication from './pyrogenesis-application.mjs';
import { openRendererSession } from './renderer-session.mjs';
import { WebGPUEngine } from './webgpu-engine.mjs';
import { installFullscreenPointer } from './application-pointer.mjs';
import { installApplicationFailureBoundary } from './application-failure.mjs';
import {openRenderWorker} from './webgpu-worker-bridge.mjs';
import {openArchiveService,installArchiveNodes,installPersistentConfig} from './application-archives.mjs';

const canvas = document.querySelector('#canvas');
const status = document.querySelector('#status');
const log = document.querySelector('#log');
const query = new URL(location.href).searchParams;
const gpuPreference = document.querySelector('#gpu-preference');
const gpuInfo = document.querySelector('#gpu-info');
const backendSelector = document.querySelector('#renderer-backend');
try {
  const saved = localStorage.getItem('0ad-gpu-preference');
  if (['default', 'high-performance'].includes(saved)) gpuPreference.value = saved;
} catch { /* Storage may be unavailable; the selector still works. */ }
gpuPreference.addEventListener('change', () => {
  try { localStorage.setItem('0ad-gpu-preference', gpuPreference.value); } catch { }
});
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
  const response = await fetch(`${mod}.zip`);
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

async function installData(module,manifest) {
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
    archiveService=await openArchiveService(blocks,{report:event=>record(JSON.stringify(event)),
      onFailure:error=>failureBoundary?.abort(error.message,module)});
    module.archiveService=archiveService;installArchiveNodes(module,blocks);
    window.archiveDiagnostics=archiveService.diagnostics;
  }else{
    await installArchive(module, 'mod');
    await installArchive(module, 'public');
  }
  const saved = localStorage.getItem('0ad-phase4-user-config');
  if (saved !== null) module.FS.writeFile('/data/config/user.cfg', saved);
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
  gpuPreference.disabled = true;
  backendSelector.disabled = true;
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
      rendererSession=await openRenderWorker({...rendererOptions,catalog:shaderCatalog,report:reportRenderer});
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
        for (const id of ['fullscreen','close','audio']) document.getElementById(id).disabled = true;
      },
      report: error => record(`Abort teardown: ${error.message}`)
    });
    window.rendererDiagnostics = rendererSession.diagnostics;
    gpuInfo.textContent = webgpu ? `WebGPU · ${rendererSession.diagnostics.adapter.vendor} ${rendererSession.diagnostics.adapter.architecture}` : rendererSession.diagnostics.renderer
      ? `WebGL 2 · GPU utilizada: ${rendererSession.diagnostics.renderer}`
      : 'WebGL 2 · El navegador no permite identificar la GPU utilizada.';
    gpuInfo.title = 'Para cambiar la preferencia de gráfica, recarga la página antes de iniciar el juego.';
    application = await createApplication({
      canvas,
      webgpuBackend,
      arguments: ['-writableRoot', '-mod=public', '-conf=windowed:true', '-conf=xres:1280', '-conf=yres:720', '-conf=vsync:true', `-conf=rendererbackend:${webgpu?'webgpu':'gl'}`, '-conf=userreport.enabledversion:0',
        ...(query.get('automation')==='1' && query.get('functional-frame-frequency')==='60' ? ['-fixed-frame-frequency=60'] : [])],
      print: record,
      printErr: record,
      preRun: [module => {
        module.ENV.HOME = '/data';
        module.ENV.ICU_DATA = '/data/icu';
        if (query.get('automation') === '1') module.ENV.PHASE4_AUTOMATION = '1';
        if (query.get('traceVFS') === '1') module.ENV.PHASE4_TRACE_VFS = '1';
        module.addRunDependency('original-data');
        installData(module,dataManifest).then(() => module.removeRunDependency('original-data')).catch(error => {
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
      },
      onAbort: function(reason) {
        // Emscripten invokes this as Module.onAbort. The factory promise may
        // still be pending during archive/startup errors.
        failureBoundary.abort(reason, this);
      }
    });
    window.application = application;
    document.querySelector('#fullscreen').disabled = false;
    document.querySelector('#audio').disabled = false;
    document.querySelector('#close').disabled = false;
    status.textContent = 'Inicializando los menús originales…';
    const readyStatus = setInterval(() => {
      if (window.applicationResult) { clearInterval(readyStatus); return; }
      if (application.applicationState?.frame > 0) {
        status.textContent = '0 A.D. en ejecución.';
        clearInterval(readyStatus);
      }
    }, 250);
    canvas.focus();
  } catch (error) {
    status.textContent = error.message;
    record(error.stack || error.message);
    window.applicationResult = { error: error.message };
    if (!rendererSession) {
      // No context was created: changing the selection is safe without reload.
      document.querySelector('#start').disabled = false;
      gpuPreference.disabled = false;
      backendSelector.disabled = false;
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
document.querySelector('#audio').addEventListener('click', () => {
  application?.resumeOriginalAudio().catch(error => { status.textContent = `No se pudo activar el audio: ${error.message}`; });
  canvas.focus();
});

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
