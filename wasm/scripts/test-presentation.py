"""Reject incomplete/incorrect display evidence instead of approving submissions."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('presentation', Path(__file__).with_name('analyze-presentation.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PresentationEvidence(unittest.TestCase):
    def setUp(self):
        self.profile = dict(measurementStartQpcMs=0, warmupSeconds=2,
                            durationSeconds=10, presentationProcessId=42,
                            fullscreen=True, presentmonExitCode=0,
                            frames=[dict(paused=False, width=1920, height=1080,receivedMs=t) for t in range(2000,12001,17)])
        self.rows = [dict(CPUStartQPCTimeInMs=str(t), ProcessID='42',
                          SwapChainAddress='A', MsUntilDisplayed='1',
                          MsBetweenDisplayChange='16.667') for t in range(2000, 12001, 17)]

    def test_complete_display_run(self):
        self.assertTrue(module.analyze(self.profile, self.rows)['presentationGate30'])

    def test_worker_fallback_or_missing_counters_invalidate_physical_gate(self):
        self.profile['renderer']=dict(owner='render-worker')
        self.assertFalse(module.analyze(self.profile,self.rows)['validFullscreen1080pRun'])
        counters=dict(rafPresents=20,backgroundFallbackPresents=1,failedPresents=0,cancelledPresents=0)
        self.profile['initialRendererWork']=dict(presentation=counters.copy())
        self.profile['finalRendererWork']=dict(presentation=counters | dict(rafPresents=620))
        self.assertTrue(module.analyze(self.profile,self.rows)['presentationGate30'])
        self.profile['finalRendererWork']['presentation']['backgroundFallbackPresents']+=1
        result=module.analyze(self.profile,self.rows)
        self.assertFalse(result['validFullscreen1080pRun'])
        self.assertFalse(result['presentationGate30'])

    def test_short_run_cannot_pass(self):
        self.assertFalse(module.analyze(self.profile, self.rows[:100])['presentationGate30'])

    def test_submissions_without_display_feedback_cannot_pass(self):
        for row in self.rows:
            row['MsUntilDisplayed'] = 'NA'
        with self.assertRaises(ValueError):
            module.analyze(self.profile, self.rows)

    def test_wrong_process_cannot_pass(self):
        self.profile['presentationProcessId'] = 99
        with self.assertRaises(ValueError):
            module.analyze(self.profile, self.rows)

    def test_pause_and_low_resolution_cannot_pass(self):
        for change in [dict(paused=True), dict(width=640), dict(height=600)]:
            self.profile['frames'] = [dict(paused=False, width=1920, height=1080) | change]
            self.assertFalse(module.analyze(self.profile, self.rows)['presentationGate30'])

    def test_dom_dimensions_without_backing_surface_cannot_pass(self):
        self.profile['browserVersion'] = 'test'
        self.assertFalse(module.analyze(self.profile, self.rows)['presentationGate30'])

    def test_lost_trace_events_cannot_pass(self):
        self.profile['presentmonEventsLost'] = 1
        self.assertFalse(module.analyze(self.profile, self.rows)['presentationGate30'])

    def test_slow_frames_cannot_pass(self):
        for row in self.rows:
            row['MsBetweenDisplayChange'] = '40'
        self.assertFalse(module.analyze(self.profile, self.rows)['presentationGate30'])

    def test_fast_compositor_with_slow_engine_cannot_pass(self):
        self.profile['frames']=self.profile['frames'][::4]
        result=module.analyze(self.profile,self.rows)
        self.assertGreater(result['displayedFps'],30)
        self.assertLess(result['engineRenderedFps'],30)
        self.assertFalse(result['presentationGate30'])

    def test_missing_draw_timestamps_cannot_pass(self):
        for frame in self.profile['frames']:frame.pop('receivedMs')
        self.assertFalse(module.analyze(self.profile,self.rows)['presentationGate30'])

    def test_fast_average_engine_and_compositor_cannot_hide_engine_stutters(self):
        times=[];timestamp=2000
        while timestamp<=12000:
            times.append(timestamp)
            timestamp+=45 if len(times)%9==0 else 17
        self.profile['frames']=[dict(paused=False,width=1920,height=1080,receivedMs=t) for t in times]
        result=module.analyze(self.profile,self.rows)
        self.assertGreater(result['engineRenderedFps'],30)
        self.assertGreater(result['displayedFps'],30)
        self.assertGreater(result['engineP95FrameMs'],33.4)
        self.assertFalse(result['presentationGate30'])

    def test_paced_capture_takes_the_refresh_of_the_same_display_explicitly(self):
        for row in self.rows:
            row['MsBetweenDisplayChange'] = '33.36'
        result = module.analyze(self.profile, self.rows)
        self.assertIsNone(result['measuredRefreshMs'])
        self.assertFalse(result['presentationGateTwoRefresh'])
        result = module.analyze(self.profile, self.rows, 16.68, 'reference capture')
        self.assertEqual((result['measuredRefreshMs'], result['refreshSource']), (16.68, 'reference capture'))
        self.assertAlmostEqual(result['twoRefreshLimitMs'], 2 * 16.68 * 1.005)
        # Two refreshes of a 59.94 Hz display are below 30 FPS: the written gate still fails.
        self.assertFalse(result['presentationGateTwoRefresh'])


if __name__ == '__main__':
    unittest.main()
