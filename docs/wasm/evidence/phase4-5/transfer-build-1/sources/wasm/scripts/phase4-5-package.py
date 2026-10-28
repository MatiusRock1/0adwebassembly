"""Assemble a separate WebGPU build, reusing immutable original ZIPs."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import argparse

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--linked-directory',type=Path)
parser.add_argument('--target-directory',type=Path)
args=parser.parse_args()
baseline=root/'wasm/dist/webgl-baseline-phase4-5'
target=(args.target_directory or root/'wasm/dist/application-phase4-5').resolve()
target.mkdir(parents=True,exist_ok=True)
linked=(args.linked_directory or root/'wasm/build/phase4-5/linked').resolve()
if not linked.exists() and not args.linked_directory:linked=target
if not (linked/'link-report.json').is_file():raise SystemExit('Link the WebGPU application first')
link_report=json.loads((linked/'link-report.json').read_text())
if link_report['exitCode']!=0:raise SystemExit('Application link failed')
for name,expected in link_report['artifacts'].items():
    path=linked/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise SystemExit('Link output incomplete or changed: '+name)
if linked!=target:
    for name in list(link_report['artifacts'])+['link-report.json']:
        temporary=target/(name+'.partial')
        shutil.copy2(linked/name,temporary);temporary.replace(target/name)
for name in ['mod.zip','public.zip','mod-resource-hashes.json','public-resource-hashes.json']:
    if not (target/name).exists():
        try:os.link(baseline/name,target/name)
        except OSError:shutil.copy2(baseline/name,target/name)
shutil.copytree(baseline/'data',target/'data',dirs_exist_ok=True)
manifest=json.loads((baseline/'application-data.json').read_text())
manifest.update(rendererBackends=['gl','webgpu'],phase45Accepted=False)
manifest['runtimeFeatures']=dict(simdEngine=bool(link_report.get('simdEngine')),
    fineScriptTiming=link_report.get('fineScriptTiming',True),
    generatedBufferUploads=bool(link_report.get('generatedBufferUploads')),
    renderWorker=bool(link_report.get('browserPerformanceFeatures')),
    asyncPipelines=bool(link_report.get('browserPerformanceFeatures')),
    persistentArchives=bool(link_report.get('browserPerformanceFeatures')),
    persistentConfig=bool(link_report.get('browserPerformanceFeatures')),
    asyncify=bool(link_report.get('asyncify')),asyncSuspension=link_report.get('asyncSuspension','none'))
(target/'application-data.json').write_text(json.dumps(manifest,indent=2))
for name in ['application.html','application.mjs','application-pointer.mjs','application-failure.mjs','renderer-session.mjs','webgpu-engine.mjs','webgpu-border.mjs','webgpu-upload.mjs','webgpu-dispatch.mjs','webgpu-upload-probe.mjs','webgpu-probe.html','webgpu-probe.mjs',
             'shared-request.mjs','webgpu-worker-bridge.mjs','webgpu-render-worker.mjs','webgpu-worker-present.mjs','webgpu-pipeline-pending.mjs','application-archives.mjs','archive-worker.mjs','archive-blocks.mjs']:
    shutil.copy2(root/'wasm/browser'/name,target/name)
shutil.copy2(target/'application.html',target/'index.html')
catalog=json.loads((root/'wasm/build/phase4-5/shaders/webgpu-shaders.json').read_text())
fingerprint=catalog['provenance']['buildFingerprint']
for name,program in catalog['programs'].items():
    program['variants']={key:variant for key,variant in program['variants'].items()
                         if variant.get('buildFingerprint')==fingerprint}
    if not program['variants']:raise SystemExit('No current shader variants: '+name)
temporary=target/'webgpu-shaders.json.partial'
temporary.write_text(json.dumps(catalog,separators=(',',':')))
temporary.replace(target/'webgpu-shaders.json')
if link_report.get('browserPerformanceFeatures'):
    blocks=dict(blockBytes=1024*1024,archives={})
    for name in ['mod','public']:
        archive=target/(name+'.zip');hashes=[];whole=hashlib.sha256()
        with archive.open('rb') as stream:
            while chunk:=stream.read(blocks['blockBytes']):
                hashes.append(hashlib.sha256(chunk).hexdigest());whole.update(chunk)
        blocks['archives'][name]=dict(bytes=archive.stat().st_size,blocks=hashes,SHA256=whole.hexdigest())
    (target/'archive-blocks.json').write_text(json.dumps(blocks,separators=(',',':')))
print('WEBGPU_APPLICATION_PACKAGED_NOT_ACCEPTED')
