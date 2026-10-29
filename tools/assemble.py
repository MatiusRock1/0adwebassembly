#!/usr/bin/env python3
"""Arma el árbol completo de 0 A.D. WebAssembly y vuelca sus cambios a este repositorio.

Este repositorio guarda solo la capa WebAssembly. El juego sale de un clon del
repositorio oficial de 0 A.D., en el commit fijado en BASE_COMMIT.txt.

  build   crea DEST como worktree del clon oficial en ese commit, aplica patches/
          y copia encima los archivos propios de la capa.
  export  regenera patches/ con los cambios hechos en DEST a archivos oficiales y
          copia aquí los archivos propios nuevos o modificados en DEST.

  python tools/assemble.py build  [--official ../0ad] [--dest ../0ad-wasm]
  python tools/assemble.py export [--dest ../0ad-wasm]
"""

import argparse
import filecmp
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / 'patches'
# Carpetas de este repositorio que no pasan al árbol completo.
TOOLING = ('patches/', 'tools/')
# Archivos oficiales que este repositorio conserva para sí; en el árbol completo
# se usa la versión oficial.
KEPT = {'README.md', '.gitignore', '.gitattributes', 'LICENSE.md',
        'license_gpl-2.0.txt', 'license_lgpl-2.1.txt', 'license_mit.txt'}
# Los parches salen con fin de línea LF, como 0 A.D. oficial, y sin depender de
# la configuración de diff del usuario.
DIFF = ['-c', 'core.autocrlf=input', '-c', 'core.safecrlf=false', 'diff', 'HEAD', '--no-renames', '--no-color',
        '--no-ext-diff', '--no-textconv', '--src-prefix=a/', '--dst-prefix=b/']


def git(cwd, *args, capture=True):
    result = subprocess.run(['git', '-C', str(cwd), *args],
                            stdout=subprocess.PIPE if capture else None)
    if result.returncode:
        sys.exit(f'Falló git {" ".join(args)} en {cwd}')
    return result.stdout


def paths(output):
    return [p for p in output.decode('utf-8', 'surrogateescape').split('\0') if p]


def base_commit():
    return (ROOT / 'BASE_COMMIT.txt').read_text().strip()


def official_paths(repo):
    return set(paths(git(repo, 'ls-tree', '-r', '-z', '--name-only', 'HEAD')))


def layer_files(official):
    """Archivos propios de la capa: los de este repositorio que 0 A.D. oficial no tiene."""
    own, shadowed = [], []
    for rel in paths(git(ROOT, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')):
        if rel.startswith(TOOLING) or not (ROOT / rel).is_file():
            continue
        if rel not in official:
            own.append(rel)
        elif rel not in KEPT:
            shadowed.append(rel)
    if shadowed:
        print(f'Aviso: {len(shadowed)} archivo(s) de aquí también existen en 0 A.D. oficial y no se '
              f'copian; sus cambios van en patches/ (ver export): {", ".join(shadowed[:5])}')
    return own


def area(rel):
    """Parche al que va un archivo oficial: root, binaries, build, source-<módulo>..."""
    parts = rel.split('/')
    if len(parts) == 1:
        return 'root'
    if parts[0] == 'source' and len(parts) > 2:
        return 'source-' + parts[1]
    return parts[0].lstrip('.')


def build(args):
    base = base_commit()
    official, dest = args.official.resolve(), args.dest.resolve()
    if dest.exists():
        sys.exit(f'{dest} ya existe. Para rehacerlo: git -C "{official}" worktree remove --force "{dest}"')
    check = subprocess.run(['git', '-C', str(official), 'cat-file', '-e', base + '^{commit}'],
                           stderr=subprocess.DEVNULL)
    if check.returncode:
        sys.exit(f'{official} no es un clon de 0 A.D. con el commit {base}. Clónalo con\n'
                 f'  git clone https://gitea.wildfiregames.com/0ad/0ad.git "{official}"\n'
                 f'o actualízalo con: git -C "{official}" fetch origin')
    git(official, 'worktree', 'add', '--detach', str(dest), base, capture=False)

    patches = sorted(PATCHES.glob('*.patch'))
    # git apply no cambia nada si alguno de los parches no encaja.
    if patches and subprocess.run(['git', '-C', str(dest), 'apply', '--whitespace=nowarn',
                                   *map(str, patches)]).returncode:
        sys.exit(f'Algún parche no aplica sobre {base}; {dest} quedó sin parches. Bórralo con\n'
                 f'  git -C "{official}" worktree remove --force "{dest}"')

    own = layer_files(official_paths(dest))
    for rel in own:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    print(f'Listo: {dest}\n  {len(patches)} parche(s) aplicados, {len(own)} archivo(s) propios copiados.')


def export(args):
    dest = args.dest.resolve()
    base = base_commit()
    head = git(dest, 'rev-parse', 'HEAD').decode().strip()
    if head != base:
        sys.exit(f'{dest} está en {head}, no en el commit de BASE_COMMIT.txt ({base}).')

    entries = paths(git(dest, *DIFF, '--name-status', '-z'))
    by_area, added = defaultdict(list), []
    for status, rel in zip(entries[0::2], entries[1::2]):
        if status == 'A':
            added.append(rel)
            continue
        # Un binario borrado no necesita su contenido en el parche: basta el índice completo.
        options = ['--full-index'] if status == 'D' else ['--full-index', '--binary']
        by_area[area(rel)].append(git(dest, *DIFF, *options, '--', ':(literal)' + rel))
    PATCHES.mkdir(exist_ok=True)
    for old in PATCHES.glob('*.patch'):
        old.unlink()
    for name, chunks in sorted(by_area.items()):
        (PATCHES / f'{name}.patch').write_bytes(b''.join(chunks))

    exported = [rel for rel in paths(git(dest, 'ls-files', '-z', '--others', '--exclude-standard')) + added
                if not rel.startswith(TOOLING)]
    copied = 0
    for rel in exported:
        source, target = dest / rel, ROOT / rel
        if target.is_file() and filecmp.cmp(source, target):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    missing = sorted(set(layer_files(official_paths(dest))) - set(exported))

    print(f'patches/: {len(by_area)} parche(s), {sum(map(len, by_area.values()))} archivo(s) oficiales cambiados.')
    print(f'{copied} archivo(s) propios copiados desde {dest}.')
    if missing:
        print(f'{len(missing)} archivo(s) propios de aquí ya no están en {dest}; no se borraron: '
              f'{", ".join(missing[:5])}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('build', help='crea el árbol completo')
    command.add_argument('--official', type=Path, default=ROOT.parent / '0ad',
                         help='clon del repositorio oficial de 0 A.D. (por defecto ../0ad)')
    command.add_argument('--dest', type=Path, default=ROOT.parent / '0ad-wasm',
                         help='carpeta nueva para el árbol completo (por defecto ../0ad-wasm)')
    command.set_defaults(run=build)
    command = commands.add_parser('export', help='vuelca aquí los cambios hechos en el árbol completo')
    command.add_argument('--dest', type=Path, default=ROOT.parent / '0ad-wasm',
                         help='árbol completo creado con build (por defecto ../0ad-wasm)')
    command.set_defaults(run=export)
    args = parser.parse_args()
    args.run(args)


if __name__ == '__main__':
    main()
