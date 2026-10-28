"""Compile only the browser application against cached original engine objects."""
import json
import subprocess
from pathlib import Path
root = Path('/spike/phase2-source')
sm = Path('/spike/mozjs-128.13.0/build-wasm')
out = Path('/spike/phase2-link')
adapters = Path('/spike/phase2-adapters')
flags = ['em++', '-std=c++20', '-pthread', '-fexceptions', '-O0', '-ffunction-sections', '-fdata-sections',
         '-ferror-limit=3', '-DFMT_HEADER_ONLY', '-DNDEBUG', '-DCONFIG_ENABLE_PCH=0',
         '-DCONFIG2_AUDIO=0', '-DCONFIG2_NVTT=0', '-DCONFIG2_LOBBY=0', '-DCONFIG2_FILE_ENABLE_AIO=0',
         '-DCONFIG2_GLES=1', '-sUSE_SDL=2', '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-I' + str(adapters),
         '-include', str(adapters / 'ps/Profiler2.h'), '-I' + str(root),
         '-I' + str(root / 'pch/scriptinterface'), '-I' + str(root / 'lib'),
         '-I/spike/headless/include', '-I' + str(sm / 'dist/include'),
         '-I' + str(root / 'third_party/glad/include')]

report = json.loads((out / 'report.json').read_text())
for source, name in [('/spike/wasm/harness/scene-main.cpp', 'scene-runtime-main'),
                     (str(root / 'renderer/RenderModifiers.cpp'), 'scene-player-colors')]:
    obj = str(out / ('objects/' + name + '.o'))
    log_path = out / (name + '.log')
    with log_path.open('w') as log:
        result = subprocess.run(flags + ['-c', source, '-o', obj], stdout=log, stderr=subprocess.STDOUT)
    report['sceneCompile'] = [r for r in report['sceneCompile'] if r['source'] != source] + [dict(source=source, object=obj, exitCode=result.returncode)]
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    if result.returncode:
        print(log_path.read_text())
        raise SystemExit(result.returncode)
print('SCENE_APPLICATION_COMPILE_PASSED', flush=True)
