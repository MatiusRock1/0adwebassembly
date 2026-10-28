"""Prepare a private JS-only bundle-cache experiment over the unchanged best binary."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

root=Path(__file__).resolve().parents[2]
base=root/'wasm/dist/application-phase4-5-audio-error'
target=root/'wasm/dist/application-phase4-5-bundles'
evidence=root/'docs/wasm/evidence/phase4-5/render-bundles-build-1'
evidence.mkdir(exist_ok=True)
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
probe=root/'wasm/probes/render-bundles.mjs'
run=subprocess.run(['node',str(probe)],capture_output=True,text=True,check=True)
cpu=json.loads(run.stdout.strip().splitlines()[-1])
assert cpu['passed'] and cpu['checks']==14
cpu.update(sourceSHA256=digest(probe),helperSHA256=digest(root/'wasm/experiments/render-bundles/webgpu-bundles.mjs'))
assert not (evidence/'cpu-probe-report.json').exists(),'Preserve previous evidence before rebuilding'
(evidence/'cpu-probe-report.json').write_text(json.dumps(cpu,indent=2))
subprocess.run([sys.executable,str(root/'wasm/scripts/phase4-5-package.py'),
                '--linked-directory',str(base),'--target-directory',str(target)],check=True)
engine=target/'webgpu-engine.mjs'
before=engine.read_text()
assert digest(engine)==digest(base/engine.name),'Control renderer changed before adaptation'
anchor="import {CommandDispatcher} from './webgpu-dispatch.mjs';"
assert before.count(anchor)==1
after=before.replace(anchor,anchor+"\nimport {RenderBundleCache} from './webgpu-bundles.mjs';",1)
old='this.pass=this.encoderForWork().beginRenderPass(descriptor);for(const label of this.labels)this.pass.pushDebugGroup(label);this.applyViewport();this.applyScissor();'
new='''const pass=this.encoderForWork().beginRenderPass(descriptor);
    this.bundleCache??=new RenderBundleCache(this.device,{stats:this.stats});
    this.pass=this.bundleCache.begin(pass,{colorFormats:a.format?[a.format]:[],depthStencilFormat:a.depthFormat??undefined,sampleCount:a.samples},framebuffer.width,framebuffer.height);
    for(const label of this.labels)this.pass.pushDebugGroup(label);this.applyViewport();this.applyScissor();'''
assert after.count(old)==1
after=after.replace(old,new,1)
cleanup='this.blitPipelines?.clear();this.blitModule=null;'
assert after.count(cleanup)==1
after=after.replace(cleanup,cleanup+'\n      this.bundleCache?.clear();this.bundleCache=null;',1)
engine.write_text(after)
upload=target/'webgpu-upload-probe.mjs'
source=upload.read_text();anchor='export async function verifyUploadBelt(device)'
assert source.count(anchor)==1
source=source.replace(anchor,'async function verifyOriginalUploadBelt(device)',1)
source+="""
export async function verifyUploadBelt(device){
  const original=await verifyOriginalUploadBelt(device);
  const {verifyRenderBundleCache}=await import('./webgpu-bundles-probe.mjs');
  return {...original,renderBundles:await verifyRenderBundleCache(device)};
}
"""
upload.write_text(source)
for name in ['webgpu-bundles.mjs','webgpu-bundles-probe.mjs']:
    shutil.copy2(root/'wasm/experiments/render-bundles'/name,target/name)
manifest=json.loads((target/'application-data.json').read_text())
manifest['platformExperiment']='bounded-render-bundle-cache'
manifest['experimentalJSSHA256']={name:digest(target/name) for name in ['webgpu-engine.mjs','webgpu-upload-probe.mjs','webgpu-bundles.mjs','webgpu-bundles-probe.mjs']}
(target/'application-data.json').write_text(json.dumps(manifest,indent=2))
control=json.loads((base/'link-report.json').read_text())
for name,expected in control['artifacts'].items():
    assert digest(target/name)==digest(base/name)==expected,'Best binary differs: '+name
patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='control/webgpu-engine.mjs',tofile='experiment/webgpu-engine.mjs'))
(evidence/'webgpu-engine.patch').write_text(patch)
for name in ['webgpu-bundles.mjs','webgpu-bundles-probe.mjs','application-data.json','link-report.json']:
    shutil.copy2(target/name,evidence/name)
shutil.copy2(probe,evidence/'cpu-probe.mjs')
shutil.copy2(Path(__file__),evidence/'package-script.py')
report=dict(passed=True,phase45Accepted=False,performanceAcceptance=False,
    package=str(target),binaryMatchesBest=True,vmSHA256=control['scriptingArchive']['SHA256'],
    experimentalJSSHA256=manifest['experimentalJSSHA256'],cpuChecks=14,
    scope='Only private JS encoder/probe changed. Best binary, VM, AL-error order, shaders, original game quality and simulation preserved. GPU correctness and physical performance still pending.')
(evidence/'package-check.json').write_text(json.dumps(report,indent=2))
print('BUNDLE_EXPERIMENT_PACKAGED_NOT_EXECUTED',flush=True)
