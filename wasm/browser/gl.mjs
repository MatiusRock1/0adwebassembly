import createGL from './pyrogenesis-gl.mjs';
const lines = [];
const status = document.querySelector('#status');
window.glResult = null;
function record(line) {
  lines.push(String(line));
  document.querySelector('#log').textContent += line + '\n';
}
try {
  if (!crossOriginIsolated || typeof SharedArrayBuffer !== 'function')
    throw new Error('Se requieren COOP/COEP y SharedArrayBuffer.');
  await createGL({canvas: document.querySelector('#canvas'), print: record, printErr: record,
    onAbort(reason) { window.glResult = {passed: false, reason: String(reason), lines}; },
    onExit(code) {
      const passed = code === 0 && lines.some(l => l.startsWith('GL_ENGINE_CLEAR_PASSED '));
      window.glResult = {passed, exitCode: code, lines};
      status.textContent = passed ? 'El backend original creó y presentó el framebuffer.' : 'El diagnóstico falló.';
    }
  });
} catch (error) {
  status.textContent = 'Error: ' + error;
  window.glResult = {passed: false, reason: String(error), lines};
}
