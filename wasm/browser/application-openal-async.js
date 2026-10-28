// SDK 4.0.10 platform adaptation (WASM_AUDIO_ASYNC). The SDK runs OpenAL on the
// browser's main thread, and every AL call from a pthread waits for it there.
// Calls that only set source or listener state, or start, stop or pause a
// source, return nothing: send them without waiting. The main thread's proxy
// queue is first in, first out, so they still run before any later call from
// the same thread, including every query, buffer upload and deletion. Vector
// arguments point into the caller's memory: read their values here and send
// them by value. An error these calls raise is reported by a later alGetError.
addToLibrary({
  alSourcef__proxy: 'async',
  alSourcei__proxy: 'async',
  alSource3f__proxy: 'async',
  alSourcePlay__proxy: 'async',
  alSourceStop__proxy: 'async',
  alSourcePause__proxy: 'async',
  alListenerf__proxy: 'async',
  alListener3f__proxy: 'async',

  Phase45alInvalidValue__deps: ['$AL'],
  Phase45alInvalidValue__proxy: 'async',
  Phase45alInvalidValue: () => {
    if (AL.currentCtx) AL.currentCtx.err = 0xA003; // AL_INVALID_VALUE
  },

  // The SDK's alSourcefv reads three values for these parameters and one for
  // every other parameter, exactly as alSource3f and alSourcef do.
  alSourcefv__deps: ['alSource3f', 'alSourcef', 'Phase45alInvalidValue'],
  alSourcefv__proxy: 'none',
  alSourcefv: (sourceId, param, pValues) => {
    if (!pValues) return _Phase45alInvalidValue();
    switch (param) {
    case 0x1004 /* AL_POSITION */:
    case 0x1005 /* AL_DIRECTION */:
    case 0x1006 /* AL_VELOCITY */:
      return _alSource3f(sourceId, param, {{{ makeGetValue('pValues', '0', 'float') }}},
        {{{ makeGetValue('pValues', '4', 'float') }}}, {{{ makeGetValue('pValues', '8', 'float') }}});
    default:
      return _alSourcef(sourceId, param, {{{ makeGetValue('pValues', '0', 'float') }}});
    }
  },

  Phase45alListenerOrientation__deps: ['$AL'],
  Phase45alListenerOrientation__proxy: 'async',
  Phase45alListenerOrientation: (atX, atY, atZ, upX, upY, upZ) => {
    if (!AL.currentCtx) return;
    AL.paramArray[0] = atX; AL.paramArray[1] = atY; AL.paramArray[2] = atZ;
    AL.paramArray[3] = upX; AL.paramArray[4] = upY; AL.paramArray[5] = upZ;
    AL.setListenerParam('alListenerfv', 0x100F /* AL_ORIENTATION */, AL.paramArray);
  },

  // Position and velocity take three values, orientation six; alListener3f
  // reports any other parameter as the SDK's alListenerfv does.
  alListenerfv__deps: ['alListener3f', 'Phase45alListenerOrientation', 'Phase45alInvalidValue'],
  alListenerfv__proxy: 'none',
  alListenerfv: (param, pValues) => {
    if (!pValues) return _Phase45alInvalidValue();
    if (param === 0x100F /* AL_ORIENTATION */)
      return _Phase45alListenerOrientation(
        {{{ makeGetValue('pValues', '0', 'float') }}}, {{{ makeGetValue('pValues', '4', 'float') }}},
        {{{ makeGetValue('pValues', '8', 'float') }}}, {{{ makeGetValue('pValues', '12', 'float') }}},
        {{{ makeGetValue('pValues', '16', 'float') }}}, {{{ makeGetValue('pValues', '20', 'float') }}});
    return _alListener3f(param, {{{ makeGetValue('pValues', '0', 'float') }}},
      {{{ makeGetValue('pValues', '4', 'float') }}}, {{{ makeGetValue('pValues', '8', 'float') }}});
  }
});
