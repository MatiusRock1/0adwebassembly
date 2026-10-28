"""Build the original SpiderMonkey's optional portable baseline interpreter.

Keep the cached VM untouched. Reuse it only if exported headers remain identical;
otherwise require an explicit ABI review/rebuild rather than silently mixing APIs.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

SOURCE=Path('/spike/mozjs-128.13.0')
BASE=SOURCE/'build-wasm'
OUT=Path('/phase45-build/spidermonkey-portable');OUT.mkdir(parents=True,exist_ok=True)
BUILD=OUT/'build'
BUILD.mkdir(parents=True,exist_ok=True)
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
configuration=(BASE/'.mozconfig').read_text().replace('MOZ_OBJDIR='+str(BASE),'MOZ_OBJDIR='+str(BUILD))
configuration+='\nac_add_options --enable-portable-baseline-interp\nac_add_options --enable-portable-baseline-interp-force\nac_add_options --disable-debug-symbols\n'
configuration+='export CFLAGS="-pthread"\nexport CXXFLAGS="-pthread"\nexport LDFLAGS="-pthread"\n'
config=OUT/'mozconfig';config.write_text(configuration)
base_config=json.loads((BASE/'.mozconfig.json').read_text())['mozconfig']
options=base_config['configure_args']+['--enable-portable-baseline-interp','--enable-portable-baseline-interp-force','--disable-debug-symbols']
# This standalone tarball's generated old-configure checks a source path
# relative to the project root, although its executable lives in js/src.
# Anchor that generated build script to the unchanged real source root.
old_directory=OUT/'configure-adapter/js/src';old_directory.mkdir(parents=True,exist_ok=True)
for name in ['old-configure.in','aclocal.m4']:shutil.copy2(SOURCE/'js/src'/name,old_directory/name)
old_original=(SOURCE/'js/src/old-configure').read_text()
assert old_original.count('ac_unique_file=js/src/jsapi.h')==1
old_adapted=old_original.replace('ac_unique_file=js/src/jsapi.h','ac_unique_file=js/src/jsapi.h\nsrcdir='+str(SOURCE),1)
old_script=old_directory/'old-configure';old_script.write_text(old_adapted)
env=dict(os.environ,MOZCONFIG=str(config),MOZBUILD_STATE_PATH='/spike/mozbuild-state',
    PYTHON3='/spike/mozbuild-state/srcdirs/mozjs-128.13.0-284d488c35db/_virtualenvs/build/bin/python',
    RUSTFLAGS='-Ctarget-feature=+atomics -Ctarget-feature=+bulk-memory -Ctarget-feature=+mutable-globals -Cpanic=abort',
    CARGO_NET_OFFLINE='true',EMCC_CORES='2',BINARYEN_CORES='2')
env.update(base_config['env']['added'])
env.update(CFLAGS='-pthread',CXXFLAGS='-pthread',LDFLAGS='-pthread',OLD_CONFIGURE=str(old_script))
report=dict(passed=False,phase45Accepted=False,originalArchiveSHA256=digest(BASE/'js/src/build/libjs_static.a'),
    scope='Same SpiderMonkey source/version, official portable baseline interpreter enabled and forced, no native JIT or game/script edits',
    configure=configuration,sourceSHA256={str(path):digest(path) for path in [SOURCE/'js/moz.configure',SOURCE/'js/src/vm/PortableBaselineInterpret.cpp',SOURCE/'js/src/vm/PortableBaselineInterpret.h']})
report['buildStorage']='Case-sensitive Linux Docker volume 0ad-phase45-spidermonkey-portable; only verified archive and reports exported to Windows workspace'
report['generatedConfigureAdapter']=dict(originalSHA256=hashlib.sha256(old_original.encode()).hexdigest(),adaptedSHA256=digest(old_script),change='Explicit unchanged source root before old-configure source detection')
def run(command,name,cwd=SOURCE):
    report[name+'Command']=command
    start=time.monotonic()
    with (OUT/(name+'.log')).open('w') as log:result=subprocess.run(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
    report[name+'ExitCode']=result.returncode;report[name+'Seconds']=time.monotonic()-start
    (OUT/'report.json').write_text(json.dumps(report,indent=2))
    print('PORTABLE_SCRIPTING',name,result.returncode,round(report[name+'Seconds'],1),flush=True)
    if result.returncode:raise RuntimeError(name+' failed; see '+str(OUT/(name+'.log')))
def headers(directory):
    return {str(path.relative_to(directory)):digest(path) for path in directory.rglob('*') if path.is_file() and path.suffix in ('.h','.hpp','.inc','.msg')}
try:
    previous=Path('/portable-previous')
    if not (BUILD/'config.status').exists() and previous.exists():
        for name in ['release','wasm32-unknown-emscripten']:
            if (previous/name).is_dir():
                shutil.copytree(previous/name,BUILD/name,dirs_exist_ok=True)
        print('PORTABLE_SCRIPTING_REUSED_RUST_CACHE',flush=True)
    run([env['PYTHON3'],str(SOURCE/'configure.py'),*options],'configure',cwd=BUILD)
    run(['make','-j2'],'build',cwd=BUILD)
    previous=headers(BASE/'dist/include');current=headers(BUILD/'dist/include')
    changed=[name for name in sorted(set(previous)|set(current)) if previous.get(name)!=current.get(name)]
    report['publicHeadersChanged']=changed
    report['publicHeadersSHA256']=hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest()
    assert not changed,('Public headers changed; review ABI before linking',changed)
    defines=(BUILD/'js/src/js-confdefs.h').read_text()
    assert '#define ENABLE_PORTABLE_BASELINE_INTERP 1' in defines
    assert '#define ENABLE_PORTABLE_BASELINE_INTERP_FORCE 1' in defines
    assert '#define JS_CODEGEN_NONE 1' in defines
    archive=BUILD/'js/src/build/libjs_static.a';temporary=OUT/'libjs_static.a.partial'
    shutil.copyfile(archive,temporary);temporary.replace(OUT/'libjs_static.a')
    report['archiveSHA256']=digest(OUT/'libjs_static.a')
    report['passed']=True
except Exception as error:report['failure']=str(error)
finally:(OUT/'report.json').write_text(json.dumps(report,indent=2))
print('PORTABLE_SCRIPTING_BUILT_NOT_ACCEPTED' if report['passed'] else 'PORTABLE_SCRIPTING_BUILD_FAILED',flush=True)
raise SystemExit(0 if report['passed'] else 1)
