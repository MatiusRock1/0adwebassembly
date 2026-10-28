"""Merge verified native conversion parts and check complete input coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--assets', type=Path, required=True)
args = parser.parse_args()
out = args.assets
resume = json.loads((out / 'resume-report.json').read_text())
if resume['status'] != 'ORIGINAL_CONVERSION_BATCHES_COMPLETE_NOT_MERGED':
    raise SystemExit('Original conversion batches are incomplete')
parts = [out / 'parts/public-prefix.zip'] + [out / 'parts' / b['archive']
        for b in sorted(resume['batches'], key=lambda b: b['index'])]
hashes = {}
destination = out / 'public-complete.zip'
with zipfile.ZipFile(destination.with_suffix('.zip.partial'), 'w',
                     compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=False) as merged:
    for part in parts:
        print('Merging original part:', part.name, flush=True)
        with zipfile.ZipFile(part) as prepared:
            for entry in prepared.infolist():
                payload = prepared.read(entry)  # verifies each entry's CRC
                digest = hashlib.sha256(payload).hexdigest()
                if entry.filename in hashes:
                    if hashes[entry.filename] != digest:
                        raise RuntimeError('Conflicting original resources: ' + entry.filename)
                    continue
                hashes[entry.filename] = digest
                merged.writestr(entry.filename, payload)
destination.with_suffix('.zip.partial').rename(destination)

def expected(relative):
    path = Path(relative)
    if relative.startswith('art/meshes/') and path.suffix == '.dae':
        return relative + '.cached.pmd'
    if relative.startswith('art/animation/') and path.suffix == '.dae':
        return relative + '.cached.psa'
    if (relative.startswith(('art/textures/', 'fonts/'))
            and not relative.startswith(('art/textures/cursors/', 'art/textures/terrain/alphamaps/'))
            and path.suffix.lower() in ['.png', '.dds', '.tga', '.bmp']):
        return relative + '.cached.dds'
    return relative

public = Path('/build/0ad/binaries/data/mods/public')
missing = []
empty = []
for source in sorted(public.rglob('*')):
    if not source.is_file():
        continue
    relative = source.relative_to(public).as_posix()
    if not source.stat().st_size:
        empty.append(relative)  # original archive builder explicitly skips empty files
    elif expected(relative) not in hashes:
        missing.append(dict(source=relative, expected=expected(relative)))
(out / 'public-resource-hashes.json').write_text(json.dumps(hashes, indent=2))
report = json.loads((out / 'assets-report.json').read_text())
report.update(status='ASSET_COVERAGE_FAILED' if missing else 'PACKAGED_NOT_RUNTIME_VERIFIED',
              resumed=True, missing=missing, emptyInputsSkippedByOriginalBuilder=empty)
report['mods']['public'] = dict(archive=destination.name, files=len(hashes),
                               bytes=destination.stat().st_size, nativeParts=[p.name for p in parts])
for name in ['config', 'l10n']:
    shutil.copytree(Path('/build/0ad/binaries/data') / name, out / name, dirs_exist_ok=True)
(out / 'assets-report.json').write_text(json.dumps(report, indent=2))
print(report['status'], len(missing), 'missing original inputs', flush=True)
raise SystemExit(1 if missing else 0)
