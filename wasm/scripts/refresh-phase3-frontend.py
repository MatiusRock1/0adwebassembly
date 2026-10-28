"""Refresh browser controls without relabeling an obsolete application binary."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
manifest_path = args.directory / 'build-profile.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
current = hashlib.sha256((root / 'wasm/harness/scene-main.cpp').read_bytes()).hexdigest()
if current != manifest.get('applicationSourceSHA256'):
    parser.error('Application source differs from this binary; rebuild before refreshing controls')
for name in ['scene.html', 'scene.mjs']:
    shutil.copy2(root / 'wasm/browser' / name, args.directory / name)
shutil.copy2(args.directory / 'scene.html', args.directory / 'index.html')
manifest['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.directory.iterdir()
                         if p.suffix in ['.mjs', '.wasm', '.data', '.html']}
manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
