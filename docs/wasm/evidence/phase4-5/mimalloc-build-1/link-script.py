"""Link the real application; undefined symbols and compile failures are fatal."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--release', action='store_true', help='Optimize without debug DWARF; preserve the diagnostic build separately.')
parser.add_argument('--spidermonkey-library',type=Path,help='Explicit separately built archive, with a passing provenance report and verified hash.')
parser.add_argument('--exception-mode',choices=['legacy','wasm'],default='legacy')
parser.add_argument('--asyncify',action='store_true',help='Enable stack suspension support in the combined browser candidate; preserve the reference separately.')
parser.add_argument('--jspi',action='store_true',help='Use WebAssembly promise integration for suspension with native Wasm exceptions.')
parser.add_argument('--allocator',choices=['dlmalloc','mimalloc'],default='dlmalloc',help='Explicit system allocator; compare separately under identical engine objects.')
args = parser.parse_args()
if args.asyncify and (args.jspi or args.exception_mode=='wasm'):
    parser.error('Classic ASYNCIFY cannot be combined with native Wasm exceptions or JSPI; use --jspi for the native-EH candidate.')
os.environ['EMCC_CORES'] = '2'
os.environ['BINARYEN_CORES'] = '2'
report = json.loads((args.build / 'compile-report.json').read_text())
if report['status'] != 'COMPILE_PASSED_NOT_LINKED' or not report['audioEnabled']:
    raise SystemExit('Full application closure must compile with audio before linking.')
assert report.get('exceptionMode','legacy')==args.exception_mode,'Engine object exception mode differs from link mode'
args.output.mkdir(parents=True, exist_ok=True)
sm = Path('/spike/mozjs-128.13.0/build-wasm')
scripting_library=sm/'js/src/build/libjs_static.a'
scripting_report=None
if args.spidermonkey_library:
    scripting_report=json.loads(args.spidermonkey_library.with_name('report.json').read_text())
    assert scripting_report['passed'] and hashlib.sha256(args.spidermonkey_library.read_bytes()).hexdigest()==scripting_report['archiveSHA256'],'Unverified scripting archive'
    assert hashlib.sha256(scripting_library.read_bytes()).hexdigest()==scripting_report['originalArchiveSHA256'],'Scripting base archive changed'
    scripting_library=args.spidermonkey_library
support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
curl_library=Path('/spike/phase4-deps/prefix/lib/libcurl.a')
dependency_audit=None
if args.exception_mode=='wasm':
    assert all('-fwasm-exceptions' in r['command'] for r in report['results']),'A legacy engine object entered the native-EH closure'
    assert all(hashlib.sha256(Path(r['object']).read_bytes()).hexdigest()==r['objectSHA256'] for r in report['results']),'A native-EH engine object changed after compilation'
    audited_scripting=[r for r in report['dependencyAudit']['files'] if Path(r['path']).name=='libjs_static.a']
    assert len(audited_scripting)==1 and audited_scripting[0]['SHA256']==hashlib.sha256(scripting_library.read_bytes()).hexdigest(),'The scripting archive differs from the compiled candidate audit'
    curl=report['nativeCurl'];curl_library=Path(curl['archive'])
    assert curl['passed'] and hashlib.sha256(curl_library.read_bytes()).hexdigest()==curl['archiveSHA256']
    from phase45_exception_audit import audit,dependencies
    dependency_audit=audit(dependencies(scripting_library,curl_library))
    assert dependency_audit['passed'],'Legacy dependency handlers entered the native-EH link'
libraries = ['/spike/xml-wasm/lib/libxml2.a', str(scripting_library),
             str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'),
             str(sm / 'build/pure_virtual/libpure_virtual.a'),
             '/spike/phase4-deps/prefix/lib/libenet.a',
             str(curl_library),
             '/spike/phase4-deps/prefix/lib/libsodium.a']
optimization = ['-O3'] if args.release else ['-O2', '-g', '-gseparate-dwarf']
exception_flags=['-fwasm-exceptions','-sSUPPORT_LONGJMP=wasm'] if args.exception_mode=='wasm' else ['-fexceptions']
runtime_browser=args.build/'runtime-browser' if args.exception_mode=='wasm' else Path('/phase4-browser')
additional_js=[]
for header in report.get('additionalHeaders',[]):
    assert hashlib.sha256(Path(header['path']).read_bytes()).hexdigest()==header['SHA256'],'Private platform header changed after preparation'
for library in report.get('additionalJSLibraries',[]):
    assert hashlib.sha256(Path(library['path']).read_bytes()).hexdigest()==library['SHA256'],'Platform JS changed after preparation'
    additional_js+=['--js-library',library['path']]
command = ['em++', *optimization, '-pthread', *exception_flags, '-Wl,--gc-sections',
           '-sMALLOC='+args.allocator,
           '-Wl,--error-limit=0', '-Wl,--threads=2', '--emit-symbol-map',
           '--use-port=zlib', '--use-port=libpng', '--use-port=freetype',
           '--use-port=icu', '--use-port=ogg', '--use-port=vorbis', '-lopenal', '-sUSE_SDL=2',
           *[r['object'] for r in report['results']], *libraries, *support,
           '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=536870912',
           '-sMAXIMUM_MEMORY=4294967296', '-sSTACK_SIZE=5242880', '-sASSERTIONS=' + ('0' if args.release else '2'),
           '-sEXIT_RUNTIME=1', '-sENVIRONMENT=web,worker', '-sMODULARIZE=1', '-sEXPORT_ES6=1',
           '-sMIN_WEBGL_VERSION=2', '-sMAX_WEBGL_VERSION=2', '-sFULL_ES3=1',
           '-sOFFSCREEN_FRAMEBUFFER=1', '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=8',
           '-sFORCE_FILESYSTEM=1',
           '-sEXPORTED_RUNTIME_METHODS=["FS","ENV","ccall","addRunDependency","removeRunDependency","abort"]',
           '--js-library', str(runtime_browser/'application-openal.js'),
           *additional_js,
           '--post-js', str(runtime_browser/'application-audio-state.js'),
           '-o', str(args.output / 'pyrogenesis-application.mjs')]
if report.get('simdEngine'):
    assert all('-msimd128' in unit['command'] for unit in report['results'])
    command.insert(1, '-msimd128')
if report.get('browserPerformanceFeatures'):
    command.insert(1, '-lidbfs.js')
    command=[value.replace('"removeRunDependency","abort"]','"removeRunDependency","abort","IDBFS"]') for value in command]
if args.asyncify:
    command[1:1]=['-sASYNCIFY=1','-sASYNCIFY_STACK_SIZE=1048576']
if args.jspi:
    command.insert(1,'-sJSPI=1')
with (args.build / 'application-link.log').open('w') as stream:
    result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
linked = dict(exitCode=result.returncode, command=command, audioEnabled=True, profile='release' if args.release else 'diagnostic',
              headlessServiceAdapters=False, applicationExecuted=False,
              phase4Accepted=False)
linked['exceptionMode']=args.exception_mode
linked['allocator']=args.allocator
linked['simdEngine']=bool(report.get('simdEngine'))
linked['browserPerformanceFeatures']=bool(report.get('browserPerformanceFeatures'))
linked['aiWorker']=bool(report.get('aiWorker'))
linked['fineScriptTiming']=report.get('fineScriptTiming',True)
linked['generatedBufferUploads']=bool(report.get('generatedBufferUploads'))
linked['asyncify']=args.asyncify
linked['asyncSuspension']='jspi' if args.jspi else 'asyncify' if args.asyncify else 'none'
linked['diagnosticOnly']=bool(report.get('diagnosticOnly') or (scripting_report or {}).get('diagnosticOnly'))
linked['aiGuestProfiler']=bool(report.get('aiGuestProfiler'))
linked['aiMapKernels']=bool(report.get('aiMapKernels'))
linked['denseAISnapshot']=bool(report.get('denseAISnapshot'))
linked['longjmpMode']='wasm' if args.exception_mode=='wasm' else 'emscripten'
linked['additionalJSLibraries']=report.get('additionalJSLibraries',[])
linked['inputCompileReportSHA256']=hashlib.sha256((args.build/'compile-report.json').read_bytes()).hexdigest()
if dependency_audit:linked['dependencyAudit']=dependency_audit
linked['scriptingArchive']=dict(path=str(scripting_library),SHA256=hashlib.sha256(scripting_library.read_bytes()).hexdigest(),provenance=scripting_report)
if not result.returncode:
    linked['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in args.output.iterdir()
                           if p.is_file() and p.name.startswith('pyrogenesis-application.')}
    linked['artifactScope'] = 'Linker outputs only; original asset hashes are recorded by phase4-assets.py.'
(args.output / 'link-report.json').write_text(json.dumps(linked, indent=2))
if not args.release:
    (args.build / 'link-report.json').write_text(json.dumps(linked, indent=2))
print('APPLICATION_LINK_PASSED_NOT_EXECUTED' if not result.returncode else 'APPLICATION_LINK_FAILED', flush=True)
raise SystemExit(result.returncode)
