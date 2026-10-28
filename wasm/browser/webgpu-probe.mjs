import { openRendererSession } from './renderer-session.mjs';
const result = { scope: 'API_ACCESS_ONLY', engineBackendIntegrated: false, phase45Accepted: false, events: [] };
window.webgpuProbeResult = result;
const output = document.querySelector('#result');
const start = document.querySelector('#probe');
const close = document.querySelector('#dispose');
let session;
function record(event) {
  result.events.push(event);
  output.textContent = JSON.stringify(result, null, 2);
}
start.addEventListener('click', async () => {
  start.disabled = true;
  try {
    session = await openRendererSession({ canvas: document.querySelector('#canvas'),
      backend: 'webgpu', powerPreference: 'high-performance', report: record });
    await session.validationScope(() => {
      const encoder = session.device.createCommandEncoder();
      session.device.queue.submit([encoder.finish()]);
    });
    record({ type: 'empty-submission-completed' });
    close.disabled = false;
  } catch (error) {
    if (session) await session.dispose();
    record({ type: 'failed', message: error.message });
  }
});
close.addEventListener('click', async () => {
  close.disabled = true;
  try { await session.dispose(); record({ type: 'disposed' }); }
  catch (error) { record({ type: 'dispose-error', message: error.message }); }
});
