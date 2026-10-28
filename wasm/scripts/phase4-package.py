"""Package the linked application and losslessly compress original archives."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--assets', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
asset_report = json.loads((args.assets / 'assets-report.json').read_text())
if asset_report['status'] != 'PACKAGED_NOT_RUNTIME_VERIFIED':
    raise SystemExit('Original archive build must finish before packaging.')
if not (args.output / 'pyrogenesis-application.wasm').is_file():
    raise SystemExit('Missing linked application.')
manifest = dict(files=[], pin=asset_report['pin'], archives={}, phase4Accepted=False)
for mod in ['mod', 'public']:
    destination = args.output / (mod + '.zip')
    source_archive = args.assets / asset_report['mods'][mod].get('archive', mod + '.zip')
    if not destination.exists():
        with zipfile.ZipFile(source_archive) as original, zipfile.ZipFile(
                destination.with_suffix('.zip.partial'), 'w', compression=zipfile.ZIP_DEFLATED,
                compresslevel=1, allowZip64=False) as compressed:
            for index, entry in enumerate(original.infolist()):
                payload = original.read(entry)
                compressed.writestr(entry.filename, payload)
                if index % 500 == 0:
                    print(mod, index, 'original files compressed', flush=True)
        destination.with_suffix('.zip.partial').rename(destination)
    # Every archived resource must retain exactly its original prepared bytes.
    hashes = {}
    with zipfile.ZipFile(source_archive) as original, zipfile.ZipFile(destination) as compressed:
        if original.namelist() != compressed.namelist():
            raise RuntimeError('Archive file lists diverge')
        for entry in original.infolist():
            left = hashlib.sha256(original.read(entry)).hexdigest()
            if left != hashlib.sha256(compressed.read(entry.filename)).hexdigest():
                raise RuntimeError('Resource bytes diverge: ' + entry.filename)
            hashes[entry.filename] = left
    (args.output / (mod + '-resource-hashes.json')).write_text(json.dumps(hashes, indent=2))
    manifest['archives'][mod] = dict(bytes=destination.stat().st_size, files=len(hashes),
                                    payloadIdentityVerified=True)
for name in ['config', 'l10n']:
    for source in sorted((args.assets / name).rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(args.assets).as_posix()
        destination = args.output / 'data' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest['files'].append(dict(path='/data/' + relative, url='data/' + relative))
icu = Path('/emsdk/upstream/emscripten/cache/ports/icu/icu/source/data/in/icudt68l.dat')
(args.output / 'data/icu').mkdir(parents=True, exist_ok=True)
shutil.copy2(icu, args.output / 'data/icu' / icu.name)
manifest['files'].append(dict(path='/data/icu/' + icu.name, url='data/icu/' + icu.name))
for name in ['application.html', 'application.mjs', 'application-pointer.mjs', 'application-failure.mjs', 'renderer-session.mjs', 'webgpu-engine.mjs', 'webgpu-border.mjs', 'webgpu-probe.html', 'webgpu-probe.mjs']:
    shutil.copy2(Path('/phase4-browser') / name, args.output / name)
shutil.copy2(args.output / 'application.html', args.output / 'index.html')
(args.output / 'application-data.json').write_text(json.dumps(manifest, indent=2))
print('APPLICATION_PACKAGED_NOT_RUNTIME_VERIFIED', flush=True)
