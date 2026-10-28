from pathlib import Path
import difflib
root = Path('/spike/mozjs-128.13.0')
diff = []
for name in ('js/src/vm/JSONPrinter.h', 'js/src/vm/JSONPrinter.cpp'):
    path = root / name
    before = path.read_text()
    guard = '#if defined(XP_DARWIN) || defined(__OpenBSD__) || defined(__wasi__)'
    assert before.count(guard) == 1, name
    after = before.replace(guard, guard + ' || defined(__EMSCRIPTEN__)')
    path.write_text(after)
    diff.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
Path('/spike/evidence/emscripten-json-size.patch').write_text(''.join(diff))