// Platform-only extension of the SDK 4.0.10 OpenAL destruction path. Preserve
// its context validation and bookkeeping, and close the browser audio device.
addToLibrary({
  alcDestroyContext__deps: ['$AL'],
  alcDestroyContext__proxy: 'sync',
  alcDestroyContext(contextId) {
    const context = AL.contexts[contextId];
    if (!context || AL.currentCtx === context) {
      AL.alcErr = 0xA002; // ALC_INVALID_CONTEXT
      return;
    }
    if (context.interval) clearInterval(context.interval);
    const lifecycle = { contextId, state: context.audioCtx.state, closing: true };
    (Module['audioLifecycle'] ||= []).push(lifecycle);
    context.audioCtx.close().then(() => {
      lifecycle.state = context.audioCtx.state;
      lifecycle.closing = false;
    }).catch(error => {
      lifecycle.error = String(error);
      lifecycle.closing = false;
      err(`OpenAL device close failed: ${error}`);
    });
    AL.deviceRefCounts[context.deviceId]--;
    delete AL.contexts[contextId];
    AL.freeIds.push(contextId);
  }
});
