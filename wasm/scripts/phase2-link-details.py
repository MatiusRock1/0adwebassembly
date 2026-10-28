"""Export the entire unresolved-symbol inventory without rerunning compiles."""
import json
import subprocess
from pathlib import Path
out = Path('/spike/phase2-link')
report = json.loads((out / 'report.json').read_text())
sm = Path('/spike/mozjs-128.13.0/build-wasm')
support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
libraries = [str(sm / 'js/src/build/libjs_static.a'), str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'),
             str(sm / 'build/pure_virtual/libpure_virtual.a')]
with (out / 'link-full.log').open('w') as log:
    result = subprocess.run(['em++', '-pthread', '-fexceptions', '-Wl,--gc-sections', '-Wl,--error-limit=0',
          '--use-port=zlib', '-sUSE_SDL=2', *[r['object'] for r in report['compile']], *libraries, *support,
          '-o', str(out / 'map-link.js')], stdout=log, stderr=subprocess.STDOUT)
report['fullDiagnosticLinkExitCode'] = result.returncode
report['unresolvedErrors'] = sum('wasm-ld: error:' in line for line in (out / 'link-full.log').read_text().splitlines())
(out / 'report.json').write_text(json.dumps(report, indent=2))
(out / 'madvise-poison-source.txt').write_text(Path('/spike/mozjs-128.13.0/mfbt/Poison.cpp').read_text())
for candidate in Path('/emsdk/upstream/emscripten/src').rglob('*.js'):
    content = candidate.read_text()
    if '__syscall_madvise' in content:
        lines = content.splitlines()
        fragments = []
        for index, line in enumerate(lines):
            if '__syscall_madvise' in line:
                fragments += lines[max(0, index-5):index+10]
        (out / ('madvise-sdk-' + candidate.name + '.txt')).write_text('\n'.join(fragments))
print('FULL_LINK_DIAGNOSTIC', result.returncode, report['unresolvedErrors'])
