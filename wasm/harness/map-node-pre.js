// Mount prepared local resources without replacing standard MEMFS streams.
Module['preRun'] = [() => {
  FS.mkdir('/data');
  for (const mod of ['mod', 'public']) {
    FS.mkdir('/data/' + mod);
    FS.mount(NODEFS, {root: '/build/0ad/binaries/data/mods/' + mod}, '/data/' + mod);
  }
  for (const path of ['/cache', '/scenario', '/output']) {
    FS.mkdir(path);
    FS.mount(NODEFS, {root: path}, path);
  }
}];
