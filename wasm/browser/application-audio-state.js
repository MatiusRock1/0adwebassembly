// Diagnostics reference the real SDK OpenAL contexts and decoded buffers.
// Record the original worker exception before the SDK's main-thread ErrorEvent
// loses its stack. Keep the default error propagation and shutdown unchanged.
if (ENVIRONMENT_IS_PTHREAD) {
  globalThis.addEventListener('error', event => {
    console.error(JSON.stringify({type:'application-worker-error',message:event.message,
      stack:event.error?.stack || '',filename:event.filename,line:event.lineno,column:event.colno}));
  });
}
Module['getOriginalAudioState'] = () => ({
  contexts: Object.values(AL.contexts).map(context => ({
    id: context.id,
    state: context.audioCtx.state,
    sampleRate: context.audioCtx.sampleRate,
    sources: Object.values(context.sources).length,
    gain: context.gain.gain.value,
    playingSources: Object.values(context.sources).filter(source => source.state === 0x1012).length
  })),
  decodedBuffers: Object.values(AL.buffers).filter(buffer => buffer.audioBuf).map(buffer => {
    const audio = buffer.audioBuf;
    const samples = audio.getChannelData(0);
    let nonzero = 0;
    for (let index = 0; index < samples.length; index += 64)
      if (Math.abs(samples[index]) > 0.00001) nonzero++;
    return {frames: audio.length, channels: audio.numberOfChannels,
      sampleRate: audio.sampleRate, nonzeroSamples: nonzero};
  }),
  closed: Module['audioLifecycle'] || []
});
Module['resumeOriginalAudio'] = () => Promise.all(Object.values(AL.contexts).map(context => context.audioCtx.resume()));
Module['getApplicationWorkerState'] = () => ({
  running: PThread.runningWorkers.map(worker => worker.workerID),
  pooled: PThread.unusedWorkers.map(worker => worker.workerID),
  pthreads: Object.keys(PThread.pthreads)
});
// Controlled lifecycle test only: exercise the SDK's actual worker-error
// handler and the launcher's fatal boundary without a host/native crash.
Module['triggerApplicationWorkerErrorForTest'] = () => {
  if (ENVIRONMENT_IS_PTHREAD || ENV.PHASE4_AUTOMATION !== '1')
    throw new Error('Worker failure test requires the automation launcher');
  const worker=PThread.runningWorkers[0];
  if (!worker) throw new Error('No owned application worker is running');
  worker.onerror(new ErrorEvent('error',{message:'Controlled SDK worker failure',filename:import.meta.url}));
};
// A fatal WASM abort cannot run the original C++ destructors. Stop only this
// application's clock/workers and audio; normal exits retain native teardown.
Module['stopAbortedApplication'] = async () => {
  const clock=Module.applicationClock;
  if(clock){clock.running=false;cancelAnimationFrame(clock.raf);clearInterval(clock.hiddenTimer);}
  JSEvents.removeAllEventListeners();
  PThread.terminateAllThreads();
  await Promise.all(Object.values(AL.contexts).map(context=>context.audioCtx.close().catch(()=>{})));
  AL.contexts={};AL.buffers={};
  Module.abortCleanupComplete=true;
};
