"""Inventory source evidence without changing upstream files or Git metadata."""
import collections
import datetime
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs' / 'wasm' / 'evidence'


def git(*args):
    result = subprocess.run(
        ['git', '--git-dir=' + str(ROOT / '.git'), '--work-tree=' + str(ROOT), *args],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return {'exit_code': result.returncode, 'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    build = (ROOT / 'libraries/source/spidermonkey/build.sh').read_text(encoding='utf-8')
    api = collections.Counter()
    matches = []
    pattern = re.compile(r'\b(?:JS_[A-Za-z0-9_]+|JS::[A-Za-z0-9_]+)\b')
    os_pattern = re.compile(r'\b(?:dlopen|fork|socket|pthread_\w+|mmap|mprotect)\s*\(|std::thread|#\s*include\s*[<"](?:windows\.h|pthread\.h|sys/socket\.h|dlfcn\.h)')
    for folder in ['source/scriptinterface', 'source/simulation2', 'source/lib', 'source/ps', 'source/network']:
        for path in sorted((ROOT / folder).rglob('*')):
            if path.suffix not in {'.cpp', '.h', '.hpp'}:
                continue
            for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                if folder == 'source/scriptinterface':
                    api.update(pattern.findall(line))
                if os_pattern.search(line):
                    matches.append({'path': path.relative_to(ROOT).as_posix(), 'line': number, 'text': line.strip()})
    report = {
        'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'head': git('rev-parse', 'HEAD'),
        'remotes': git('remote', '-v'),
        'index_exists': (ROOT / '.git/index').is_file(),
        'index_lock_exists': (ROOT / '.git/index.lock').exists(),
        'spidermonkey_version': re.search(r'^PV=(.+)$', build, re.M)[1],
        'spidermonkey_library_version': re.search(r'^LIB_VERSION="(.+)"$', build, re.M)[1].replace('${PV}', re.search(r'^PV=(.+)$', build, re.M)[1]),
        'js_api_lexical_occurrences': dict(sorted(api.items())),
        'os_api_candidates': matches,
        'limitations': ['Lexical matches include comments/tests and are not a call graph.',
                         'No compilation or runtime compatibility established by this report.']}
    (OUT / 'source-audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Audit: {len(api)} JS API identifiers; {len(matches)} OS candidates; index={report["index_exists"]}; lock={report["index_lock_exists"]}')


if __name__ == '__main__':
    main()
