"""Replace only curl's cached legacy setjmp object in a private archive."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def prepare():
    source=Path('/spike/phase4-deps/src/curl-8.5.0')
    original=Path('/spike/phase4-deps/prefix/lib/libcurl.a')
    out=Path('/phase45-build/native-deps/curl-wasm-sjlj');out.mkdir(parents=True,exist_ok=True)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(original)=='771762ffb275b44e2a1e635d090344b173f92820807ceaaf399a1d1b07052d04','Cached curl archive changed'
    obj=out/'libcurl_la-hostip.o';archive=out/'libcurl.a'
    command=['emcc','-DHAVE_CONFIG_H','-I'+str(source/'include'),'-I'+str(source/'lib'),'-DBUILDING_LIBCURL','-DCURL_STATICLIB',
        '-DCURL_HIDDEN_SYMBOLS','-pthread','-fvisibility=hidden','-O2','-Qunused-arguments','-Wno-pointer-bool-conversion',
        '-sSUPPORT_LONGJMP=wasm','-c',str(source/'lib/hostip.c'),'-o',str(obj)]
    report=dict(passed=False,command=command,originalArchiveSHA256=digest(original),
        sourceSHA256={str(p):digest(p) for p in [source/'lib/hostip.c',source/'lib/curl_config.h']},
        scope='Same configured curl 8.5.0, headers, feature defines and O2 flags. Only hostip.o longjmp handling changes; all other archive members are retained. Original cache remains unchanged.')
    try:
        with (out/'compile.log').open('w') as log:compiled=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        report['compileExitCode']=compiled.returncode
        assert compiled.returncode==0,'Native curl hostip compile failed'
        before=subprocess.check_output(['emar','t',str(original)],text=True).splitlines()
        assert before.count(obj.name)==1
        shutil.copyfile(original,archive)
        subprocess.run(['emar','rcs',str(archive),str(obj)],check=True)
        assert subprocess.check_output(['emar','t',str(archive)],text=True).splitlines()==before
        symbols=subprocess.check_output(['emnm','--undefined-only',str(obj)],text=True)
        (out/'undefined-symbols.txt').write_text(symbols)
        all_symbols=subprocess.check_output(['emnm',str(obj)],text=True)
        assert '__THREW__' not in symbols and '__c_longjmp' in all_symbols and '__wasm_longjmp' in symbols,'curl handler was not converted to native Wasm longjmp'
        report.update(passed=True,archive=str(archive),archiveSHA256=digest(archive),objectSHA256=digest(obj))
    except Exception as error:report['failure']=str(error)
    finally:(out/'report.json').write_text(json.dumps(report,indent=2))
    if not report['passed']:raise RuntimeError(report['failure'])
    return report


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
