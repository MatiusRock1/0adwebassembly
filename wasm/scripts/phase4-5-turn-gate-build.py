"""Recompile a few units of an existing deferred-capture candidate with extra defines.

By default CCmpAIManager.cpp and TurnManager.cpp get -DWASM_AI_TURN_GATE=1 (the
AI turn gate). Each unit reruns its recorded command (same -O level, defines,
SIMD, exception and FP flags) plus the extra defines and a private include root
that takes precedence. Every other object, library and the dependency audit are
reused from the base.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

os.environ.update(EMCC_CORES='2', BINARYEN_CORES='2')
includes = Path('/tmp/phase4-includes'); includes.mkdir(exist_ok=True)
for name in ['boost', 'enet', 'libxml']:
    target = includes / name
    if not target.exists(): target.symlink_to(Path('/spike/headless/include') / name)
shutil.copytree('/spike/headless/include/fmt', includes / 'fmt', dirs_exist_ok=True)
fmt = includes / 'fmt/core.h'
fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))', 'parse_format_string<true>(str_, checker(str_, {}))'))

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', default='ai-deferred-capture-9-o3', help='Existing /phase45-build/application-<base> candidate.')
parser.add_argument('--variant', required=True, help='New output directory suffix; never reuse an existing candidate.')
parser.add_argument('--unit', action='append', help='Unit (relative to source/) to recompile; default: the turn-gate units.')
parser.add_argument('--header', action='append', default=[], help='Extra changed header (relative to source/) that must take precedence.')
parser.add_argument('--recorded-unit', action='append', default=[],
    help='Unit recompiled from its recorded (already patched) source, e.g. main.cpp, so that changed headers apply.')
parser.add_argument('--harness-header', action='append', default=[],
    help='Changed wasm/harness header copied to the private include root, where it takes precedence.')
parser.add_argument('--define', action='append', help='Extra NAME=VALUE definition; default: WASM_AI_TURN_GATE=1.')
parser.add_argument('--js-library', action='append', default=[],
    help='Platform JS library from wasm/browser added to the link, after those of the base.')
parser.add_argument('--diagnostic', action='store_true', help='Mark the candidate diagnostic only; never FPS evidence.')
args = parser.parse_args()
unit_names = args.unit or ['simulation2/components/CCmpAIManager.cpp', 'simulation2/system/TurnManager.cpp']
defines = args.define or ['WASM_AI_TURN_GATE=1']
base = Path('/phase45-build') / ('application-' + args.base)
out = Path('/phase45-build') / ('application-' + args.variant)
assert not (out / 'compile-report.json').exists(), 'Refusing to overwrite an existing candidate'
out.mkdir(exist_ok=True)
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
report = json.loads((base / 'compile-report.json').read_text())
assert report['status'] == 'COMPILE_PASSED_NOT_LINKED' and report.get('aiDeferredCapture') and not report.get('diagnosticOnly')
for unit in report['results']:
    assert unit['exitCode'] == 0 and digest(unit['object']) == unit['objectSHA256']
shutil.copytree(base / 'runtime-browser', out / 'runtime-browser', dirs_exist_ok=True)
for name in args.js_library:
    library = out / 'runtime-browser' / name
    library.write_bytes((Path('/workspace/wasm/browser') / name).read_bytes().replace(b'\r\n', b'\n'))
    report['additionalJSLibraries'] = report.get('additionalJSLibraries', []) + [dict(path=str(library), SHA256=digest(library))]


def scene_diagnostics(text):
    # The frozen tree carries phase2-scene-build.py's console markers; reapply
    # them so the only difference from the frozen unit is the workspace change.
    text = text.replace('#include "ObjectManager.h"', '#include "ObjectManager.h"\n#include <cstdio>')
    text = text.replace('m_QualityHook =', 'std::puts("SCENE_ACTOR_QUALITY_HOOK_BEGIN"); m_QualityHook =', 1)
    text = text.replace('m_VariantDiversityHook =', 'std::puts("SCENE_ACTOR_QUALITY_HOOK_END"); m_VariantDiversityHook =', 1)
    text = text.replace('if (!g_Xeromyces.AddValidator', 'std::puts("SCENE_ACTOR_VALIDATOR_BEGIN"); if (!g_Xeromyces.AddValidator', 1)
    text = text.replace('const int quality{g_ConfigDB.Get("max_actor_quality", 0)};', 'std::puts("SCENE_QUALITY_GET_BEGIN"); const int quality{g_ConfigDB.Get("max_actor_quality", 0)}; std::printf("SCENE_QUALITY_GET_END %d %d\\n",quality,int(m_QualityLevel));')
    text = text.replace('m_Simulation.Interpolate(0.f, 0.f, 0.f);', 'std::puts("SCENE_QUALITY_INTERPOLATE_BEGIN"); m_Simulation.Interpolate(0.f, 0.f, 0.f); std::puts("SCENE_QUALITY_INTERPOLATE_END");')
    return text


def sound_manager_platform(text):
    # The frozen tree carries phase4-application-patch.py's two Web Audio edits.
    def edit(old, new):
        assert text.count(old) == 1, old
        return text.replace(old, new)
    text = edit('void CSoundManager::RunHardwareDetection()\n{',
        'void CSoundManager::RunHardwareDetection()\n{\n'
        '#if defined(__EMSCRIPTEN__)\n'
        '\t// Web Audio exposes the active virtual device, not host-device enumeration.\n'
        '\tif (const ALCchar* name = alcGetString(m_Device, ALC_DEVICE_SPECIFIER))\n'
        '\t\tm_SoundCardNames = name;\n'
        '\tif (const ALchar* version = alGetString(AL_VERSION))\n'
        '\t\tm_OpenALVersion = version;\n'
        '\treturn;\n#endif')
    return edit('\tif (m_Context)\n\t\talcDestroyContext(m_Context);',
        '\tif (m_Context)\n\t{\n'
        '#if defined(__EMSCRIPTEN__)\n\t\talcMakeContextCurrent(nullptr);\n#endif\n'
        '\t\talcDestroyContext(m_Context);\n\t}')


FROZEN_TRANSFORMS = {'graphics/ObjectManager.cpp': scene_diagnostics, 'soundmanager/SoundManager.cpp': sound_manager_platform}

private = out / 'source'
helpers = ['AIDeferredStart.h', 'AITurnGate.h', 'AIGuestProfiler.h', 'AIMapKernels.h', 'AIWorkerMailbox.h',
           'AIWorkerScript.h', 'DeferredCommands.h', 'SimKernels.h', 'SimTiming.h']
headers = []
for relative in unit_names + args.header + ['simulation2/helpers/' + h for h in helpers]:
    dst = private / relative; dst.parent.mkdir(parents=True, exist_ok=True)
    # The Windows checkout may use CRLF; compile the same text the frozen tree used.
    text = (Path('/workspace/source') / relative).read_bytes().replace(b'\r\n', b'\n').decode()
    dst.write_bytes(FROZEN_TRANSFORMS.get(relative, lambda t: t)(text).encode())
    if dst.suffix == '.h': headers.append(dict(path=str(dst), SHA256=digest(dst)))
for name in args.harness_header:
    dst = private / name
    dst.write_bytes((Path('/workspace/wasm/harness') / name).read_bytes().replace(b'\r\n', b'\n'))
    headers.append(dict(path=str(dst), SHA256=digest(dst)))

units = {u['source']: u for u in report['results']}
failed = False
for relative in unit_names + args.recorded_unit:
    unit = units[relative]
    source = private / relative
    if relative in args.recorded_unit:
        # Quoted includes search the unit's own directory first; a private copy
        # lets the changed headers win over those next to the recorded source.
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(Path(unit['sourceFile']).read_bytes())
    target = out / (relative.replace('/', '_') + '.o')
    depfile = target.with_suffix('.d')
    command = list(unit['command'])
    command[command.index('-c') + 1] = str(source)
    command[command.index('-o') + 1] = str(target)
    # Quoted includes next to the recorded unit (frozen tree or an earlier private
    # copy with its changed headers) still resolve there.
    command[1:1] = [*('-D' + d for d in defines), '-I' + str(private), '-iquote', str(Path(unit['sourceFile']).parent)]
    log = out / (relative.replace('/', '_') + '.log')
    with log.open('w') as stream:
        result = subprocess.run(command + ['-MD', '-MF', str(depfile)], stdout=stream, stderr=subprocess.STDOUT)
    unit.update(command=command, sourceFile=str(source), sourceSHA256=digest(source), object=str(target), log=str(log),
                exitCode=result.returncode, baseObjectSHA256=unit['objectSHA256'])
    if result.returncode:
        failed = True; print(log.read_text()[-12000:], flush=True); continue
    unit['objectSHA256'] = digest(target)
    # Every private header that the unit includes must resolve to this candidate's copy.
    dependencies = depfile.read_text().replace('\\\n', ' ').split()
    for header in helpers + args.header + args.harness_header:
        resolved = [d for d in dependencies if d.endswith('/' + Path(header).name)]
        assert all(d.startswith(str(private)) for d in resolved), (relative, resolved)
    unit['resolvedPrivateHeaders'] = sorted(d for d in dependencies if d.startswith(str(private)))
report.update(aiTurnGate='WASM_AI_TURN_GATE=1' in defines, extraDefines=defines, recompiledUnits=unit_names + args.recorded_unit,
    extraHeaders=args.header + ['harness/' + h for h in args.harness_header],
    frozenTransforms=sorted(set(FROZEN_TRANSFORMS) & set(unit_names)),
    diagnosticOnly=bool(args.diagnostic), status='COMPILE_FAILED' if failed else 'COMPILE_PASSED_NOT_LINKED',
    platformExperiment=report.get('platformExperiment', '') + '-' + args.variant,
    additionalHeaders=report.get('additionalHeaders', []) + headers,
    buildScriptSHA256=digest(Path(__file__)), baseCompileReportSHA256=digest(base / 'compile-report.json'),
    unitRebuildBase=str(base),
    scope=report.get('scope', '') + ' Units ' + ', '.join(unit_names) + ' recompiled with ' + ', '.join(defines) +
        ('; diagnostic only, never FPS evidence.' if args.diagnostic else
         '; requires original-state parity and independent physical validation.'))
(out / 'compile-report.json').write_text(json.dumps(report, indent=2))
print(report['status'], flush=True)
raise SystemExit(1 if failed else 0)
