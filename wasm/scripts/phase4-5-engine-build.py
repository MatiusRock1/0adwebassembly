"""Incrementally compile real engine WebGPU units against the frozen phase 4 ABI."""
import concurrent.futures
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess

out=Path('/phase45-build/application');out.mkdir(parents=True,exist_ok=True)
root=out/'source'
if not root.exists():shutil.copytree('/phase4-build/source',root)
subprocess.run(['python3','/workspace/wasm/scripts/phase4-application-patch.py',str(root),'--patch',str(out/'application.patch')],check=True)
shutil.copytree('/workspace/source/renderer/backend/webgpu',root/'renderer/backend/webgpu',dirs_exist_ok=True)
shutil.copy2('/workspace/source/renderer/backend/Backend.h',root/'renderer/backend/Backend.h')
for relative in ['graphics/ObjectBase.cpp','graphics/VisualVariantRandom.h']:
    shutil.copy2(Path('/workspace/source')/relative,root/relative)
video=root/'ps/VideoMode.cpp';text=video.read_text()
if 'Backend::WEBGPU' not in text:
    text=text.replace('#include "renderer/backend/vulkan/DeviceForward.h"','#include "renderer/backend/vulkan/DeviceForward.h"\n#include "renderer/backend/webgpu/DeviceForward.h"')
    text=text.replace('if (rendererBackend == "dummy")','if (rendererBackend == "webgpu")\n\t\tm_Backend = Renderer::Backend::Backend::WEBGPU;\n\telse if (rendererBackend == "dummy")')
    text=text.replace('case Renderer::Backend::Backend::GL:\n\t\tfallback', 'case Renderer::Backend::Backend::WEBGPU:\n\t\tbreak;\n\tcase Renderer::Backend::Backend::GL:\n\t\tfallback')
    text=text.replace('case Renderer::Backend::Backend::GL:\n\t\tname', 'case Renderer::Backend::Backend::WEBGPU:\n\t\tname = "WebGPU";\n\t\tbreak;\n\tcase Renderer::Backend::Backend::GL:\n\t\tname')
    text=text.replace('case Renderer::Backend::Backend::GL:\n\t\tm_BackendDevice', 'case Renderer::Backend::Backend::WEBGPU:\n\t\tm_BackendDevice = Renderer::Backend::WebGPU::CreateDevice(window);\n\t\tENSURE(m_BackendDevice);\n\t\tbreak;\n\tcase Renderer::Backend::Backend::GL:\n\t\tm_BackendDevice')
    video.write_text(text)
manager=root/'graphics/ShaderManager.cpp';text=manager.read_text()
if 'Backend::WEBGPU' not in text:text=text.replace('m_Device->GetBackend() == Renderer::Backend::Backend::GL)', 'm_Device->GetBackend() == Renderer::Backend::Backend::GL || m_Device->GetBackend() == Renderer::Backend::Backend::WEBGPU)');manager.write_text(text)
coordinate_units=['renderer/SceneRenderer.cpp','renderer/ShadowMap.cpp','renderer/PostprocManager.cpp','graphics/LOSTexture.cpp','graphics/MiniMapTexture.cpp']
for relative in coordinate_units:
    path=root/relative;text=path.read_text()
    for expression in ['deviceCommandContext->GetDevice()->GetBackend()','Device->GetBackend()','device->GetBackend()']:
        text=text.replace(expression+' == Renderer::Backend::Backend::VULKAN','Renderer::Backend::UsesUpperLeftOrigin('+expression+')')
    path.write_text(text)
includes=Path('/tmp/phase4-includes');includes.mkdir(exist_ok=True)
for name in ['boost','enet','libxml']:
    target=includes/name
    if not target.exists():target.symlink_to(Path('/spike/headless/include')/name)
shutil.copytree('/spike/headless/include/fmt',includes/'fmt',dirs_exist_ok=True)
fmt=includes/'fmt/core.h';fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))','parse_format_string<true>(str_, checker(str_, {}))'))
flags=['em++','-std=c++20','-pthread','-fexceptions','-O2','-ffunction-sections','-fdata-sections','-ferror-limit=6','-DFMT_HEADER_ONLY','-DNDEBUG','-DCONFIG_ENABLE_PCH=0',
       '-DCONFIG2_AUDIO=1','-DCONFIG2_NVTT=0','-DCONFIG2_LOBBY=0','-DCONFIG2_MINIUPNPC=0','-DCONFIG2_DAP_INTERFACE=0','-DCONFIG2_FILE_ENABLE_AIO=0','-DCONFIG2_GLES=1',
       '-sUSE_SDL=2','--use-port=zlib','--use-port=libpng','--use-port=freetype','--use-port=icu','--use-port=ogg','--use-port=vorbis',
       '-I'+str(root),'-I'+str(root/'lib'),'-I'+str(root/'pch/engine'),'-I/tmp/phase4-includes','-I/phase4-build/include',
       '-I'+str(root/'third_party/tinygettext/include'),'-I/build/0ad/libraries/source/cpp-httplib/include','-I/spike/phase4-deps/prefix/include','-I/phase4-harness',
       '-I/spike/mozjs-128.13.0/build-wasm/dist/include','-I'+str(root/'third_party/glad/include'),'-include','/spike/wasm/harness/scene-script-timing.h']
report=json.loads(Path('/phase4-build/compile-report.json').read_text())
previous_path=out/'compile-report.json'
previous=json.loads(previous_path.read_text()) if previous_path.exists() else report
results={r['source']:r for r in previous['results']}
def compile_unit(relative):
    name=relative.replace('/','_');obj=out/(name+'.o');log=out/(name+'.log')
    command=flags+['-c',str(root/relative),'-o',str(obj)]
    dependencies=(root/'renderer/backend/Backend.h').read_bytes()+(root/'renderer/backend/webgpu/Device.h').read_bytes()
    if relative=='renderer/backend/webgpu/Device.cpp':dependencies+=(root/'renderer/backend/webgpu/CommandQueue.h').read_bytes()+(root/'renderer/backend/webgpu/CommandData.h').read_bytes()
    if relative in ['main.cpp','renderer/backend/webgpu/Device.cpp']:dependencies+=Path('/phase4-harness/application-deferred-audio.h').read_bytes()
    if relative in ['main.cpp','ps/Replay.cpp','renderer/backend/webgpu/Device.cpp']:dependencies+=Path('/phase4-harness/application-deferred-replay.h').read_bytes()
    if relative=='main.cpp':dependencies+=Path('/phase4-harness/application-clock.h').read_bytes()+Path('/phase4-harness/application-frame-time.h').read_bytes()
    if relative=='graphics/ObjectBase.cpp':dependencies+=(root/'graphics/VisualVariantRandom.h').read_bytes()
    identity=hashlib.sha256((root/relative).read_bytes()+dependencies+json.dumps(command).encode()).hexdigest()
    old=results.get(relative)
    if old and old.get('identity')==identity and old['exitCode']==0 and obj.exists():return old
    with log.open('w') as stream:p=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    print(relative,p.returncode,flush=True)
    return dict(source=relative,object=str(obj),log=str(log),exitCode=p.returncode,command=command,identity=identity,sourceSHA256=hashlib.sha256((root/relative).read_bytes()).hexdigest())
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(compile_unit,['main.cpp','ps/Replay.cpp','ps/VideoMode.cpp','graphics/ShaderManager.cpp','graphics/ObjectBase.cpp','renderer/backend/webgpu/Device.cpp']+coordinate_units):results[result['source']]=result
report['results']=list(results.values());report['status']='COMPILE_FAILED' if any(r['exitCode'] for r in results.values()) else 'COMPILE_PASSED_NOT_LINKED'
report['engineBackend']='webgpu';report['phase45Accepted']=False
(out/'compile-report.json').write_text(json.dumps(report,indent=2))
raise SystemExit(report['status']=='COMPILE_FAILED')
