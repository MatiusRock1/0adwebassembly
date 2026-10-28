// Fatal SDK/worker errors must stop the owned runtime, audio and renderer.
// This boundary preserves the original error; it never restarts or hides it.
export function installApplicationFailureBoundary({eventTarget, runtimeURL,
  getApplication, releasePointer, disposeRenderer, onFailure, report}) {
  let completion;
  function abort(reason, fallbackModule) {
    if (completion) return completion;
    completion = Promise.resolve().then(async () => {
      const errors = [];
      let stopped;
      let released;
      try { stopped = (getApplication() || fallbackModule)?.stopAbortedApplication?.(); }
      catch (error) { errors.push(error); }
      // The SDK removes its input listeners synchronously before releasing
      // pointer lock can enqueue callbacks for the already dead pthread.
      try { released = releasePointer(); } catch (error) { errors.push(error); }
      try { await stopped; } catch (error) { errors.push(error); }
      try { await released; } catch (error) { errors.push(error); }
      try { await disposeRenderer(); } catch (error) { errors.push(error); }
      if (errors.length) throw new AggregateError(errors, 'Fatal runtime cleanup failed');
    });
    onFailure(String(reason), completion);
    completion.catch(error => report(error));
    return completion;
  }
  function onError(event) {
    const files = [event.filename, event.error?.filename].filter(Boolean);
    if (!files.some(file => {
      try { return new URL(file, runtimeURL).href === runtimeURL; }
      catch { return false; }
    })) return;
    abort(event.error?.message || event.message || 'Application worker failed');
  }
  eventTarget.addEventListener('error', onError);
  return {abort, dispose() { eventTarget.removeEventListener('error', onError); }};
}
