from pathlib import Path
import difflib
path = Path('/spike/mozjs-128.13.0/js/src/threading/posix/PosixThread.cpp')
before = path.read_text()
old = '  int rv;\n#ifdef XP_DARWIN\n  rv = pthread_setname_np(name);'
assert before.count(old) == 1
after = before.replace(old, '  int rv;\n#ifdef __EMSCRIPTEN__\n  emscripten_set_thread_name(pthread_self(), name);\n  rv = 0;\n#elif defined(XP_DARWIN)\n  rv = pthread_setname_np(name);')
after = '#ifdef __EMSCRIPTEN__\n#include <emscripten/threading.h>\n#endif\n' + after
path.write_text(after)
Path('/spike/evidence/emscripten-thread-name.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/js/src/threading/posix/PosixThread.cpp', tofile='b/js/src/threading/posix/PosixThread.cpp')))
