"""Compile genuine map/VFS/renderer entry units; no link or runtime claims."""
import json
import shutil
import subprocess
from pathlib import Path

source = Path('/spike/phase2-source')
shutil.copytree('/build/0ad/source', source, dirs_exist_ok=True)
# Reuse only the documented architecture adaptation; component registration remains original.
shutil.copy2('/spike/0ad-source/lib/sysdep/arch.h', source / 'lib/sysdep/arch.h')
out = Path('/spike/phase2-audit')
out.mkdir(exist_ok=True)
# Emscripten has synchronous MEMFS I/O but no POSIX AIO header. The engine's
# existing non-AIO path still uses aiocb as an operation descriptor.
import difflib
aio = source / 'lib/posix/posix_aio.h'
before = aio.read_text()
after = before.replace('#include <fcntl.h>', '#include <fcntl.h>\n#if defined(__EMSCRIPTEN__)\n#include <signal.h>\n#endif')
after = after.replace('#elif OS_ANDROID || OS_OPENBSD', '#elif OS_ANDROID || OS_OPENBSD || defined(__EMSCRIPTEN__)')
assert after != before
aio.write_text(after)
(out / 'emscripten-aio.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/lib/posix/posix_aio.h', tofile='b/lib/posix/posix_aio.h')))

# Fix stale desktop-only checks and self-aliases in the original GLES path.
import re
for relative in ['lib/external_libraries/opengles2_wrapper.h', 'renderer/backend/gl/Device.cpp']:
    path = source / relative
    before = path.read_text()
    if relative.endswith('opengles2_wrapper.h'):
        after = re.sub(r'^#define (gl\w+) \1\s*$', '', before, flags=re.MULTILINE)
    else:
        after = before.replace('glGetQueryiv(parameter, GL_QUERY_COUNTER_BITS, values);',
          '{\n#if CONFIG2_GLES\n            static_assert(!doQueryCounterBits, "Query counter bits require desktop GL");\n#else\n            glGetQueryiv(parameter, GL_QUERY_COUNTER_BITS, values);\n#endif\n        }')
        after = after.replace('if (!minimumRequiredGLVersionSupported || !GLAD_GL_EXT_framebuffer_object)',
          '#if CONFIG2_GLES\n    const bool hasFramebufferObjects = true; // Core in GLES 2.0 and newer.\n#else\n    const bool hasFramebufferObjects = GLAD_GL_EXT_framebuffer_object;\n#endif\n    if (!minimumRequiredGLVersionSupported || !hasFramebufferObjects)')
    assert after != before, relative
    path.write_text(after)
    (out / (Path(relative).name + '.patch')).write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/' + relative, tofile='b/' + relative)))
sm = Path('/spike/mozjs-128.13.0/build-wasm')
flags = ['em++', '-std=c++20', '-pthread', '-fexceptions', '-fsyntax-only', '-ferror-limit=5',
         '-DFMT_HEADER_ONLY', '-DNDEBUG', '-DCONFIG_ENABLE_PCH=0', '-DCONFIG2_AUDIO=0',
         '-DCONFIG2_NVTT=0', '-DCONFIG2_LOBBY=0', '-DCONFIG2_FILE_ENABLE_AIO=0',
         '-I/spike/wasm/harness/adapters', '-I' + str(source),
         '-I' + str(source / 'pch/scriptinterface'), '-I' + str(source / 'lib'), '-I/spike/headless/include',
         '-I' + str(sm / 'dist/include'), '-I' + str(source / 'third_party/glad/include')]
units = ['simulation2/Simulation2.cpp', 'ps/scripting/JSInterface_VFS.cpp',
         'lib/file/vfs/vfs.cpp', 'lib/file/io/io.cpp', 'simulation2/components/CCmpPathfinder.cpp',
         'simulation2/components/CCmpUnitMotion_System.cpp', 'graphics/MapReader.cpp',
         'renderer/backend/gl/Device.cpp', 'renderer/backend/gl/Buffer.cpp',
         'renderer/backend/gl/ShaderProgram.cpp']
results = []
for unit in units:
    command = flags + (['-sUSE_SDL=2', '-DCONFIG2_GLES=1'] if unit.startswith(('graphics/', 'renderer/')) else []) + [str(source / unit)]
    name = unit.replace('/', '_') + '.log'
    with (out / name).open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    results.append({'source': unit, 'exitCode': result.returncode, 'log': name})
    print(unit, result.returncode, flush=True)
(out / 'compile-audit.json').write_text(json.dumps({'kind': 'syntax-only-not-a-game-build', 'units': results}, indent=2))
(out / 'sdl-sdk-port.py').write_text(Path('/emsdk/upstream/emscripten/tools/ports/sdl2.py').read_text())
(out / 'sdl-native-version.txt').write_text(subprocess.check_output(['pkg-config', '--modversion', 'sdl2'], text=True))
