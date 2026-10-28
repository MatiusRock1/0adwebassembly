// OffscreenCanvas publishes its bitmap at the worker's rendering opportunity.
// Present exactly once in that callback; never replace or drop an engine frame.
// A paced present (engine built with WASM_PRESENT_PACING) is also held until the
// display signal of its interval, at least one cap interval after the previous
// paced present, and is then published to the engine's frame clock.
const REFRESH_60HZ_MS=1000/60;
// Display signals are vsync aligned; this only absorbs timestamp jitter. It is
// below every refresh period up to 240 Hz, so a signal one refresh before the
// interval ends never passes and the cap holds.
export const PACING_TOLERANCE_MS=2;

export class WorkerPresentation {
  constructor({requestFrame=callback=>globalThis.requestAnimationFrame(callback),
    cancelFrame=id=>globalThis.cancelAnimationFrame(id),
    postFallback=callback=>setTimeout(callback,250),cancelFallback=id=>clearTimeout(id),
    now=()=>performance.now()}={}){
    this.requestFrame=requestFrame;this.cancelFrame=cancelFrame;
    this.postFallback=postFallback;this.cancelFallback=cancelFallback;
    this.now=now;this.pending=null;this.disposed=false;
    this.deadline=-Infinity;this.lastPaced=undefined;
    this.stats={rafPresents:0,backgroundFallbackPresents:0,failedPresents:0,
      cancelledPresents:0,totalWaitMilliseconds:0,maxWaitMilliseconds:0,lastFrameId:0,
      // Paced presents, display signals skipped because the frame was early, and
      // intervals between paced presents in 60 Hz refreshes (1, 2, 3, 4, 5+).
      pacedPresents:0,pacedHolds:0,pacedIntervals:[0,0,0,0,0]};
  }
  present(draw,pacing=null){
    if(this.disposed)return Promise.reject(new Error('Presentation disposed'));
    if(this.pending)return Promise.reject(new Error('Presentation already pending'));
    return new Promise((resolve,reject)=>{
      let done=false,frame,timer;
      const started=this.now();
      const cleanup=()=>{
        if(frame!==undefined)this.cancelFrame(frame);
        if(timer!==undefined)this.cancelFallback(timer);
        this.pending=null;
      };
      this.pending=()=>{
        if(done)return;done=true;cleanup();
        this.stats.cancelledPresents++;
        reject(new Error('Presentation disposed'));
      };
      const fail=error=>{done=true;cleanup();this.stats.failedPresents++;reject(error);};
      const run=(raf,timestamp)=>{
        if(done)return;
        if(raf&&pacing&&timestamp<this.deadline-PACING_TOLERANCE_MS){
          // Ready early: keep it for the display signal of its own interval.
          this.stats.pacedHolds++;
          try{frame=this.requestFrame(next=>run(true,next));}catch(error){fail(error);}
          return;
        }
        done=true;cleanup();
        const wait=this.now()-started;
        this.stats.totalWaitMilliseconds+=wait;
        this.stats.maxWaitMilliseconds=Math.max(this.stats.maxWaitMilliseconds,wait);
        try{
          const result=draw();
          // Acquiring the canvas texture and submitting must stay in this task.
          if(result&&typeof result.then==='function'){
            Promise.resolve(result).catch(()=>{});
            throw new Error('Presentation draw must be synchronous');
          }
          this.stats[raf?'rafPresents':'backgroundFallbackPresents']++;
          this.stats.lastFrameId++;
          if(pacing)this.publish(pacing,raf?timestamp:this.now());
          resolve(result);
        }catch(error){this.stats.failedPresents++;reject(error);}
      };
      try{
        frame=this.requestFrame(timestamp=>run(true,timestamp));
        // Hidden/occluded windows may stop rAF. Keep the game closable there;
        // this branch is counted and cannot certify a foreground FPS window.
        timer=this.postFallback(()=>run(false));
      }catch(error){fail(error);}
    });
  }
  // The next paced frame is shown no earlier than one cap interval after this
  // signal. A late frame moves the cadence instead of letting the next frame
  // catch up one refresh later.
  publish({words,times,address,intervalMs},signal){
    this.deadline=signal+intervalMs;
    if(this.lastPaced!==undefined){
      const refreshes=Math.round((signal-this.lastPaced)/REFRESH_60HZ_MS);
      this.stats.pacedIntervals[Math.min(Math.max(refreshes,1),5)-1]++;
    }
    this.lastPaced=signal;this.stats.pacedPresents++;
    const index=address>>>2,count=(Atomics.load(words,index)+1)|0;
    times[(address>>>3)+1+(count&1)]=signal;
    Atomics.store(words,index,count);
    Atomics.notify(words,index);
  }
  dispose(){this.disposed=true;this.pending?.();}
}
