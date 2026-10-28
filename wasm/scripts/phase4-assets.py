"""Package pinned human-authored assets with the original native archive builder."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/build/0ad')
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o777)
    home = out / 'native-home'
    home.mkdir(exist_ok=True)
    home.chmod(0o777)
    report = dict(status='IN_PROGRESS', originalArchiveBuilder=True, generatedArt=False,
                  mods={}, pin='40b8794eecb9618da69e10bacffa8814c561aa51')
    report_path = out / 'assets-report.json'
    for mod in ['mod', 'public']:
        archive = out / (mod + '.zip')
        source = root / 'binaries/data/mods' / mod
        command = [str(root / 'binaries/system/pyrogenesis'),
                   '-archivebuild=' + str(source), '-archivebuild-output=' + str(archive),
                   '-mod=mod', '-mod=public']
        with (out / (mod + '-archivebuild.log')).open('w') as stream:
            result = subprocess.run(command, cwd=home, env=dict(os.environ, HOME=str(home),
                                    OMP_NUM_THREADS='2'), user=1000, group=1000,
                                    extra_groups=[], stdout=stream, stderr=subprocess.STDOUT)
        report['mods'][mod] = dict(exitCode=result.returncode, command=command)
        if result.returncode:
            report['status'] = 'ARCHIVE_BUILD_FAILED'
            report_path.write_text(json.dumps(report, indent=2))
            raise SystemExit(result.returncode)
        with zipfile.ZipFile(archive) as packaged:
            report['mods'][mod]['files'] = len(packaged.infolist())
        digest = hashlib.sha256()
        with archive.open('rb') as stream:
            while block := stream.read(8 * 1024 * 1024):
                digest.update(block)
        report['mods'][mod].update(bytes=archive.stat().st_size, sha256=digest.hexdigest())
        report_path.write_text(json.dumps(report, indent=2))
        print(mod, 'packaged', flush=True)
    shutil.copytree(root / 'binaries/data/config', out / 'config', dirs_exist_ok=True)
    shutil.copytree(root / 'binaries/data/l10n', out / 'l10n', dirs_exist_ok=True)
    report['status'] = 'PACKAGED_NOT_RUNTIME_VERIFIED'
    report_path.write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
