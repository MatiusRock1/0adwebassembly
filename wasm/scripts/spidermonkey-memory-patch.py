from pathlib import Path
import difflib
path = Path('/spike/mozjs-128.13.0/js/src/gc/Memory.cpp')
before = path.read_text()
after = before.replace('#ifndef __wasi__', '#if !defined(__wasi__)')
after = after.replace('#ifdef __wasi__', '#if defined(__wasi__) || defined(__EMSCRIPTEN__)')
after = after.replace('!defined(__wasi__)', '!defined(__wasi__) && !defined(__EMSCRIPTEN__)')
after = after.replace('#elif defined(__wasi__)', '#elif defined(__wasi__) || defined(__EMSCRIPTEN__)')
assert after != before
path.write_text(after)
Path('/spike/evidence/emscripten-gc-memory.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/js/src/gc/Memory.cpp', tofile='b/js/src/gc/Memory.cpp')))
