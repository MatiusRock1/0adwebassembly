"""Recompile measured hot original SpiderMonkey units at O3, preserving ABI/math.

The cached library remains immutable. This produces a separately hashed archive;
all other members retain their original optimization. No VM/script source edits.
"""
import hashlib
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--optimization',choices=['O2','O3'],default='O3')
parser.add_argument('--portable',action='store_true',help='Optimize the measured portable interpreter unit from the verified separate build.')
parser.add_argument('--upstream-dispatch-fix',action='store_true',help='Backport the reviewed Mozilla D224659 enum assignment into an isolated source copy.')
parser.add_argument('--switch-dispatch',action='store_true',help='Adapt Mozilla D224656 switch dispatch, keeping original opcode bodies and interrupt checks.')
parser.add_argument('--call-underflow',action='store_true',help='Adapt only non-constructing argument-underflow handling from Mozilla D224676.')
parser.add_argument('--missing-cacheop-counts',action='store_true',help='Diagnostic-only counters for unsupported CacheIR opcodes; never a performance candidate.')
parser.add_argument('--pure-cacheir-guards',action='store_true',help='Private SM128-only handlers for undefined result, multiple shapes and non-dense index guard; preserve all other handlers and GC hooks.')
args=parser.parse_args()
assert not args.upstream_dispatch_fix or args.portable
assert not args.switch_dispatch or (args.portable and args.upstream_dispatch_fix)
assert not args.call_underflow or args.switch_dispatch
assert not args.missing_cacheop_counts or (args.switch_dispatch and not args.call_underflow)
assert not args.pure_cacheir_guards or (args.switch_dispatch and not args.call_underflow and not args.missing_cacheop_counts)
BASE=Path('/spike/mozjs-128.13.0/build-wasm/js/src')
ROOT=Path('/phase45-build/spidermonkey-portable/build/js/src') if args.portable else BASE
OUT=Path('/phase45-build/spidermonkey-'+('portable-guards-' if args.pure_cacheir_guards else 'portable-cache-count-' if args.missing_cacheop_counts else 'portable-underflow-' if args.call_underflow else 'portable-switch-' if args.switch_dispatch else 'portable-fixed-' if args.upstream_dispatch_fix else 'portable-hot-' if args.portable else 'hot-')+args.optimization.lower());OUT.mkdir(parents=True,exist_ok=True)
original=ROOT/'build/libjs_static.a'
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
archive_hash=digest(original)
input_provenance=None
if args.portable:
    input_provenance=json.loads(Path('/phase45-build/spidermonkey-portable/report.json').read_text())
    assert input_provenance['passed'] and not input_provenance['publicHeadersChanged']
    assert archive_hash==input_provenance['archiveSHA256'],'Portable build archive changed'
targets=['PortableBaselineInterpret.o'] if args.portable else ['Interpreter.o','Unified_cpp_js_src11.o','Unified_cpp_js_src15.o','Unified_cpp_js_src16.o','Unified_cpp_js_src20.o']
members=subprocess.check_output(['emar','t',str(original)],text=True).splitlines()
previous=json.loads((OUT/'report.json').read_text()) if (OUT/'report.json').exists() else {}
old={unit['target']:unit for unit in previous.get('units',[])}
report=dict(passed=False,phase45Accepted=False,originalArchiveSHA256=digest(BASE/'build/libjs_static.a'),
    inputArchiveSHA256=archive_hash,inputProvenance=input_provenance,
    optimization=args.optimization,scope='Only listed measured hot VM objects recompiled; remaining input archive objects unchanged. No JIT or source modifications.',units=[])
try:
    patched_source=None
    if args.upstream_dispatch_fix:
        patch=Path('/workspace/wasm/patches/upstream/mozjs-D224659.patch')
        metadata=json.loads(patch.with_suffix('.json').read_text())
        assert digest(patch)==metadata['SHA256']=='77757974a93f4061924c1b318ba93b0278a6d7dd2a1ece0aa51f1a8d65937e95'
        original_source=Path('/spike/mozjs-128.13.0/js/src/vm/PortableBaselineInterpret.cpp')
        before=original_source.read_text()
        start=before.index('#define PREDICT_NEXT(name)')
        end=before.index('#define PREDICT_RETURN()',start)
        macro=before[start:end]
        assert 'cacheop = CacheOp::name;' not in macro and macro.count('    goto cacheop_##name;')==1
        fixed=macro.replace('    goto cacheop_##name;', '    cacheop = CacheOp::name;                        '+chr(92)+'\n    goto cacheop_##name;',1)
        after=before[:start]+fixed+before[end:]
        if args.switch_dispatch:
            from phase45_portable_switch import adapt
            switch_patch=Path('/workspace/wasm/patches/upstream/mozjs-D224656.patch')
            switch_metadata=json.loads(switch_patch.with_suffix('.json').read_text())
            assert digest(switch_patch)==switch_metadata['SHA256']=='bf07c78038ebc5e64ab61308373d2d71adfda191fe2bd32110ab394d48ffcd67'
            after=adapt(after)
            report['switchDispatchPatch']=dict(**switch_metadata,opcodeHandlerBodiesUnchanged=True,interruptAndCoverageChecksPreserved=True)
        if args.call_underflow:
            from phase45_portable_underflow import adapt
            call_patch=Path('/workspace/wasm/patches/upstream/mozjs-D224676.patch')
            call_metadata=json.loads(call_patch.with_suffix('.json').read_text())
            assert digest(call_patch)==call_metadata['SHA256']=='1c0e2e85109d1f69d8db6d6eedd014a511ce2c7446f1b98232946d8d781f47c2'
            after=adapt(after)
            report['callUnderflowPatch']=call_metadata
        if args.pure_cacheir_guards:
            from phase45_portable_guards import adapt,SDK_INPUTS,OPS
            for relative,expected in SDK_INPUTS.items():
                assert digest(Path('/spike/mozjs-128.13.0/js/src')/relative)==expected,'Pinned guard semantics changed: '+relative
            after=adapt(after)
            report['guardHandlers']=dict(ops=OPS,sdkSourceSHA256=SDK_INPUTS,
                scope='Three pure SM128 handlers adapted from its native CacheIR compiler. Existing weak ShapeListObject GC hooks unchanged; only compare PrivateValue pointers. No allocation, time/script/AI/quality changes or new GC points.')
        if args.missing_cacheop_counts:
            from phase45_cacheir_counts import instrument
            after=instrument(after)
            report.update(diagnosticOnly=True,performanceAcceptance=False,
                missingCacheIROpCounts=True,counterScope='Only unsupported opcodes; handler/fallback semantics unchanged. Instrumented VM is not eligible for FPS acceptance.')
        patched_source=OUT/'PortableBaselineInterpret.cpp';patched_source.write_text(after)
        import difflib
        adapted_patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/js/src/vm/PortableBaselineInterpret.cpp',tofile='b/js/src/vm/PortableBaselineInterpret.cpp'))
        (OUT/('adapted-portable-underflow.patch' if args.call_underflow else 'adapted-portable-switch.patch' if args.switch_dispatch else 'adapted-D224659.patch')).write_text(adapted_patch)
        report['upstreamPatch']=dict(**metadata,originalSourceSHA256=digest(original_source),adaptedSourceSHA256=digest(patched_source),adaptedPatch=adapted_patch)
        report['scope']='Only portable interpreter object optimized and private source backport of Mozilla D224659; no original game/script or public header changes'
        if args.switch_dispatch:report['scope']='Only portable interpreter object optimized; private source adaptations of Mozilla D224659 and D224656 switch dispatch. Original opcode handlers, interrupts, coverage, game scripts and public headers preserved.'
        if args.call_underflow:report['scope']='Private SM128 interpreter copy with D224659, D224656 and only the non-constructing argument-underflow portion of D224676. Actual argc, constructor/cross-realm/spread fallbacks, other opcode bodies, interrupts, coverage, game scripts and public headers preserved.'
        if args.missing_cacheop_counts:report['scope']='Diagnostic-only private switch interpreter with atomic counts on unsupported CacheIR dispatch. All original opcode/fallback/GC/stack/interrupt behavior and headers retained; no FPS acceptance.'
        if args.pure_cacheir_guards:report['scope']='Private fixed/switch SM128 interpreter with only LoadUndefinedResult, GuardMultipleShapes and GuardIndexIsNotDenseElement implemented from pinned native semantics. Existing opcode bodies, weak-list GC hooks, fallbacks, stack, interrupts, public headers and original game content retained.'
    for target in targets:
        assert members.count(target)==1,('Original archive member missing/duplicated',target)
        dry=subprocess.run(['make','-n','-B',target],cwd=ROOT,capture_output=True,text=True,check=True)
        (OUT/(target+'.make-dry-run.txt')).write_text(dry.stdout)
        candidates=[]
        for line in dry.stdout.splitlines():
            if not line.startswith('/emsdk/upstream/emscripten/em++ '):continue
            command=shlex.split(line)
            if command[command.index('-o')+1]==target:candidates.append(command)
        assert len(candidates)==1,(target,len(candidates))
        original_command=candidates[0];command=list(original_command)
        assert command.count('-O')==1 and '-ffp-contract=off' in command
        assert not any(flag in command for flag in ['-ffast-math','-Ofast','-funsafe-math-optimizations'])
        command[command.index('-O')]='-'+args.optimization
        command[command.index('-o')+1]=str(OUT/target)
        command[command.index('-MF')+1]=str(OUT/(target+'.d'))
        command.insert(-1,'-g0')
        if args.switch_dispatch:command.insert(-1,'-Wno-unused-label')
        if patched_source:
            assert Path(command[-1]).name=='PortableBaselineInterpret.cpp'
            command[-1]=str(patched_source)
        source=Path(command[-1])
        if not source.is_absolute():source=ROOT/source
        sources=[source]
        if source.name.startswith('Unified_'):
            import re
            sources += [Path(path) for path in re.findall(r'^#include "([^"]+\.cpp)"',source.read_text(),re.MULTILINE)]
        hashes={str(path):digest(path) for path in sources}
        identity=hashlib.sha256(json.dumps(dict(command=command,sources=hashes,archive=archive_hash),sort_keys=True).encode()).hexdigest()
        cached=old.get(target,{})
        if cached.get('identity')==identity and cached.get('exitCode')==0 and (OUT/target).exists() and digest(OUT/target)==cached.get('objectSHA256'):
            report['units'].append(cached);print('CACHED',target,flush=True);continue
        start=time.monotonic()
        with (OUT/(target+'.log')).open('w') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        unit=dict(target=target,identity=identity,command=command,originalCommand=original_command,sourceSHA256=hashes,
            exitCode=result.returncode,seconds=time.monotonic()-start)
        if result.returncode==0:unit['objectSHA256']=digest(OUT/target)
        report['units'].append(unit)
        print('SCRIPTING_COMPILED',target,result.returncode,round(unit['seconds'],1),flush=True)
        assert result.returncode==0,('Compile failed; inspect log',target)
    temporary=OUT/'libjs_static.a.partial'
    shutil.copyfile(original,temporary)
    subprocess.run(['emar','rcs',str(temporary),*[str(OUT/target) for target in targets]],check=True)
    after=subprocess.check_output(['emar','t',str(temporary)],text=True).splitlines()
    assert sorted(after)==sorted(members),'Archive membership changed'
    temporary.replace(OUT/'libjs_static.a')
    report['archiveSHA256']=digest(OUT/'libjs_static.a')
    report['passed']=True
except Exception as error:
    report['failure']=str(error)
finally:
    (OUT/'report.json').write_text(json.dumps(report,indent=2))
print('SCRIPTING_HOT_'+args.optimization+'_BUILT_NOT_ACCEPTED' if report['passed'] else 'SCRIPTING_BUILD_FAILED',flush=True)
raise SystemExit(0 if report['passed'] else 1)
