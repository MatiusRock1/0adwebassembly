import createPyrogenesis from './pyrogenesis-browser.mjs';
const logs = [];
const start = performance.now();
let state;
let wasmMemoryBytes;
function report(code, error) {
  parent.postMessage({type: 'fixture-result', code, error, state, logs,
    wasmMemoryBytes, durationMs: performance.now() - start}, location.origin);
}
try {
  await createPyrogenesis({
    print(line) { logs.push(line); if (line.startsWith('{"scenario":')) state = line;
      if (line.startsWith('0ad-browser-wasm-memory-bytes=')) wasmMemoryBytes = Number(line.split('=')[1]); },
    printErr(line) { logs.push(line); },
    onExit(code) { report(code); },
    onAbort(reason) { report(-1, String(reason)); }
  });
} catch (error) { report(-1, String(error)); }
