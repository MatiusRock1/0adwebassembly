import createScene from './pyrogenesis-scene.mjs';
const canvas = document.querySelector('#canvas');
const status = document.querySelector('#status');
const lines = [];
const frameSamples = [];
const traceMarks = new URL(location.href).searchParams.get('traceMarks') === '1';
window.sceneJsLongTasks = [];
if (typeof PerformanceObserver === 'function' && PerformanceObserver.supportedEntryTypes.includes('longtask')) {
  new PerformanceObserver(list => {
    for (const entry of list.getEntries()) {
      window.sceneJsLongTasks.push({startMs: entry.startTime, durationMs: entry.duration, name: entry.name});
      if (window.sceneJsLongTasks.length > 4096) window.sceneJsLongTasks.shift();
    }
  }).observe({type: 'longtask', buffered: true});
}
window.sceneFrames = frameSamples;
window.sceneResult = null;
window.sceneState = {ready: false, metrics: null, events: []};
function record(line) {
  line = String(line);
  if (line.startsWith('SCENE_FRAME ')) {
    const receiveStart = performance.now();
    const sample = JSON.parse(line.slice(12));
    sample.receivedMs = performance.now();
    frameSamples.push(sample);
    if (traceMarks) {
      const name = '0ad-draw:' + sample.frame;
      performance.mark(name); performance.clearMarks(name);
    }
    if (frameSamples.length > 65000) frameSamples.shift();
    sample.receiveCostMs = performance.now() - receiveStart;
    return;
  }
  lines.push(line);
  if (lines.length > 300) lines.shift();
  if (line.startsWith('SCENE_') || line.startsWith('ERROR:') || line.includes('Aborted')) console.log(line);
  if (line.startsWith('SCENE_STATS ')) {
    const metrics = JSON.parse(line.slice(12));
    window.sceneState.metrics = metrics;
    document.querySelector('#metrics').textContent = `Turno ${metrics.tick} | ${metrics.paused ? 'Pausa' : 'En marcha'} | Unidad ${metrics.selected || '-'} | Reinicios ${metrics.restarts}`;
  } else if (line === 'SCENE_READY') {
    try {
      const gl = canvas.getContext('webgl2');
      const debug = gl?.getExtension('WEBGL_debug_renderer_info');
      if (gl) Object.assign(window.sceneHardware, {
        renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
        gpuTimerAvailable: Boolean(gl.getExtension('EXT_disjoint_timer_query_webgl2')),
        rendererSource: 'actual scene context', requestedPowerPreference: 'high-performance'});
    } catch { window.sceneHardware.rendererSource = 'startup probe; worker-owned context cannot be inspected here'; }
    window.sceneState.ready = true;
    status.textContent = 'Mapa listo. Haz clic en el terreno para activar los controles.';
  } else if (line.startsWith('SCENE_')) {
    window.sceneState.events.push(line);
    if (line === 'SCENE_MAP_LOAD_BEGIN') status.textContent = 'Cargando mapa original...';
    if (line === 'SCENE_LOADER_FINISHED') status.textContent = 'Inicializando jugadores y scripts...';
    if (line === 'SCENE_GAME_INITIALIZED') status.textContent = 'Preparando terreno y modelos...';
    if (line.startsWith('SCENE_MAP_LOADED ') && window.sceneState.ready) status.textContent = 'Mapa recargado. Haz clic en el terreno para activar los controles.';
    if (line === 'SCENE_FOCUS_PAUSED' && window.sceneState.metrics) window.sceneState.metrics.paused = true;
  }
  if (!line.startsWith('VFS_READ ')) document.querySelector('#log').textContent = lines.filter(l => !l.startsWith('VFS_READ ')).join('\n');
}
canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('pointerdown', () => canvas.focus());
canvas.addEventListener('keydown', e => {if (['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code)) e.preventDefault();});
// Esc is reserved for browser fullscreen exit and pause. Closing is explicit.
window.addEventListener('keydown', e => {
  if (e.code === 'Escape') {
    window.sceneState.events.push('SCENE_ESCAPE');
    e.stopImmediatePropagation();
    if (document.fullscreenElement) document.exitFullscreen().catch(error => {
      status.textContent = `No se pudo salir de pantalla completa: ${error.message}`;
    });
    pauseWhenInactive();
  }
}, true);
const keys = {Space: [' ', 32], KeyN: ['n', 78], KeyR: ['r', 82], Escape: ['x', 88]};
function sendKey(code, key, keyCode) {
  for (const type of ['keydown', 'keyup']) canvas.dispatchEvent(new KeyboardEvent(type, {key, code, keyCode, which: keyCode, bubbles: true}));
}
for (const button of document.querySelectorAll('[data-key]')) button.addEventListener('click', () => {
  canvas.focus();
  const code = button.dataset.key;
  const [key, keyCode] = keys[code];
  sendKey(code === 'Escape' ? 'KeyX' : code, key, keyCode);
});
function pauseWhenInactive() {
  if (window.sceneState.ready && window.sceneResult === null) sendKey('KeyP', 'p', 80);
}
window.addEventListener('blur', pauseWhenInactive);
document.addEventListener('visibilitychange', () => {if (document.hidden) pauseWhenInactive();});
document.querySelector('#resolution').addEventListener('change', e => {
  const [width, height] = e.target.value.split(',').map(Number);
  canvas.width = width; canvas.height = height; canvas.focus();
});
function fitFullscreen() {
  if (document.fullscreenElement !== canvas) return;
  const scale = Number(document.querySelector('#render-scale').value);
  canvas.width = Math.max(1, Math.round(innerWidth * devicePixelRatio * scale));
  canvas.height = Math.max(1, Math.round(innerHeight * devicePixelRatio * scale));
}
let windowedSize;
document.querySelector('#fullscreen').addEventListener('click', async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else { windowedSize = [canvas.width, canvas.height]; await canvas.requestFullscreen({navigationUI: 'hide'}); canvas.focus(); }
  } catch (error) { status.textContent = `Pantalla completa no disponible: ${error.message}`; }
});
document.addEventListener('fullscreenchange', () => {
  document.querySelector('#fullscreen').textContent = document.fullscreenElement === canvas ? 'Salir de pantalla completa' : 'Pantalla completa';
  if (document.fullscreenElement === canvas) fitFullscreen();
  else if (windowedSize) [canvas.width, canvas.height] = windowedSize;
  canvas.focus();
});
window.addEventListener('resize', fitFullscreen);
document.querySelector('#render-scale').addEventListener('change', fitFullscreen);
canvas.addEventListener('webglcontextlost', e => {
  e.preventDefault(); pauseWhenInactive();
  window.sceneModule?._StopSceneFrameClock?.();
  window.sceneModule?.PThread?.terminateAllThreads();
  status.textContent = 'Se perdio el contexto WebGL. Usa Recuperar escena para cargar de nuevo el mapa; el estado no guardado se perdera.';
  window.sceneResult = {passed: false, reason: 'WebGL context lost', lines};
});
document.querySelector('#recover').addEventListener('click', () => location.reload());
document.querySelector('#export-profile').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify({hardware: window.sceneHardware, frames: frameSamples,
    state: window.sceneState, result: window.sceneResult}, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob); const a = document.createElement('a');
  a.href = url; a.download = 'scene-profile.json'; a.click(); URL.revokeObjectURL(url);
});
try {
  if (!crossOriginIsolated || typeof SharedArrayBuffer !== 'function') throw new Error('Se requieren COOP/COEP y SharedArrayBuffer.');
  const probe = document.createElement('canvas').getContext('webgl2', {powerPreference: 'high-performance'});
  if (!probe) throw new Error('Se requiere WebGL 2 con aceleracion grafica habilitada.');
  const debug = probe.getExtension('WEBGL_debug_renderer_info');
  window.sceneHardware = {userAgent: navigator.userAgent, concurrency: navigator.hardwareConcurrency,
    timeOriginMs: performance.timeOrigin,
    deviceMemoryGiB: navigator.deviceMemory ?? null, dpr: devicePixelRatio,
    renderer: debug ? probe.getParameter(debug.UNMASKED_RENDERER_WEBGL) : probe.getParameter(probe.RENDERER),
    gpuTimerAvailable: Boolean(probe.getExtension('EXT_disjoint_timer_query_webgl2')),
    offscreenAvailable: typeof OffscreenCanvas === 'function'};
  probe.getExtension('WEBGL_lose_context')?.loseContext();
  try { new WebAssembly.Memory({initial: 1024, maximum: 32768, shared: true}); }
  catch { throw new Error('No se pudo reservar la memoria compartida inicial (64 MiB). Cierra otras aplicaciones o usa un navegador de 64 bits.'); }
  window.sceneModule = await createScene({canvas, print: record, printErr: record,
    onAbort(reason) {(window.sceneModule ?? this)?._StopSceneFrameClock?.(); (window.sceneModule ?? this)?.PThread?.terminateAllThreads(); status.textContent = 'Error: ' + reason; window.sceneResult = {passed: false, reason: String(reason), lines};},
    onExit(code) {window.sceneModule?.PThread?.terminateAllThreads(); window.sceneResult = {passed: code === 0 && window.sceneState.ready, exitCode: code, lines}; status.textContent = code === 0 ? 'Escena cerrada.' : 'La escena fallo.';}
  });
} catch (error) {
  status.textContent = 'Error: ' + error;
  window.sceneResult = {passed: false, reason: String(error), lines};
}
