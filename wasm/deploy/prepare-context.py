"""Assemble the Docker build context of the web deployment from a built package.

The context holds the landing page, the server configuration, the license texts
and the package under play/. Large files are hard-linked when the output is on
the same volume as the package, and copied otherwise. Debug symbols are left out.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = Path(__file__).resolve().parent
REQUIRED = ['application.html', 'application.mjs', 'application-data.json', 'archive-blocks.json',
            'pyrogenesis-application.mjs', 'pyrogenesis-application.wasm', 'public.zip', 'mod.zip']
LICENSES = ['LICENSE.md', 'license_gpl-2.0.txt', 'license_lgpl-2.1.txt', 'license_mit.txt']


def place(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True, help='Built package, e.g. wasm/dist/application-phase4-5-<name>.')
    parser.add_argument('--output', type=Path, required=True, help='New or empty directory for the build context.')
    args = parser.parse_args()
    package = args.package.resolve()
    missing = [name for name in REQUIRED if not (package / name).is_file()]
    if missing:
        raise SystemExit(f'Not a complete browser package ({", ".join(missing)} missing): {package}')
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f'Refusing to write into a non-empty directory: {output}')
    output.mkdir(parents=True, exist_ok=True)

    for name in ['Dockerfile', 'nginx.conf', '.dockerignore', '15-archive-urls.sh']:
        shutil.copy2(DEPLOY / name, output / name)
    shutil.copytree(DEPLOY / 'site', output / 'site')
    for name in LICENSES:
        place(ROOT / name, output / 'licenses' / name)
    files = 0
    for source in sorted(package.rglob('*')):
        if source.is_file() and source.suffix != '.symbols':
            place(source, output / 'play' / source.relative_to(package))
            files += 1
    subprocess.run([sys.executable, str(DEPLOY / 'check-module-imports.py'),
                    str(output / 'play')], check=True)
    print(f'Context ready: {output} ({files} package files)')
    print(f'  docker build -t 0ad-wasm-web "{output}"')
    print('  docker run --rm -p 8080:8080 0ad-wasm-web   # then open http://localhost:8080/')


if __name__ == '__main__':
    main()
