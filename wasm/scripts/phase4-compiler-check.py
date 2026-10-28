"""Verify the fmt compatibility backport with valid and invalid format strings."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

out = Path('/phase4-build')
with tempfile.TemporaryDirectory(prefix='phase4-fmt-') as temporary:
    root = Path(temporary)
    shutil.copytree('/spike/headless/include/fmt', root / 'fmt')
    header = root / 'fmt/core.h'
    before = header.read_text()
    after = before.replace('parse_format_string<true>(str_, checker(s, {}))',
                           'parse_format_string<true>(str_, checker(str_, {}))')
    assert after != before
    header.write_text(after)
    flags = ['em++', '-std=c++20', '-pthread', '-DFMT_HEADER_ONLY', '-I' + str(root)]
    valid = root / 'valid.cpp'
    valid.write_text('#include <fmt/format.h>\nint main(){auto v=fmt::format(FMT_STRING("{:.1f} {:08x}"),12.5,42);fmt::print("{}\\n",v);return v=="12.5 0000002a"?0:1;}\n')
    valid_compile = subprocess.run(flags + [str(valid), '-o', str(root / 'valid.js')],
                                   capture_output=True, text=True)
    execution = subprocess.run(['node', str(root / 'valid.js')], capture_output=True, text=True) if not valid_compile.returncode else None
    invalid = root / 'invalid.cpp'
    invalid.write_text('#include <fmt/format.h>\nint main(){auto v=fmt::format(FMT_STRING("{:s}"),42);}\n')
    invalid_compile = subprocess.run(flags + ['-c', str(invalid), '-o', str(root / 'invalid.o')],
                                     capture_output=True, text=True)
    report = dict(passed=valid_compile.returncode == 0 and execution is not None
                  and execution.returncode == 0 and invalid_compile.returncode != 0,
                  validCompileExitCode=valid_compile.returncode,
                  runtimeExitCode=execution.returncode if execution else None,
                  runtimeOutput=execution.stdout if execution else None,
                  invalidFormatRejected=invalid_compile.returncode != 0,
                  headerBefore=hashlib.sha256(before.encode()).hexdigest(),
                  headerAfter=hashlib.sha256(after.encode()).hexdigest(),
                  upstream='https://github.com/fmtlib/fmt/commit/6797f0c39a4ef13061cbc3bb850c35af7428fdc4')
    (out / 'fmt-valid.log').write_text(valid_compile.stdout + valid_compile.stderr)
    (out / 'fmt-invalid.log').write_text(invalid_compile.stdout + invalid_compile.stderr)
    (out / 'fmt-check.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
