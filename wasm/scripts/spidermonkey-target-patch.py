"""Experimental target recognition only; does not assert OS API compatibility."""
from pathlib import Path
import difflib

root = Path('/spike/mozjs-128.13.0')
evidence = Path('/spike/evidence')
changes = []
constants = root / 'python/mozbuild/mozbuild/configure/constants.py'
before = constants.read_text()
assert before.count('        "WASI",') == 2
after = before.replace('        "WASI",', '        "WASI",\n        "Emscripten",')
macro = '    "WASI": "__wasi__",'
assert after.count(macro) == 1
after = after.replace(macro, macro + '\n    "Emscripten": "__EMSCRIPTEN__",')
changes.append((constants, before, after))
init = root / 'build/moz.configure/init.configure'
before = init.read_text()
needle = '    elif os.startswith("wasi") and allow_wasi:\n'
assert before.count(needle) == 1
after = before.replace(needle, '    elif os.startswith("emscripten") and allow_wasi:\n        canonical_os = canonical_kernel = "Emscripten"\n' + needle)
changes.append((init, before, after))
patch = []
for path, before, after in changes:
    relative = path.relative_to(root).as_posix()
    patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/' + relative, tofile='b/' + relative))
    path.write_text(after)
(evidence / 'emscripten-target-recognition.patch').write_text(''.join(patch))
