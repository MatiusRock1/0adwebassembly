import test from 'node:test';
import assert from 'node:assert/strict';
import {WorkerPresentation} from '../browser/webgpu-worker-present.mjs';

function fixture(overrides={}){
  let frame,timer,time=0;
  const cancelled=[];
  const presentation=new WorkerPresentation({
    requestFrame:callback=>{frame=callback;return 11;},
    cancelFrame:id=>cancelled.push(['frame',id]),
    postFallback:callback=>{timer=callback;return 22;},
    cancelFallback:id=>cancelled.push(['timer',id]),now:()=>time,...overrides});
  return {presentation,cancelled,raf:()=>frame(16.7),fallback:()=>timer(),advance:ms=>{time+=ms;}};
}

test('draw and acknowledgement happen once in rAF, despite late callbacks',async()=>{
  const f=fixture(),events=[];
  const pending=f.presentation.present(()=>{events.push('draw');return 7;});
  pending.then(()=>events.push('ack'));
  assert.deepEqual(events,[]);f.advance(12);f.raf();
  assert.deepEqual(events,['draw']);assert.equal(await pending,7);
  f.fallback();f.raf();assert.deepEqual(events,['draw','ack']);
  assert.equal(f.presentation.stats.rafPresents,1);
  assert.equal(f.presentation.stats.backgroundFallbackPresents,0);
  assert.equal(f.presentation.stats.maxWaitMilliseconds,12);
  assert.ok(f.cancelled.some(([kind,id])=>kind==='timer'&&id===22));
});

test('fallback cancels rAF and cannot present twice when rAF resumes',async()=>{
  const f=fixture();let draws=0;
  const pending=f.presentation.present(()=>++draws);
  f.advance(250);f.fallback();await pending;f.raf();
  assert.equal(draws,1);assert.equal(f.presentation.stats.backgroundFallbackPresents,1);
  assert.equal(f.presentation.stats.rafPresents,0);
  assert.deepEqual(f.cancelled,[['frame',11],['timer',22]]);
});

test('a second outstanding present is rejected rather than sharing a callback',async()=>{
  const f=fixture();let draws=0;
  const first=f.presentation.present(()=>++draws);
  await assert.rejects(f.presentation.present(()=>++draws),/already pending/);
  f.raf();await first;
  const second=f.presentation.present(()=>++draws);f.raf();await second;
  assert.equal(draws,2);assert.equal(f.presentation.stats.lastFrameId,2);
});

test('draw failure propagates and permits the next frame without counting success',async()=>{
  const f=fixture(),error=new Error('GPU validation');
  const pending=f.presentation.present(()=>{throw error;});f.raf();
  await assert.rejects(pending,value=>value===error);f.fallback();
  assert.equal(f.presentation.stats.failedPresents,1);assert.equal(f.presentation.stats.rafPresents,0);
  const next=f.presentation.present(()=>3);f.raf();assert.equal(await next,3);
});

test('scheduler failure cancels any registered rAF and rejects',async()=>{
  const f=fixture({postFallback:()=>{throw new Error('timer unavailable');}});
  await assert.rejects(f.presentation.present(()=>assert.fail('late draw')),/timer unavailable/);
  f.raf();assert.deepEqual(f.cancelled,[['frame',11]]);
  assert.equal(f.presentation.stats.failedPresents,1);
});

test('missing worker rAF fails explicitly',async()=>{
  const f=fixture({requestFrame:()=>{throw new Error('rAF unavailable');}});
  await assert.rejects(f.presentation.present(()=>assert.fail('draw')),/rAF unavailable/);
  assert.equal(f.presentation.pending,null);
});

test('dispose cancels pending work and rejects future frames',async()=>{
  const f=fixture();let draws=0;
  const pending=f.presentation.present(()=>++draws);
  f.presentation.dispose();f.presentation.dispose();
  await assert.rejects(pending,/disposed/);f.raf();f.fallback();
  await assert.rejects(f.presentation.present(()=>++draws),/disposed/);
  assert.equal(draws,0);assert.equal(f.presentation.stats.cancelledPresents,1);
});

test('asynchronous final draw is rejected and not counted as a presentation',async()=>{
  const f=fixture();
  const pending=f.presentation.present(()=>Promise.reject(new Error('late failure')));
  f.raf();await assert.rejects(pending,/must be synchronous/);
  assert.equal(f.presentation.stats.failedPresents,1);assert.equal(f.presentation.stats.lastFrameId,0);
});

function pacedFixture(){
  const callbacks=[];let timer,time=0;
  const presentation=new WorkerPresentation({
    requestFrame:callback=>{callbacks.push(callback);return callbacks.length;},
    cancelFrame:()=>{},postFallback:callback=>{timer=callback;return 1;},cancelFallback:()=>{},now:()=>time});
  const buffer=new SharedArrayBuffer(64),words=new Int32Array(buffer),times=new Float64Array(buffer);
  const pacing={words,times,address:8,intervalMs:1000/30};
  // Deliver one display signal to every callback requested so far.
  const signal=timestamp=>{time=timestamp;for(const callback of callbacks.splice(0))callback(timestamp);};
  return {presentation,pacing,signal,words,times,fallback:at=>{time=at;timer();}};
}
const published=f=>({count:f.words[2],time:f.times[2+(f.words[2]&1)]});

test('paced presents publish their count and display signal for the engine clock',async()=>{
  const f=pacedFixture();
  const first=f.presentation.present(()=>1,f.pacing);f.signal(1000);await first;
  assert.deepEqual(published(f),{count:1,time:1000});
  const second=f.presentation.present(()=>2,f.pacing);
  f.signal(1000+1000/60);
  assert.equal(f.presentation.stats.lastFrameId,1,'one refresh after the previous present is too early');
  f.signal(1000+2000/60);assert.equal(await second,2);
  assert.deepEqual(published(f),{count:2,time:1000+2000/60});
  assert.equal(f.presentation.stats.pacedHolds,1);
  assert.deepEqual(f.presentation.stats.pacedIntervals,[0,1,0,0,0]);
});

test('a late paced frame moves the cadence instead of letting the next one catch up',async()=>{
  const f=pacedFixture(),refresh=1000/60;
  const first=f.presentation.present(()=>1,f.pacing);f.signal(0);await first;
  // Ready only after its interval: shown three refreshes after the previous one.
  const late=f.presentation.present(()=>2,f.pacing);f.signal(3*refresh);await late;
  const next=f.presentation.present(()=>3,f.pacing);
  f.signal(4*refresh);assert.equal(f.presentation.stats.lastFrameId,2);
  f.signal(5*refresh);await next;
  assert.deepEqual(published(f),{count:3,time:5*refresh});
  assert.deepEqual(f.presentation.stats.pacedIntervals,[0,1,1,0,0]);
});

test('paced presents accept signal jitter but never two frames in one cap interval',async()=>{
  const f=pacedFixture(),refresh=1000/60;let draws=0;
  let signalTime=0;
  for(let frame=0;frame<120;++frame){
    const pending=f.presentation.present(()=>++draws,f.pacing);
    // A 60 Hz display with ±0.5 ms timestamp jitter; frames are always ready early.
    for(let tries=0;tries<4&&draws===frame;++tries){
      signalTime+=refresh+(tries%2?0.5:-0.5);f.signal(signalTime);
    }
    await pending;
  }
  assert.equal(draws,120);
  assert.equal(f.presentation.stats.pacedIntervals[1],119,'every interval is two refreshes');
});

test('a hidden page presents paced frames from the fallback timer',async()=>{
  const f=pacedFixture();
  const first=f.presentation.present(()=>1,f.pacing);f.signal(10);await first;
  const hidden=f.presentation.present(()=>2,f.pacing);f.fallback(270);await hidden;
  assert.deepEqual(published(f),{count:2,time:270});
  assert.equal(f.presentation.stats.backgroundFallbackPresents,1);
});

test('unpaced presents keep the original behaviour and publish nothing',async()=>{
  const f=pacedFixture();
  const first=f.presentation.present(()=>1);f.signal(10);await first;
  const second=f.presentation.present(()=>2);f.signal(11);await second;
  assert.equal(f.words[2],0);assert.equal(f.presentation.stats.pacedPresents,0);
  assert.equal(f.presentation.stats.pacedHolds,0);
});
