"""Preserve the original save serialization and debug scope separately.

ComponentManagerSerialization.cpp skips ENTITY_IS_LOCAL in SerializeState and
ComputeStateHash. DumpDebugState intentionally includes those render-local
entities; CCmpDecay updates their sinking position on MT_Interpolate.
"""
import hashlib
import io
import re
import zipfile


def debug_scopes(payload):
    chunks = re.split(rb'(?m)(?=^- id: \d+\n)', payload)
    synchronized = []
    local = []
    for chunk in chunks:
        (local if re.search(rb'(?m)^  type: local\r?$',chunk) else synchronized).append(chunk)
    return dict(nonLocalDebugSHA256=hashlib.sha256(b''.join(synchronized)).hexdigest(),
                localDebugSHA256=hashlib.sha256(b''.join(local)).hexdigest(),
                localEntityCount=len(local))


def preserve_save(archive, directory, target):
    # ZIP timestamps and GUI metadata are deliberately outside simulation.dat.
    # Keep the whole archive as evidence as well as the exact simulation bytes.
    with zipfile.ZipFile(io.BytesIO(archive)) as saved:
        simulation = saved.read('simulation.dat')
    assert simulation, 'Original save contains no simulation state'
    (directory/f'state-{target}.0adsave').write_bytes(archive)
    (directory/f'state-{target}.bin').write_bytes(simulation)
    return dict(serializedSHA256=hashlib.sha256(simulation).hexdigest(),
                serializedBytes=len(simulation),serialization='Original SavedGames::Save / simulation.dat')
