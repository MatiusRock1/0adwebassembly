"""Compile the original application closure with real logging and profiling.

Executed inside the cached SDK image. Build output is separate from phase 3.
Failed units retain their diagnostics; no unresolved symbol is ignored.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', nargs='*')
    parser.add_argument('--audio', action='store_true')
    parser.add_argument('--report-name', default='compile-report.json')
    args = parser.parse_args()
    if Path(args.report_name).name != args.report_name:
        parser.error('Report name must be a filename')
    os.environ['EMCC_CORES'] = '2'
    os.environ['BINARYEN_CORES'] = '2'
    out = args.output
    root = out / 'source'
    includes = out / 'include'
    objects = out / 'objects'
    logs = out / 'logs'
    for folder in [includes, objects, logs]:
        folder.mkdir(parents=True, exist_ok=True)
    if not root.exists():
        shutil.copytree('/spike/phase2-source', root)
    build_version = out / 'build/build_version'
    build_version.mkdir(parents=True, exist_ok=True)
    shutil.copy2('/build/0ad/build/build_version/build_version.txt', build_version)
    container_includes = Path('/tmp/phase4-includes')
    container_includes.mkdir(exist_ok=True)
    for name in ['boost', 'enet', 'libxml']:
        (container_includes / name).symlink_to(Path('/spike/headless/include') / name)
    shutil.copytree('/spike/headless/include/fmt', container_includes / 'fmt')
    # Backport the relevant view-consistency correction from fmt upstream
    # 6797f0c39a4ef13061cbc3bb850c35af7428fdc4: the checker must use the
    # exact view being parsed, preserving compile-time format checking.
    fmt_core = container_includes / 'fmt/core.h'
    fmt_before = fmt_core.read_text()
    fmt_after = fmt_before.replace('parse_format_string<true>(str_, checker(s, {}))',
                                  'parse_format_string<true>(str_, checker(str_, {}))')
    if fmt_after == fmt_before:
        raise RuntimeError('Unexpected cached fmt version')
    fmt_core.write_text(fmt_after)
    (out / 'fmt-compatibility.json').write_text(json.dumps(dict(
        file='fmt/core.h', before=hashlib.sha256(fmt_before.encode()).hexdigest(),
        after=hashlib.sha256(fmt_after.encode()).hexdigest(),
        replacement='checker(s, {}) -> checker(str_, {})',
        upstream='https://github.com/fmtlib/fmt/commit/6797f0c39a4ef13061cbc3bb850c35af7428fdc4'), indent=2))
    # ICU headers must match the WASM port, never the native major-version ABI.
    subprocess.run([sys.executable, str(Path(__file__).with_name('phase4-application-patch.py')),
                    str(root), '--patch', str(out / 'application.patch')], check=True)
    # These are headers for compile diagnosis, not native libraries for linking.
    for source in ['/usr/include/x86_64-linux-gnu/curl', '/usr/include/sodium']:
        if Path(source).is_dir():
            shutil.copytree(source, includes / Path(source).name, dirs_exist_ok=True)
    if Path('/usr/include/sodium.h').exists():
        shutil.copy2('/usr/include/sodium.h', includes / 'sodium.h')
    workspaces = Path('/build/0ad/build/workspaces/gcc')
    projects = ['engine', 'graphics', 'gui', 'network', 'scriptinterface',
                'simulation2', 'tinygettext', 'rlinterface', 'lowlevel', 'atlas']
    units = {}
    for project in projects:
        text = (workspaces / (project + '.make')).read_text()
        for relative in re.findall(r'\.\./\.\./\.\./source/([^\s"\n]+\.(?:cpp|c))', text):
            if '/tests/' not in relative and (root / relative).is_file():
                units[relative] = project
    # Native manifests include architecture/platform-specific files. Browser
    # replacements are supplied separately, never compiled as x86 native code.
    excluded = {p: group for p, group in units.items()
                if p.startswith(('lib/sysdep/arch/', 'lib/sysdep/os/',
                                 'lib/sysdep/rtl/', 'renderer/backend/vulkan/'))}
    for p in excluded:
        del units[p]
    units['lib/sysdep/os/unix/ufilesystem.cpp'] = 'lowlevel'
    units['lib/sysdep/os/unix/unuma.cpp'] = 'lowlevel'
    units['lib/sysdep/rtl/gcc/gcc.cpp'] = 'lowlevel'
    units['main.cpp'] = 'application'
    units['third_party/glad/src/gles2.cpp'] = 'gladwrapper'
    units['lobby/Globals.cpp'] = 'lobby'
    units['lobby/scripting/JSInterface_Lobby.cpp'] = 'lobby'
    httplib = out / 'source/wasm-httplib.cpp'
    shutil.copy2('/build/0ad/libraries/source/cpp-httplib/build/out/httplib.cc', httplib)
    units['wasm-httplib.cpp'] = 'cpp-httplib'
    platform = out / 'source/wasm-application-platform.cpp'
    shutil.copy2('/phase4-harness/application-platform.cpp', platform)
    units['wasm-application-platform.cpp'] = 'browser-platform'
    flags = ['em++', '-std=c++20', '-pthread', '-fexceptions', '-O2',
             '-ffunction-sections', '-fdata-sections', '-ferror-limit=4',
             '-DFMT_HEADER_ONLY', '-DNDEBUG', '-DCONFIG_ENABLE_PCH=0',
             '-DCONFIG2_AUDIO=' + str(int(args.audio)), '-DCONFIG2_NVTT=0', '-DCONFIG2_LOBBY=0',
             '-DCONFIG2_MINIUPNPC=0', '-DCONFIG2_DAP_INTERFACE=0',
             '-DCONFIG2_FILE_ENABLE_AIO=0', '-DCONFIG2_GLES=1',
             '-sUSE_SDL=2', '--use-port=zlib', '--use-port=libpng',
             '--use-port=freetype', '--use-port=icu', '-I' + str(root), '-I' + str(root / 'lib'),
             '-I' + str(root / 'pch/engine'), '-I' + str(container_includes), '-I' + str(includes),
             '-I' + str(root / 'third_party/tinygettext/include'),
             '-I/build/0ad/libraries/source/cpp-httplib/include',
             '-I/spike/phase4-deps/prefix/include',
             '-I/phase4-harness',
             '-I/spike/mozjs-128.13.0/build-wasm/dist/include',
             '-I' + str(root / 'third_party/glad/include'),
             '-include', '/spike/wasm/harness/scene-script-timing.h']
    if args.audio:
        flags += ['--use-port=ogg', '--use-port=vorbis']
    previous_path = out / args.report_name
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    results = {r['source']: r for r in previous.get('results', [])}

    def compile_unit(item):
        relative, project = item
        source = root / relative
        name = relative.replace('/', '_')
        obj = objects / (name + '.o')
        # SpiderMonkey is built without RTTI; its GUI proxy subclasses must
        # use the same setting rather than require absent BaseProxy typeinfo.
        extra = ['-fno-rtti'] if relative == 'gui/Scripting/JSInterface_GUIProxy.cpp' else []
        command = flags + extra + ['-c', str(source), '-o', str(obj)]
        dependencies = b''
        if relative == 'main.cpp':
            dependencies = Path('/phase4-harness/application-clock.h').read_bytes()
        identity = hashlib.sha256(source.read_bytes() + dependencies + json.dumps(command).encode()).hexdigest()
        old = results.get(relative)
        if old and old.get('identity') == identity and old['exitCode'] == 0 and obj.exists():
            return old
        started = time.monotonic()
        log = logs / (name + '.log')
        with log.open('w') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        print(relative, result.returncode, flush=True)
        return dict(source=relative, project=project, identity=identity,
                    exitCode=result.returncode, object=str(obj), log=str(log),
                    seconds=time.monotonic() - started)

    selected = {p: g for p, g in units.items() if not args.only or p in args.only}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(compile_unit, sorted(selected.items())):
            results[result['source']] = result
            previous_path.write_text(json.dumps(dict(
                status='IN_PROGRESS', jobs=2, audioEnabled=args.audio,
                headlessServiceAdapters=False, excludedNativePlatformUnits=excluded,
                results=list(results.values())), indent=2))
    failed = [p for p, r in results.items() if r['exitCode']]
    missing = sorted(set(units) - set(results))
    report = dict(status='COMPILE_FAILED' if failed else
                  ('PARTIAL_COMPILE' if missing else 'COMPILE_PASSED_NOT_LINKED'),
                  jobs=2, audioEnabled=args.audio, applicationLinked=False,
                  headlessServiceAdapters=False, excludedNativePlatformUnits=excluded,
                  failed=failed, notAttempted=missing, results=list(results.values()))
    previous_path.write_text(json.dumps(report, indent=2))
    print(report['status'], len(results) - len(failed), 'passed;', len(failed), 'failed', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
