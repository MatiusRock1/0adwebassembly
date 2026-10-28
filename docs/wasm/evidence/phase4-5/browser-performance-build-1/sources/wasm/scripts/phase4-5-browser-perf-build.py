"""Combine SIMD with dedicated GPU/I/O workers and parallel WebGL compilation."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

started=time.monotonic()
base=Path('/phase45-build/application-simd')
out=Path('/phase45-build/application-browser-perf');out.mkdir(exist_ok=True)
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
report=json.loads((base/'compile-report.json').read_text())
assert report['status']=='COMPILE_PASSED_NOT_LINKED' and report['simdEngine']
assert len(report['results'])==483 and report['dependencyAudit']['passed']
roots={'source':Path(report['frozenSourceRoot']),'harness':Path(report['frozenHarnessRoot'])}
for unit in report['results']:
    assert unit['exitCode']==0 and '-msimd128' in unit['command']
    assert digest(Path(unit['object']))==unit['objectSHA256']
    source=Path(unit.get('sourceFile',roots['source']/unit['source']))
    assert digest(source)==unit['sourceSHA256']
shutil.copytree(base/'runtime-browser',out/'runtime-browser',dirs_exist_ok=True)
includes=Path('/tmp/phase4-includes');includes.mkdir(exist_ok=True)
for name in ['boost','enet','libxml']:
    target=includes/name
    if not target.exists():target.symlink_to(Path('/spike/headless/include')/name)
shutil.copytree('/spike/headless/include/fmt',includes/'fmt',dirs_exist_ok=True)
fmt=includes/'fmt/core.h'
fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))','parse_format_string<true>(str_, checker(str_, {}))'))
private=out/'source'
backend=private/'renderer/backend/webgpu'
shutil.copytree(roots['source']/'renderer/backend/webgpu',backend,dirs_exist_ok=True)
for relative in ['renderer/backend/gl/BrowserShaderCompile.h','lib/file/io/browser_archives.h']:
    destination=private/relative;destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path('/workspace/source')/relative,destination)
    report.setdefault('additionalHeaders',[]).append(dict(path=str(destination),SHA256=digest(destination)))

changes={'renderer/backend/webgpu/Device.cpp':'WASM_WEBGPU_RENDER_WORKER',
         'lib/file/io/io.cpp':'WASM_BROWSER_ARCHIVES',
         'renderer/backend/gl/ShaderProgram.cpp':'WASM_PARALLEL_SHADER_COMPILE'}
patches=[]
for relative,feature in changes.items():
    source=private/relative;source.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path('/workspace/source')/relative,source)
    original=roots['source']/relative
    patches.append(''.join(difflib.unified_diff(original.read_text().splitlines(True),source.read_text().splitlines(True),fromfile='a/'+relative,tofile='b/'+relative)))
    index=next(i for i,unit in enumerate(report['results']) if unit['source']==relative)
    command=list(report['results'][index]['command'])
    target=out/(relative.replace('/','_')+'.o')
    command[command.index('-c')+1]=str(source);command[command.index('-o')+1]=str(target)
    command[command.index('-c'):command.index('-c')]=['-D'+feature,'-iquote',str(original.parent)]
    log=target.with_suffix('.log')
    with log.open('w') as stream:compiled=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    result=dict(source=relative,sourceFile=str(source),sourceSHA256=digest(source),command=command,
                object=str(target),log=str(log),exitCode=compiled.returncode)
    if not compiled.returncode:result['objectSHA256']=digest(target)
    report['results'][index]=result
    print('BROWSER_PERF_COMPILE',relative,compiled.returncode,flush=True)
    if compiled.returncode:break
report['failed']=[unit['source'] for unit in report['results'] if unit['exitCode']]
report.update(status='COMPILE_FAILED' if report['failed'] else 'COMPILE_PASSED_NOT_LINKED',
              browserPerformanceFeatures=True,platformExperiment='combined-browser-performance',
              buildScriptSHA256=digest(Path(__file__)),baseCompileReportSHA256=digest(base/'compile-report.json'),
              seconds=time.monotonic()-started,phase45Accepted=False,
              scope='Combined candidate: all 483 SIMD engine units, O3 reference VM, '
                    'dedicated render worker/shared payload acknowledgements, bounded persistent archive reads, '
                    'and WebGL parallel program polling. Original resources, simulation and graphics retained. '
                    'Asyncify and IDBFS are enabled by the separate combined link action.')
(out/'browser-perf.patch').write_text(''.join(patches))
(out/'compile-report.json').write_text(json.dumps(report,indent=2))
print(report['status'],flush=True)
raise SystemExit(1 if report['failed'] else 0)
