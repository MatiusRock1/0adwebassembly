"""Prepare an explicitly incomplete startup diagnostic while assets finish.

This package cannot close any phase 4 acceptance gate. Only CRC-verified native
entries are included, and missing resources remain errors in browser reports.
"""
import argparse
import json
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--assets', type=Path, required=True)
parser.add_argument('--linked', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
for name in ['pyrogenesis-application.mjs', 'pyrogenesis-application.wasm']:
    shutil.copy2(args.linked / name, args.output / name)
shutil.copy2(args.assets / 'mod.zip', args.output / 'mod.zip')
shutil.copy2(args.assets / 'parts/public-prefix.zip', args.output / 'public.zip')
manifest = dict(files=[], assetCoverageComplete=False, phase4Accepted=False,
                purpose='Original application startup diagnostic with verified archive prefix')
data = Path('/build/0ad/binaries/data')
for name in ['config', 'l10n']:
    for source in sorted((data / name).rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(data).as_posix()
        target = args.output / 'data' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest['files'].append(dict(path='/data/' + relative, url='data/' + relative))
icu = Path('/emsdk/upstream/emscripten/cache/ports/icu/icu/source/data/in/icudt68l.dat')
(args.output / 'data/icu').mkdir(parents=True, exist_ok=True)
shutil.copy2(icu, args.output / 'data/icu' / icu.name)
manifest['files'].append(dict(path='/data/icu/' + icu.name, url='data/icu/' + icu.name))
for name in ['application.html', 'application.mjs', 'application-pointer.mjs', 'application-failure.mjs', 'renderer-session.mjs', 'webgpu-engine.mjs', 'webgpu-border.mjs', 'webgpu-probe.html', 'webgpu-probe.mjs']:
    shutil.copy2(Path('/phase4-browser') / name, args.output / name)
shutil.copy2(args.output / 'application.html', args.output / 'index.html')
(args.output / 'application-data.json').write_text(json.dumps(manifest, indent=2))
print('INCOMPLETE_STARTUP_DIAGNOSTIC_PACKAGED', flush=True)
