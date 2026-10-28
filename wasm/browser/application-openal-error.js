// SDK 4.0.10 platform adaptation. Only AL's error word is shared: all sound
// creation, playback, timing and parameters retain their original SDK paths.
// Bit 16 marks a current context; the SDK's AL error enums fit in 16 bits.
addToLibrary({
  $Phase45AudioErrorState__deps: ['Phase45OpenALErrorAddress'],
  $Phase45AudioErrorState: {
    active: null,
    records: null,
    indexCache: 0,
    index() {
      return this.indexCache ||= _Phase45OpenALErrorAddress() >>> 2;
    },
    attach(context) {
      this.records ||= new WeakMap();
      let record = this.records.get(context);
      if (record) return record;
      record = { value: context.err };
      this.records.set(context, record);
      const state = this;
      Object.defineProperty(context, 'err', {
        configurable: true,
        enumerable: true,
        get() {
          return state.active === context
            ? Atomics.load(HEAP32, state.index()) & 0xffff : record.value;
        },
        set(value) {
          if (state.active === context)
            Atomics.store(HEAP32, state.index(), 0x10000 | value);
          else record.value = value;
        }
      });
      return record;
    },
    select(context) {
      context ||= null;
      // Re-selecting a context must not reintroduce an error concurrently
      // consumed by a reader between a snapshot and an exchange.
      if (context === this.active) return;
      const next = context ? 0x10000 | this.attach(context).value : 0;
      const previous = Atomics.exchange(HEAP32, this.index(), next);
      if (this.active) this.records.get(this.active).value = previous & 0xffff;
      this.active = context;
    },
    take() {
      const index = this.index();
      for (;;) {
        const previous = Atomics.load(HEAP32, index);
        if (!(previous & 0x10000)) return 0xa004; // AL_INVALID_OPERATION
        if (Atomics.compareExchange(HEAP32, index, previous, 0x10000) === previous)
          return previous & 0xffff;
      }
    }
  },
  // 'none' is the SDK's explicit non-proxied mode. The shared word is the
  // same for every pthread; no worker-local copy of AL.currentCtx is read.
  alGetError__deps: ['$Phase45AudioErrorState'],
  alGetError__proxy: 'none',
  alGetError() {
    return Phase45AudioErrorState.take();
  },
  alcMakeContextCurrent__deps: ['$AL', '$Phase45AudioErrorState'],
  alcMakeContextCurrent__proxy: 'sync',
  alcMakeContextCurrent(contextId) {
    // Exactly the SDK's context selection and return value. Publish with one
    // exchange, retaining each inactive context's unconsumed error separately.
    AL.currentCtx = contextId === 0 ? null : AL.contexts[contextId];
    Phase45AudioErrorState.select(AL.currentCtx);
    return 1; // ALC_TRUE
  }
});
