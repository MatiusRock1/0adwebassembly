import createMap from './pyrogenesis-map.mjs';
const status = document.querySelector('#status');
const log = document.querySelector('#log');
const lines = [];
let module;
window.mapResult = null;
function record(line) {
  lines.push(String(line));
  if (!String(line).startsWith('VFS_READ ')) log.textContent += line + '\n';
}
try {
  if (!crossOriginIsolated || typeof SharedArrayBuffer !== 'function')
    throw new Error('Se requieren COOP/COEP y SharedArrayBuffer.');
  const reference = await (await fetch('./native-checkpoints.json')).json();
  status.textContent = 'Cargando y ejecutando 1.100 ticks…';
  module = await createMap({
    print: record,
    printErr: record,
    onAbort(reason) {
      status.textContent = 'Error: ' + reason;
      window.mapResult = {passed: false, reason: String(reason), lines};
    },
    onExit(code) {
      setTimeout(async () => {
        try {
          const checkpoints = [];
          for (const expected of reference) {
            const bytes = module.FS.readFile('/output/tick-' + expected.tick + '.dat');
            const digest = await crypto.subtle.digest('SHA-256', bytes);
            const sha256 = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
            checkpoints.push({tick: expected.tick, bytes: bytes.length, sha256,
              matches: sha256 === expected.serializedStateSHA256});
          }
          const passed = code === 0 && checkpoints.every(c => c.matches);
          window.mapResult = {passed, exitCode: code, checkpoints, lines};
          status.textContent = passed ? 'Paridad exacta en los siete checkpoints.' : 'La prueba de paridad falló.';
        } catch (error) {
          window.mapResult = {passed: false, reason: String(error), lines};
          status.textContent = 'Error al comparar: ' + error;
        }
      }, 0);
    }
  });
} catch (error) {
  status.textContent = 'Error: ' + error;
  window.mapResult = {passed: false, reason: String(error), lines};
}
