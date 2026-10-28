"""Fail if static relative JS imports in a browser package are missing."""
import argparse
from pathlib import Path
import re

IMPORT = re.compile(r'''(?:\bfrom\s*|\bimport\s*(?:\(\s*)?)["'](\.[^"']+)["']''')


def check(directory):
    missing = []
    for module in sorted(directory.rglob('*.mjs')):
        for specifier in IMPORT.findall(module.read_text(encoding='utf-8')):
            target = specifier.split('?', 1)[0].split('#', 1)[0]
            if not (module.parent / target).is_file():
                missing.append(f'{module.relative_to(directory)} -> {specifier}')
    if missing:
        raise SystemExit('Missing module dependencies:\n' + '\n'.join(missing))
    print('Relative module imports: OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    check(parser.parse_args().package)
