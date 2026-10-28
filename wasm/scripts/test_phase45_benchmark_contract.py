import copy
from pathlib import Path
import tempfile
import unittest
from phase45_benchmark_contract import make_plan,summarize,assess_backlog,assess_simulation_rate,fingerprint,assess_worker_presentation

class AcceptanceContract(unittest.TestCase):
    def test_optional_experimental_modules_are_fingerprinted_when_present(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(fingerprint(directory),{})
            for name in ['webgpu-bundles.mjs','webgpu-bundles-probe.mjs','shared-request.mjs','webgpu-worker-bridge.mjs','webgpu-render-worker.mjs','webgpu-worker-present.mjs','webgpu-pipeline-pending.mjs','application-archives.mjs','archive-worker.mjs','archive-blocks.mjs','archive-blocks.json','application-graphics.mjs','webgpu-command-ring.mjs','webgpu-pipeline-cache.mjs']:
                path=Path(directory)/name
                path.write_text('first version')
                original=fingerprint(directory)[name]
                path.write_text('changed version')
                self.assertNotEqual(fingerprint(directory)[name],original)

    def setUp(self):
        self.plan=make_plan(['webgpu'],3,120,900)
        self.results={(r['backend'],r['workload'],r['repetition']):dict(
            passed=True,tickRate=1,errors=[],exitCode=0,warmupSeconds=120,durationSeconds=900,
            renderer=dict(backend='webgpu',adapter=dict(vendor='test',architecture='same')),
            initialState=dict(pendingTurns=2),lastState=dict(pendingTurns=2),samples=[dict(state=dict(pendingTurns=2))]*5,
            shutdown=dict(workers=[],liveApplicationTargets=[],sdk=dict(running=[],pooled=[],pthreads=[])),
            presentmonExitCode=0,presentmonEventsLost=0,
            presentation=dict(measurementComplete=True,presentationGate30=True)) for r in self.plan}

    def test_six_complete_runs_pass_performance_but_never_accept_phase(self):
        result=summarize(self.plan,self.results)
        self.assertTrue(result['webgpuPerformanceGate'])
        self.assertFalse(result['phase45Accepted'])
        self.assertFalse(result['nativeAndWebGLIncluded'])
        self.assertFalse(result['sameActiveGPUVerified'])

    def test_missing_or_partial_run_cannot_pass(self):
        self.results.pop(('webgpu','combat',3))
        self.assertFalse(summarize(self.plan,self.results)['webgpuPerformanceGate'])

    def test_worker_capture_requires_successful_raf_without_fallback_or_errors(self):
        key=('webgpu','combat',3)
        report=self.results[key]
        report['renderer']['owner']='render-worker'
        self.assertFalse(summarize(self.plan,self.results)['webgpuPerformanceGate'])
        baseline=dict(rafPresents=10,backgroundFallbackPresents=2,failedPresents=0,cancelledPresents=0)
        report['initialRendererWork']=dict(presentation=baseline.copy())
        report['finalRendererWork']=dict(presentation=baseline | dict(rafPresents=600))
        self.assertTrue(summarize(self.plan,self.results)['webgpuPerformanceGate'])
        for field,value in [('backgroundFallbackPresents',3),('failedPresents',1),('cancelledPresents',1),
                            ('rafPresents',10),('rafPresents',9),('rafPresents',float('nan'))]:
            changed=copy.deepcopy(report)
            changed['finalRendererWork']['presentation'][field]=value
            with self.subTest(field=field,value=value):
                self.assertFalse(assess_worker_presentation(changed)['valid'])
                results=copy.deepcopy(self.results);results[key]=changed
                self.assertFalse(summarize(self.plan,results)['webgpuPerformanceGate'])

    def test_incomplete_worker_counters_cannot_be_treated_as_legacy(self):
        for report in [dict(initialRendererWork=dict(presentation={})),
                       dict(finalRendererWork=dict(presentation={})),
                       dict(renderer=dict(owner='render-worker'))]:
            self.assertFalse(assess_worker_presentation(report)['valid'])

    def test_short_measured_duration_cannot_use_long_plan(self):
        self.results[('webgpu','combat',3)]['durationSeconds']=45
        self.assertFalse(summarize(self.plan,self.results)['webgpuPerformanceGate'])

    def test_wrong_backend_adapter_errors_lost_events_or_slow_simulation_fail(self):
        key=('webgpu','combat',3)
        for change in [dict(renderer=dict(backend='webgl')),dict(renderer=dict(backend='webgpu',adapter=dict(vendor='different'))),
                       dict(errors=['validation']),dict(presentmonEventsLost=1),dict(tickRate=.8),
                       dict(presentation=dict(measurementComplete=False,presentationGate30=True)),
                       dict(teardownFailure='Live worker'),dict(shutdown={}),dict(exitCode=1),dict(exitCode=None),
                       dict(functionalFixedFrameFrequency=60),dict(applicationArguments=['-fixed-frame-frequency=60'])]:
            results=copy.deepcopy(self.results);results[key].update(change)
            with self.subTest(change=change):self.assertFalse(summarize(self.plan,results)['webgpuPerformanceGate'])

    def test_duplicate_repetition_does_not_count_three_times(self):
        plan=[self.plan[0]]*3+[self.plan[1]]*3
        self.assertFalse(summarize(plan,self.results)['webgpuPerformanceGate'])

    def test_single_workload_diagnostic_never_accepts_both_workloads(self):
        plan=make_plan(['webgpu'],3,120,900,['combat'])
        self.assertEqual(len(plan),3)
        self.assertFalse(summarize(plan,self.results)['webgpuPerformanceGate'])
        for workloads in [[],['combat','combat'],['unknown']]:
            with self.subTest(workloads=workloads),self.assertRaises(ValueError):
                make_plan(['webgpu'],1,120,900,workloads)

    def test_original_turn_backlog_must_be_observed_and_not_grow(self):
        self.assertFalse(assess_backlog({})['nonGrowing'])
        key=('webgpu','combat',3)
        self.results[key]['samples']=[dict(state=dict(pendingTurns=n)) for n in [2,2,2,3,4,5]]
        self.results[key]['lastState']=dict(pendingTurns=5)
        self.assertFalse(summarize(self.plan,self.results)['webgpuPerformanceGate'])

    def test_plan_is_serial_and_validates_arguments(self):
        self.assertEqual(len(make_plan(['webgpu','webgl','native'],3,120,900)),18)
        for args in [([],3,120,900),(['webgpu','webgpu'],3,120,900),(['webgpu'],0,120,900),(['webgpu'],1,-1,900)]:
            with self.subTest(args=args),self.assertRaises(ValueError):make_plan(*args)

    def test_simulation_speed_uses_actual_state_reads_after_deadline(self):
        report=dict(initialState=dict(simulation=dict(timeElapsed=1000)),
            lastState=dict(simulation=dict(timeElapsed=261000)),
            initialStateIntervalQpcMs=[0,200],lastStateIntervalQpcMs=[260000,260200])
        self.assertTrue(assess_simulation_rate(report)['withinTolerance'])
        # 240 simulated seconds after 260 real seconds must not pass merely
        # because the planned measurement lasted 240 seconds.
        report['lastState']['simulation']['timeElapsed']=241000
        self.assertFalse(assess_simulation_rate(report)['withinTolerance'])

    def test_observation_uncertainty_cannot_hide_slow_or_fast_simulation(self):
        report=dict(initialState=dict(simulation=dict(timeElapsed=0)),
            lastState=dict(simulation=dict(timeElapsed=240000)),
            initialStateIntervalQpcMs=[0,10000],lastStateIntervalQpcMs=[240000,250000])
        self.assertAlmostEqual(assess_simulation_rate(report)['rate'],1)
        self.assertFalse(assess_simulation_rate(report)['withinTolerance'])

    def test_missing_overlapping_or_invalid_observation_times_fail(self):
        for initial,final in [([],[]),(None,None),([10,0],[20,30]),([0,20],[10,30]),([0,float('nan')],[20,30])]:
            with self.subTest(initial=initial,final=final):
                self.assertFalse(assess_simulation_rate(dict(initialStateIntervalQpcMs=initial,
                    lastStateIntervalQpcMs=final))['withinTolerance'])

if __name__=='__main__':unittest.main()
