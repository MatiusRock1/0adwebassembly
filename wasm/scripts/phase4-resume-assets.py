"""Recover complete native ZIP entries by CRC and finish in bounded batches.

The interrupted ZIP is never mounted. Only complete, CRC-verified entries are
rewritten into a valid archive; remaining inputs use the original converter.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile
import zlib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--batch-size', type=int, default=256)
args = parser.parse_args()
out = args.output
root = Path('/build/0ad')
public = root / 'binaries/data/mods/public'
parts = out / 'parts'
parts.mkdir(exist_ok=True)
parts.chmod(0o777)
prefix = parts / 'public-prefix.zip'
recovery = out / 'prefix-recovery.json'
if not prefix.exists():
    recovered = {}
    with (out / 'public.zip').open('rb') as source, zipfile.ZipFile(
            prefix.with_suffix('.zip.partial'), 'w', compression=zipfile.ZIP_DEFLATED,
            compresslevel=1, allowZip64=False) as destination:
        while True:
            start = source.tell()
            header = source.read(30)
            if len(header) != 30:
                break
            signature, version, flags, method, time, date, crc, packed, unpacked, name_length, extra_length = struct.unpack('<IHHHHHIIIHH', header)
            if signature != 0x04034B50:
                break
            if flags & 8 or method not in [0, 8]:
                raise RuntimeError('Cannot verify this native ZIP entry layout')
            name = source.read(name_length).decode('utf-8')
            source.read(extra_length)
            data = source.read(packed)
            if len(data) != packed:
                break
            payload = zlib.decompress(data, -15) if method == 8 else data
            if len(payload) != unpacked or zlib.crc32(payload) & 0xFFFFFFFF != crc:
                raise RuntimeError('Interrupted ZIP checksum mismatch: ' + name)
            destination.writestr(name, payload)
            recovered[name] = hashlib.sha256(payload).hexdigest()
            if len(recovered) % 1000 == 0:
                print('CRC-verified original entries:', len(recovered), flush=True)
        boundary = source.tell()
    prefix.with_suffix('.zip.partial').rename(prefix)
    recovery.write_text(json.dumps(dict(status='PREFIX_VERIFIED_NOT_COMPLETE_MOD',
                        files=recovered, interruptedArchiveBytes=(out / 'public.zip').stat().st_size,
                        completeBoundary=start, inspectedBoundary=boundary), indent=2))
names = set(json.loads(recovery.read_text())['files'])

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

all_inputs = sorted(p.relative_to(public).as_posix() for p in public.rglob('*') if p.is_file())
remaining = [p for p in all_inputs if expected(p) not in names and (public / p).stat().st_size]
report_path = out / 'resume-report.json'
report = json.loads(report_path.read_text()) if report_path.exists() else dict(
    status='IN_PROGRESS', batchSize=args.batch_size, originalArchiveBuilder=True,
    inputFiles=len(all_inputs), remainingFiles=len(remaining), batches=[])
for index, offset in enumerate(range(0, len(remaining), args.batch_size)):
    archive = parts / f'public-tail-{index:04}.zip'
    old = next((batch for batch in report['batches'] if batch['index'] == index), None)
    if old and old['exitCode'] == 0 and archive.is_file():
        continue
    batch_inputs = remaining[offset:offset + args.batch_size]
    with tempfile.TemporaryDirectory(prefix='phase4-original-assets-') as temporary:
        source_dir = Path(temporary) / 'source'
        home = Path(temporary) / 'home'
        home.mkdir()
        home.chmod(0o777)
        for relative in batch_inputs:
            destination = source_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(public / relative, destination)
        source_dir.chmod(0o755)
        Path(temporary).chmod(0o755)
        command = [str(root / 'binaries/system/pyrogenesis'),
                   '-archivebuild=' + str(source_dir), '-archivebuild-output=' + str(archive),
                   '-archivebuild-compress', '-mod=mod', '-mod=public']
        print('Original conversion batch', index, len(batch_inputs), 'files', flush=True)
        with (parts / f'public-tail-{index:04}.log').open('w') as log:
            result = subprocess.run(command, cwd=home, env=dict(os.environ, HOME=str(home),
                                    OMP_NUM_THREADS='2'), user=1000, group=1000, extra_groups=[],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=900)
        batch = dict(index=index, inputs=batch_inputs, exitCode=result.returncode,
                     archive=archive.name, command=command)
        if not result.returncode:
            with zipfile.ZipFile(archive) as prepared:
                batch['files'] = len(prepared.infolist())
        report['batches'] = [b for b in report['batches'] if b['index'] != index] + [batch]
        report_path.write_text(json.dumps(report, indent=2))
        if result.returncode:
            raise SystemExit(result.returncode)
report['status'] = 'ORIGINAL_CONVERSION_BATCHES_COMPLETE_NOT_MERGED'
report_path.write_text(json.dumps(report, indent=2))
print(report['status'], flush=True)
