from pathlib import Path
import difflib
path = Path('/spike/mozjs-128.13.0/memory/mozalloc/mozalloc_abort.cpp')
before = path.read_text()
old = '!defined(LIBFUZZER)'
assert before.count(old) == 1
after = before.replace(old, '!defined(LIBFUZZER) && !defined(__EMSCRIPTEN__)')
path.write_text(after)
Path('/spike/evidence/emscripten-abort.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/memory/mozalloc/mozalloc_abort.cpp', tofile='b/memory/mozalloc/mozalloc_abort.cpp')))
