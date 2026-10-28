"""Prepare original scenario assets with the native archive builder, not new art."""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
root = Path('/build/0ad')
public = root/'binaries/data/mods/public'
out = Path('/spike/scene-assets')
out.mkdir(parents=True, exist_ok=True)
selected = set()
visited = set()
missing = set()

def add(relative):
    relative = str(relative)
    if not (public/relative).is_file():
        missing.add(relative)
        return
    selected.add(relative)

def model(prefix, name, extension):
    path = Path(prefix)/name
    for suffix in ['.dae', extension]:
        candidate = str(path.with_suffix(suffix))
        if (public/candidate).is_file():
            add(candidate)
            return
    missing.add(str(path))

def actor(relative):
    relative = str(relative)
    if relative in visited:
        return
    visited.add(relative)
    add(relative)
    if not (public/relative).is_file():
        return
    xml = ET.parse(public/relative)
    for element in xml.iter():
        text = (element.text or '').strip()
        if element.tag == 'mesh' and text:
            model('art/meshes', text, '.pmd')
        elif element.tag == 'animation' and element.get('file'):
            model('art/animation', element.get('file'), '.psa')
        elif element.tag == 'texture' and element.get('file'):
            add('art/textures/skins/' + element.get('file'))
        elif element.tag == 'variant' and element.get('file'):
            actor('art/variants/' + element.get('file'))
        elif element.tag == 'actor' and element.get('file'):
            actor('art/actors/' + element.get('file'))
        elif element.tag == 'prop' and element.get('actor'):
            actor('art/actors/' + element.get('actor'))
        elif element.tag == 'particles' and element.get('file'):
            actor('art/particles/' + element.get('file'))

def template(name, civ):
    key = 'template:' + name
    if key in visited:
        return
    visited.add(key)
    path = public/'simulation/templates/special/filter'/ (name + '.xml')
    if not path.is_file():
        path = public/'simulation/templates/mixins'/ (name + '.xml')
    if not path.is_file():
        path = public/'simulation/templates'/ (name + '.xml')
    if not path.is_file():
        missing.add(str(path.relative_to(public)))
        return
    xml = ET.parse(path)
    for parent in xml.getroot().get('parent', '').split('|'):
        if parent: template(parent.replace('{civ}', civ), civ)
    for e in xml.findall('./VisualActor/Actor'):
        if e.text: actor('art/actors/' + e.text.strip().replace('{civ}', civ))

map_xml = ET.parse(public/'maps/scenarios/pathfinding_terrain_demo.xml')
for entity in map_xml.findall('./Entities/Entity'):
    name = entity.findtext('Template')
    if name.startswith('actor|'): actor('art/actors/' + name[6:])
    else:
        civ = name.split('/')[1] if name.startswith('units/') or name.startswith('structures/') else 'athen'
        template(name, civ)

# Read the original, documented PMP terrain tag list (no data is modified).
payload = (public/'maps/scenarios/pathfinding_terrain_demo.pmp').read_bytes()
assert payload[:4] == b'PSMP'
patches = struct.unpack_from('<I', payload, 12)[0]
offset = 16 + ((patches*16+1)**2)*2
count = struct.unpack_from('<I', payload, offset)[0]
offset += 4
tags = []
for _ in range(count):
    length = struct.unpack_from('<I', payload, offset)[0]
    offset += 4
    tags.append(payload[offset:offset+length].decode())
    offset += length
assert count < 100
terrain_files = {p.stem:p for p in (public/'art/terrains').rglob('*.xml')}
for tag in tags:
    path = terrain_files[tag]
    add(path.relative_to(public))
    for parent in path.parents:
        if parent == public: break
        props = parent/'terrains.xml'
        if props.is_file(): add(props.relative_to(public))
    xml = ET.parse(path)
    for e in xml.findall('./textures/texture'):
        add('art/textures/terrain/' + e.get('file'))
    alpha = xml.findtext('alphamap') or 'standard'
    for p in (public/'art/textures/terrain/alphamaps'/alpha).glob('*.png'):
        add(p.relative_to(public))
for folder in ['art/materials', 'art/skeletons']:
    for p in (public/folder).rglob('*'):
        if p.is_file(): add(p.relative_to(public))
for p in (public/'art/textures/selection').rglob('*'):
    if p.is_file(): add(p.relative_to(public))
for p in (public/'art/textures').rglob('settings.xml'):
    add(p.relative_to(public))
for p in (public/'art/textures/animated/water/default').rglob('*'):
    if p.is_file(): add(p.relative_to(public))
for relative in ['art/textures/terrain/types/water/coastalWave.png', 'art/textures/terrain/types/water/foam.png', 'art/actors/actor.rng', 'art/actors/empty.xml', 'art/actors/placeholder.xml', 'art/terrains/terrain.rng', 'art/terrains/terrain_texture.rng']:
    if (public/relative).is_file(): add(relative)
(out/'missing.json').write_text(json.dumps(sorted(missing), indent=2))
if missing:
    raise RuntimeError('Asset closure contains missing original references: ' + str(sorted(missing)[:20]))
source_dir = out/'source'
for relative in sorted(selected):
    target = source_dir/relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(public/relative, target)
manifest = [{'path': p, 'bytes': (public/p).stat().st_size, 'sha256': hashlib.sha256((public/p).read_bytes()).hexdigest()} for p in sorted(selected)]
(out/'input-manifest.json').write_text(json.dumps({'mapTerrainTags': tags, 'files': manifest, 'totalBytes':sum(p['bytes'] for p in manifest)}, indent=2))
home = Path('/tmp/phase2-assets-home')
home.mkdir(exist_ok=True)
for relative in ['.cache/0ad', '.config/0ad', '.local/share/0ad/mods']:
    (home/relative).mkdir(parents=True, exist_ok=True)
for folder in [home, out]:
    os.chown(folder, 1000, 1000)
    for p in folder.rglob('*'): os.chown(p, 1000, 1000)
command = [str(root/'binaries/system/pyrogenesis'), '-archivebuild='+str(source_dir), '-archivebuild-output='+str(out/'prepared.zip'), '-mod=mod', '-mod=public']
with (out/'native-conversion.log').open('w') as log:
    result = subprocess.run(command, cwd=home, env=dict(os.environ, HOME=str(home), OMP_NUM_THREADS='2'), user=1000, group=1000, extra_groups=[], stdout=log, stderr=subprocess.STDOUT, timeout=240)
(out/'conversion-exit.txt').write_text(str(result.returncode))
if result.returncode: raise RuntimeError('Original archive builder failed')
with zipfile.ZipFile(out/'prepared.zip') as archive:
    names = archive.namelist()
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
    archive.extractall(out/'prepared')
for f in manifest:
    suffix = Path(f['path']).suffix
    if suffix == '.dae':
        ext = '.pmd' if f['path'].startswith('art/meshes/') else '.psa'
        expected = f['path'] + '.cached' + ext
        if expected not in names: raise RuntimeError('Model conversion missing: ' + expected)
print('ORIGINAL_SCENE_ASSETS_PREPARED', len(names), flush=True)
