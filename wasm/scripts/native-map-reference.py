"""Prepare and exercise an unmodified native replay over original map data."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path('/build/0ad')
out = Path('/spike/native-map')
out.mkdir(parents=True, exist_ok=True)
(out / 'status.txt').write_text('NATIVE_MAP_FAILED')
scenario = json.loads(Path('/opt/scenario.json').read_text())
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == scenario['baseCommit']
public = root / 'binaries/data/mods/public'
map_path = public / (scenario['map'] + '.xml')
xml = ET.parse(map_path)
settings = json.loads(xml.findtext('ScriptSettings'))
settings['Seed'] = scenario['seed']
settings['AISeed'] = scenario['seed']
mod = json.loads((public / 'mod.json').read_text())
attributes = {'mapType': 'scenario', 'map': scenario['map'], 'settings': settings,
              'mods': [{'mod': 'public', 'name': mod['name'], 'version': mod['version']} ]}
replay = ['start ' + json.dumps(attributes, separators=(',', ':'))]
for tick in range(scenario['initialTicks'] + scenario['movementTicks']):
    replay.append(f"turn {tick} {scenario['turnLengthMs']}")
    if tick == scenario['initialTicks']:
        replay.append('cmd ' + str(scenario['player']) + ' ' + json.dumps(scenario['command'], separators=(',', ':')))
    replay.append('end')
(out / 'commands.txt').write_text('\n'.join(replay) + '\n')
files = []
for path in [map_path, map_path.with_suffix('.pmp')]:
    if not path.is_file():
        raise RuntimeError(f'Missing original map resource: {path}')
    payload = path.read_bytes()
    files.append({'path': str(path.relative_to(root)), 'bytes': len(payload),
                  'sha256': hashlib.sha256(payload).hexdigest()})
    shutil.copy2(path, out / path.name)
manifest = {**scenario, 'mapFiles': files,
            'initialEntities': [{'id': int(e.attrib['uid']), 'template': e.findtext('Template'),
                                 'player': int(e.findtext('Player')), 'position': e.find('Position').attrib}
                                for e in xml.findall('./Entities/Entity')],
            'license': 'See LICENSE.md and the longest applicable path; map-specific license requires verification',
            'mapHistory': subprocess.check_output(['git', 'log', '-5', '--format=%H %an <%ae> %s',
                          '--', str(map_path.relative_to(root))], cwd=root, text=True)}
shutil.copy2(root / 'LICENSE.md', out / 'upstream-LICENSE.md')
map_license = public / 'maps/LICENSE.txt'
manifest['mapLicenseFound'] = map_license.is_file()
if map_license.is_file():
    shutil.copy2(map_license, out / 'map-LICENSE.txt')
(out / 'scenario-manifest.json').write_text(json.dumps(manifest, indent=2))
home = Path('/tmp/phase2-native-home')
home.mkdir(exist_ok=True)
os.chown(home, 1000, 1000)
for relative in ['.local/share/0ad/mods', '.cache/0ad', '.config/0ad']:
    directory = home / relative
    directory.mkdir(parents=True, exist_ok=True)
for directory in home.rglob('*'):
    os.chown(directory, 1000, 1000)
env = dict(os.environ, HOME=str(home))
command = [str(root / 'binaries/system/pyrogenesis'), '-replay=' + str(out / 'commands.txt'), '-ooslog']
with (out / 'native-map.log').open('w') as log:
  try:
    result = subprocess.run(command, cwd=home, env=env, stdout=log,
                            stderr=subprocess.STDOUT, timeout=180, user=1000, group=1000, extra_groups=[])
  except subprocess.TimeoutExpired:
    print((out / 'native-map.log').read_text(errors='replace')[-10000:], flush=True)
    (out / 'status.txt').write_text('NATIVE_MAP_TIMEOUT')
    raise
text = (out / 'native-map.log').read_text(errors='replace')
report = {'exitCode': result.returncode, 'finalStateHash': re.findall(r'# Final state: ([0-9a-f]+)', text),
          'ticks': scenario['initialTicks'] + scenario['movementTicks']}
# Retain just the documented checkpoints from the engine's authentic state dumps.
logs = Path('/tmp/phase2-native-home/.config/0ad/logs/oos_logs')
all_dumps = sorted(logs.rglob('*.txt'))
if not all_dumps:
    all_dumps = sorted(Path('/tmp/phase2-native-home').rglob('oos_logs/**/*.txt'))
report['dumpsFound'] = len(all_dumps)
for tick in scenario['checkpoints']:
    matches = [p for p in all_dumps if p.name == f'{tick-1:05d}.txt']
    for path in matches:
        shutil.copy2(path, out / f'tick-{tick:04d}.txt')
        binary = path.with_suffix('.dat')
        if binary.exists():
            shutil.copy2(binary, out / f'tick-{tick:04d}.dat')
checkpoints = []
for tick in scenario['checkpoints']:
    path = out / f'tick-{tick:04d}.txt'
    binary = out / f'tick-{tick:04d}.dat'
    if not path.is_file() or not binary.is_file():
        raise RuntimeError(f'Missing checkpoint {tick}')
    dump = path.read_text()
    states = []
    for match in re.finditer(r'^- id: (\d+)\n(.*?)(?=^- id: |\Z)', dump, re.MULTILINE | re.DOTALL):
        position = re.search(r'^  Position:\n((?:    .*\n)*)', match[2], re.MULTILINE)
        owner = re.search(r'^  Ownership:\n    owner: (\d+)', match[2], re.MULTILINE)
        if position:
            coordinates = {k: re.search(r'^    ' + k + r': (.+)$', position[1], re.MULTILINE)[1]
                           for k in ['x', 'y', 'z']}
            states.append({'id': int(match[1]), 'positionDisplay': coordinates,
                           'owner': int(owner[1]) if owner else None})
    checkpoints.append({'tick': tick, 'originalStateHash': dump.splitlines()[0].split(': ')[1],
                        'serializedStateSHA256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                        'entities': sorted(states, key=lambda e: e['id'])})
(out / 'native-checkpoints.json').write_text(json.dumps(checkpoints, indent=2))
def moved_entity(checkpoint):
    return next(e for e in checkpoint['entities'] if e['id'] == scenario['entity'])
report['movementObserved'] = moved_entity(checkpoints[1])['positionDisplay'] != moved_entity(checkpoints[-1])['positionDisplay']
with (out / 'native-repeat.log').open('w') as log:
    repeat = subprocess.run(command[:-1], cwd=home, env=env, stdout=log, stderr=subprocess.STDOUT,
                            timeout=180, user=1000, group=1000, extra_groups=[])
repeat_hash = re.findall(r'# Final state: ([0-9a-f]+)', (out / 'native-repeat.log').read_text(errors='replace'))
report['repeatExitCode'] = repeat.returncode
report['repeatFinalStateHash'] = repeat_hash
report['reproducible'] = repeat.returncode == 0 and repeat_hash == report['finalStateHash']
(out / 'native-map-report.json').write_text(json.dumps(report, indent=2))
if result.returncode != 0 or not report['finalStateHash'] or not report['movementObserved'] or not report['reproducible']:
    print(text[-10000:], flush=True)
    raise RuntimeError('Native map replay failed; inspect native-map.log')
print('NATIVE_MAP_REPLAY_PASSED', report)

(out / 'status.txt').write_text('NATIVE_MAP_REPLAY_PASSED')
