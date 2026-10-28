// SDK 4.0.10 platform adaptation. With pthreads the SDK's emscripten_get_now
// reads performance.timeOrigin on every call. The time origin is fixed for the
// lifetime of each global (page or worker), so read it once per global. The
// returned values are identical; only one native getter call per read is saved.
addToLibrary({
  $Phase45TimeOrigin: 'performance.timeOrigin',
  emscripten_get_now__deps: ['$Phase45TimeOrigin'],
  emscripten_get_now: () => Phase45TimeOrigin + performance.now(),
});
