"""Reject cached legacy exception/setjmp handlers before a native-EH link."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def audit(paths):
    result=dict(passed=True,files=[],scope='Undefined-symbol audit of cached C/C++ dependencies. Native-EH engine objects and SDK-selected native-EH system ports are built separately; the cached Rust archive uses panic=abort.')
    pattern=re.compile(r'\b(?:_?setjmp|sigsetjmp|__sigsetjmp|saveSetjmp|testSetjmp|emscripten_setjmp|__wasm_setjmp|__cxa_find_matching_catch_\d+)\b')
    for path in paths:
        path=Path(path)
        run=subprocess.run(['emnm','--undefined-only','--print-file-name',str(path)],capture_output=True,text=True)
        if run.returncode:raise RuntimeError('Cannot audit '+str(path)+': '+run.stderr[-1000:])
        hits=[line.strip() for line in run.stdout.splitlines() if pattern.search(line)]
        native=[]
        if hits:
            all_run=subprocess.run(['emnm','--print-file-name',str(path)],capture_output=True,text=True)
            if all_run.returncode:raise RuntimeError('Cannot inspect tags in '+str(path)+': '+all_run.stderr[-1000:])
            all_symbols=all_run.stdout
            tag_members={line.rsplit(':',1)[0] for line in all_symbols.splitlines() if re.search(r'\b[WwDd] __c_longjmp$',line)}
            legacy_members={line.rsplit(':',1)[0] for line in run.stdout.splitlines() if '__THREW__' in line}
            native=[line for line in hits if '__cxa_find_matching_catch_' not in line and line.rsplit(':',1)[0] in tag_members-legacy_members]
            hits=[line for line in hits if line not in native]
        result['files'].append(dict(path=str(path),SHA256=hashlib.sha256(path.read_bytes()).hexdigest(),legacyHandlers=hits,nativeLongjmpHandlers=native))
        if hits:result['passed']=False
    return result


def dependencies(scripting,curl=None):
    base=Path('/spike/mozjs-128.13.0/build-wasm')
    return [Path('/spike/xml-wasm/lib/libxml2.a'),Path(scripting),base/'build/pure_virtual/libpure_virtual.a',
        Path('/spike/phase4-deps/prefix/lib/libenet.a'),Path(curl) if curl else Path('/spike/phase4-deps/prefix/lib/libcurl.a'),Path('/spike/phase4-deps/prefix/lib/libsodium.a'),
        *sorted(path for folder in ['mfbt','mozglue','memory'] for path in (base/folder).rglob('*.o'))]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scripting',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=audit(dependencies(args.scripting));args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(passed=report['passed'],files=len(report['files']),handlers=[row for row in report['files'] if row['legacyHandlers']]),indent=2))
    raise SystemExit(0 if report['passed'] else 1)
