const status = document.querySelector('#status');
const log = document.querySelector('#log');
const run = document.querySelector('#run');
const download = document.querySelector('#download');
let evidence;
const capable = crossOriginIsolated && typeof SharedArrayBuffer !== 'undefined' && typeof WebAssembly !== 'undefined';
status.textContent = capable ? 'Listo. Cada ciclo usa un iframe nuevo y destruye su m?dulo al terminar.' : 'Se requiere WebAssembly, SharedArrayBuffer y aislamiento COOP/COEP. Usa el servidor indicado por HTTP localhost.';
run.disabled = !capable;
function cycle() {
  return new Promise((resolve, reject) => {
    const frame = document.createElement('iframe');
    frame.hidden = true;
    let timer;
    const cleanup = () => { clearTimeout(timer); removeEventListener('message', receive); frame.remove(); };
    const receive = event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow || event.data?.type !== 'fixture-result') return;
      cleanup(); resolve(event.data);
    };
    addEventListener('message', receive);
    timer = setTimeout(() => { cleanup(); reject(new Error('Timeout de 120 segundos')); }, 120000);
    frame.src = './fixture.html'; document.body.append(frame);
  });
}
run.onclick = async () => {
  run.disabled = true; download.disabled = true; log.textContent = '';
  evidence = {browser: navigator.userAgent, crossOriginIsolated, cycles: [], started: new Date().toISOString()};
  try {
    const response = await fetch('./native-state.json');
    if (!response.ok) throw new Error('Falta la referencia nativa');
    const expected = (await response.text()).trim();
    for (let i = 0; i < 10; ++i) {
      status.textContent = `Ejecutando ciclo ${i + 1}/10?`;
      const result = await cycle(); evidence.cycles.push(result);
      log.textContent += `Ciclo ${i + 1}: salida ${result.code}, ${result.durationMs.toFixed(0)} ms\n${result.logs.join('\n')}\n`;
      if (result.code !== 0 || result.error || result.state !== expected) throw new Error(`Fallo o divergencia en ciclo ${i + 1}`);
    }
    evidence.status = 'TEN_CYCLES_PARITY_PASSED';
    status.textContent = 'Diez ciclos coinciden con la referencia nativa. Memoria y workers requieren inspecci?n adicional.';
  } catch (error) { evidence.status = 'FAILED'; evidence.error = String(error); status.textContent = String(error); }
  finally { run.disabled = false; download.disabled = false; }
};
download.onclick = () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(evidence, null, 2)], {type: 'application/json'}));
  const a = document.createElement('a'); a.href = url; a.download = 'browser-evidence.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
