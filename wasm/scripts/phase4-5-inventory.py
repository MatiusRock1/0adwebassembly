"""Fingerprint the baseline and inventory original shader sources, without converting art.

The baseline manifest is a fingerprint, not a frozen copy. Pass --snapshot to
retain the full build separately. Existing snapshots are never overwritten.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if not (args.baseline / 'pyrogenesis-application.wasm').is_file():
        parser.error('Missing baseline application WASM')
    if args.snapshot:
        # copytree rejects an existing destination, including the source itself.
        if args.snapshot.resolve().is_relative_to(args.baseline.resolve()):
            parser.error('Snapshot must be outside the baseline directory')
        shutil.copytree(args.baseline, args.snapshot)
    baseline = args.snapshot or args.baseline
    args.output.mkdir(parents=True, exist_ok=True)
    files = {p.relative_to(baseline).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p))
             for p in sorted(baseline.rglob('*')) if p.is_file()}
    report = dict(scope='BASELINE_FINGERPRINT_NOT_ACCEPTANCE',
                  pin='40b8794eecb9618da69e10bacffa8814c561aa51',
                  generatedUTC=datetime.now(timezone.utc).isoformat(),
                  snapshotCreated=bool(args.snapshot), files=files, phase45Accepted=False)
    (args.output / 'webgl-baseline.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    shader_root = root / 'binaries/data/mods/mod/shaders'
    shaders = []
    for path in sorted(shader_root.rglob('*')):
        if not path.is_file():
            continue
        item = dict(path=path.relative_to(root).as_posix(), sha256=digest(path),
                    conversion='NOT_CONVERTED', variantsVerified=False)
        if path.suffix == '.xml':
            try:
                tree = ET.parse(path)
                item['declarations'] = [dict(tag=node.tag, attributes=node.attrib)
                                        for node in tree.iter() if node.attrib]
            except ET.ParseError as error:
                item['parseError'] = str(error)
        shaders.append(item)
    interfaces = []
    for path in sorted((root / 'source/renderer/backend').glob('*.h')):
        interfaces.append(dict(path=path.relative_to(root).as_posix(), sha256=digest(path),
                               webgpuImplementation='MISSING'))
    (args.output / 'renderer-inventory.json').write_text(json.dumps(dict(
        shaders=shaders, interfaces=interfaces, engineBackendIntegrated=False,
        note='Source inventory only; runtime define combinations and effect coverage remain unverified.'),
        indent=2), encoding='utf-8')
    print(f'Inventoried {len(files)} baseline files, {len(shaders)} shader files, {len(interfaces)} interfaces.')


if __name__ == '__main__':
    main()
