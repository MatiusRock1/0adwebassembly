import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from phase45_simulation_snapshot import debug_scopes,preserve_save


class SimulationSnapshotContract(unittest.TestCase):
    def test_render_local_decay_is_separate_from_every_nonlocal_component(self):
        base=b'rng: 123\nentities:\n- id: 1\n  Position:\n    y: 5\n- id: 536870912\n  type: local\n  Position:\n    y: -1\n'
        local_change=base.replace(b'y: -1',b'y: -2')
        simulation_change=base.replace(b'y: 5',b'y: 6')
        first=debug_scopes(base)
        self.assertEqual(first['localEntityCount'],1)
        self.assertEqual(first['nonLocalDebugSHA256'],debug_scopes(local_change)['nonLocalDebugSHA256'])
        self.assertNotEqual(first['localDebugSHA256'],debug_scopes(local_change)['localDebugSHA256'])
        self.assertNotEqual(first['nonLocalDebugSHA256'],debug_scopes(simulation_change)['nonLocalDebugSHA256'])
        # An unmarked entity is synchronized even if its ID resembles a local
        # ID: never discard unknown data based on a guessed numeric threshold.
        self.assertEqual(debug_scopes(base.replace(b'  type: local\n',b''))['localEntityCount'],0)

    def test_original_simulation_bytes_and_complete_archive_are_preserved(self):
        payload=b'original serialized simulation\x00\xff'
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as saved:
            saved.writestr('metadata.json','{"timestamp":123}')
            saved.writestr('simulation.dat',payload)
        archive=stream.getvalue()
        temporary_root=Path(__file__).resolve().parents[1]/'build/phase4-5/test-tmp'
        temporary_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
            directory=Path(temporary)
            self.assertTrue(directory.resolve().is_relative_to(temporary_root.resolve()))
            result=preserve_save(archive,directory,10000)
            self.assertEqual((directory/'state-10000.bin').read_bytes(),payload)
            self.assertEqual((directory/'state-10000.0adsave').read_bytes(),archive)
            self.assertEqual(result['serializedSHA256'],hashlib.sha256(payload).hexdigest())


if __name__=='__main__':unittest.main()
