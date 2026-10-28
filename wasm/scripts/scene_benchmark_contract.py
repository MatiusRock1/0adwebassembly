"""Identity of the equivalent native/browser scene; no performance thresholds."""
import hashlib
import json
from pathlib import Path

def contract(data_root, commands, pin):
    digest = hashlib.sha256()
    for file in sorted(Path(data_root).rglob('*'), key=lambda file: file.relative_to(data_root).as_posix()):
        # Runtime-generated XML/texture caches are not immutable input assets.
        if file.is_file() and "cache" not in file.relative_to(data_root).parts:
            digest.update(file.relative_to(data_root).as_posix().encode() + b'\0')
            digest.update(hashlib.sha256(file.read_bytes()).digest())
    payload = Path(commands).read_bytes()
    attributes = json.loads(payload.decode().splitlines()[0][6:])
    assert attributes['map'] == 'maps/scenarios/pathfinding_terrain_demo'
    return {'baseCommit': pin, 'map': attributes['map'], 'seed': attributes['settings']['Seed'],
            'assetsContentSHA256': digest.hexdigest(), 'commandsSHA256': hashlib.sha256(payload).hexdigest(),
            'camera': {'x': 155, 'z': 245, 'elevation': 120, 'fovRadians': .785398},
            'internalResolution': [1920, 1080], 'frameCap': 60, 'swapIntervalRequested': 0,
            'simulationTickMs': 200, 'interactiveCommandsDuringMeasurement': False,
            'renderOptions': {'maxActorQuality': 100, 'shadows': False, 'waterEffects': False,
                'waterFancy': False, 'waterReflection': False, 'waterRefraction': False,
                'postProcessing': False, 'gpuSkinning': False, 'silhouettes': False, 'smoothLOS': False},
            'scope': 'Phase3 original-engine 37-entity scene; not full-game FPS acceptance'}
