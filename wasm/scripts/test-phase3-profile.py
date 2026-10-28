"""Guard the performance gate against truncated, paused or slowed simulations."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('analyzer', Path(__file__).with_name('analyze-scene-profile.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def fixture():
    return {'frames': [dict(frame=i, timeMs=i * 20, tick=i // 10, backlogMs=0,
                            paused=False, width=1920, height=1080,
                            **{key: 1 for key in ['tickMs', 'interpolateMs', 'uploadMs', 'rendererMs', 'presentMs']})
                       for i in range(601)]}

class GateTests(unittest.TestCase):
    def test_submission_gate_is_not_full_acceptance(self):
        result = module.analyze(fixture(), 0, 12)
        self.assertTrue(result['submissionGate30'])
        self.assertFalse(result['submissionGate60'])
        self.assertEqual(result['acceptance'], 'PENDING')
        self.assertEqual(result['nativePerformanceParity'], 'PENDING')
        self.assertIn('not acceptance gates', result['thresholdPurpose'])

    def test_incomplete_or_paused_or_low_resolution_fails(self):
        self.assertFalse(module.analyze(fixture(), 0, 900)['submissionGate30'])
        for key, value in [('paused', True), ('width', 640)]:
            data = fixture(); data['frames'][100][key] = value
            self.assertFalse(module.analyze(data, 0, 12)['submissionGate30'])

    def test_slow_simulation_fails(self):
        data = fixture()
        for frame in data['frames']:
            frame['tick'] //= 2
        self.assertFalse(module.analyze(data, 0, 12)['submissionGate30'])

    def test_duplicate_and_missing_frames(self):
        data = fixture(); data['frames'][100]['timeMs'] = data['frames'][99]['timeMs']
        with self.assertRaises(ValueError):
            module.analyze(data, 0, 12)
        data = fixture(); del data['frames'][100]
        self.assertFalse(module.analyze(data, 0, 12)['submissionGate30'])

if __name__ == '__main__':
    unittest.main()
