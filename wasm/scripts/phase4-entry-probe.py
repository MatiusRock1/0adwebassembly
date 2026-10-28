"""Diagnose native application compilation in the cached phase 3 container.

This is a compile probe, not an application target or acceptance test. It keeps
the cached source and objects intact and records failures instead of adding
replacement implementations. Run with network disabled and two CPU / 8 GiB.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/spike/phase2-source')
    adapters = Path('/spike/phase2-adapters')
    sm = Path('/spike/mozjs-128.13.0/build-wasm')
    args.output.mkdir(parents=True, exist_ok=True)
    sources = ['main.cpp', 'ps/GameSetup/GameSetup.cpp',
               'ps/GameSetup/Config.cpp', 'ps/GameSetup/Paths.cpp',
               'ps/VideoMode.cpp', 'gui/GUIManager.cpp',
               'gui/Scripting/JSInterface_GUIManager.cpp', 'i18n/L10n.cpp',
               'ps/Game.cpp', 'simulation2/system/LocalTurnManager.cpp',
               'simulation2/components/CCmpAIManager.cpp']
    flags = ['em++', '-std=c++20', '-pthread', '-fexceptions', '-O0',
             '-ferror-limit=5', '-DFMT_HEADER_ONLY', '-DNDEBUG',
             '-DCONFIG_ENABLE_PCH=0', '-DCONFIG2_AUDIO=0', '-DCONFIG2_NVTT=0',
             '-DCONFIG2_LOBBY=0', '-DCONFIG2_FILE_ENABLE_AIO=0',
             '-DCONFIG2_GLES=1', '-sUSE_SDL=2', '--use-port=zlib',
             '--use-port=libpng', '--use-port=freetype', '-I' + str(adapters),
             '-include', str(adapters / 'ps/Profiler2.h'), '-I' + str(root),
             '-include', '/spike/wasm/harness/scene-script-timing.h',
             '-I' + str(root / 'pch/scriptinterface'), '-I' + str(root / 'lib'),
             '-I/spike/headless/include', '-I' + str(sm / 'dist/include'),
             '-I' + str(root / 'third_party/glad/include')]

    def compile_unit(relative):
        source = root / relative
        name = relative.replace('/', '_')
        command = flags + ['-c', str(source), '-o', '/tmp/phase4-' + name + '.o']
        log_path = args.output / (name + '.log')
        with log_path.open('w', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        print(relative, result.returncode, flush=True)
        return dict(source=relative, sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    exitCode=result.returncode, log=log_path.name, command=command)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compile_unit, sources))
    report = dict(status='COMPILE_FAILED' if any(r['exitCode'] for r in results)
                  else 'COMPILE_PASSED_NOT_LINKED', jobs=2,
                  audioEnabled=False, applicationLinked=False,
                  applicationExecuted=False, phase4Accepted=False,
                  adapterHeaders={str(p.relative_to(adapters)):
                                  hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(adapters.rglob('*.h'))},
                  results=results)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(report['status'], flush=True)
    return 1 if any(r['exitCode'] for r in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
