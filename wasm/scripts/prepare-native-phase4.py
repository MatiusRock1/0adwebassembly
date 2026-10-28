"""Prepare an isolated original Windows application for full-game parity."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

root = Path(__file__).resolve().parents[2]
out = root / 'wasm/build/native-phase4'
pin = (root / 'BASE_COMMIT.txt').read_text().strip()
out.mkdir(parents=True, exist_ok=True)
archive = root / 'wasm/build/native-phase4-source.tar'
if not (out / 'source/main.cpp').exists():
    with archive.open('wb') as stream:
        subprocess.run(['git', '-c', 'safe.directory=' + root.as_posix(), 'archive', pin,
                        'source', 'build', 'libraries'], cwd=root, stdout=stream, check=True,
                       env=dict(os.environ, GIT_LFS_SKIP_SMUDGE='1', GIT_TERMINAL_PROMPT='0'))
    with tarfile.open(archive) as tar:
        tar.extractall(out, filter='data')
missing_tool_resources = []
for file in (out / 'source').rglob('*'):
    if file.is_file() and file.stat().st_size < 256:
        payload = file.read_bytes()
        if payload.startswith(b'version https://git-lfs.github.com/spec/v1'):
            oid = payload.decode().split('oid sha256:')[1].splitlines()[0]
            cached = root / '.git/lfs/objects' / oid[:2] / oid[2:4] / oid
            if not cached.is_file():
                if 'tools' not in file.relative_to(out / 'source').parts:
                    raise RuntimeError('Missing original cached dependency: ' + str(file))
                missing_tool_resources.append(str(file.relative_to(out)))
                continue
            assert hashlib.sha256(cached.read_bytes()).hexdigest() == oid
            shutil.copy2(cached, file)
(out / 'excluded-tools-resources.json').write_text(json.dumps(missing_tool_resources, indent=2))
libs = root / 'wasm/build/native-windows-libs'
if not (out / 'libraries/win64').exists():
    shutil.copytree(libs, out / 'libraries/win64')
for folder in libs.iterdir():
    if (folder / 'bin').is_dir():
        for file in (folder / 'bin').iterdir():
            if file.is_file():
                destination = out / ('build/bin' if folder.name in ['premake-core', 'cxxtest-4.4'] else 'binaries/system')
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, destination / file.name)
premake = out / 'build/premake/premake5.lua'
text = premake.read_text()
needle = '\t\tfiles { source_root.."lobby/Globals.cpp" }'
extra = '\t\tproject_add_extern_libs({"enet"}, "StaticLib")\n'
if extra + needle not in text:
    assert text.count(needle) == 1
    premake.write_text(text.replace(needle, extra + needle))

mailbox = out / 'source/phase4-native-mailbox.h'
mailbox.write_text('''#pragma once
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include "gui/CGUI.h"
#include "gui/GUIManager.h"
#include "scriptinterface/Interface.h"
inline void ProcessPhase4NativeRequest()
{
    const char* directory = std::getenv("PHASE4_NATIVE_AUTOMATION");
    if (!directory || !g_GUI || !g_GUI->GetActiveGUI()) return;
    const auto root = std::filesystem::u8path(directory);
    static unsigned sequence = 1;
    const std::string suffix = std::to_string(sequence);
    const auto request = root / ("request-" + suffix + ".js");
    if (!std::filesystem::exists(request)) return;
    std::ifstream input(request);
    if (!input.is_open()) return;
    const std::string code((std::istreambuf_iterator<char>(input)), {});
    input.close();
    if (code.empty()) return;
    std::string result;
    const auto activeGUI = g_GUI->GetActiveGUI();
    const bool success = activeGUI->GetScriptInterface()->Eval(code, result);
    std::ofstream response(root / ("response-" + suffix + ".txt"));
    response << (success ? result : "SCRIPT_EVALUATION_FAILED");
    response.close();
    std::ofstream ready(root / ("ready-" + suffix));
    ready << "ready";
    ready.close();
    ++sequence;
}
''')
main = out / 'source/main.cpp'
text = main.read_text()
if '#include "phase4-native-mailbox.h"' not in text:
    text = text.replace('#include "lib/precompiled.h"', '#include "lib/precompiled.h"\n#include "phase4-native-mailbox.h"')
    needle = '\t\t\t\t\tif (isVisual)\n\t\t\t\t\t{'
    assert text.count(needle) == 1
    text = text.replace(needle, needle + '\n\t\t\t\t\t\tProcessPhase4NativeRequest();')
    main.write_text(text)
for mod in ['mod', 'public']:
    directory = out / 'binaries/data/mods' / mod
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / (mod + '.zip')
    if not destination.exists():
        os.link(root / 'wasm/dist/application-phase4' / (mod + '.zip'), destination)
shutil.copytree(root / 'wasm/dist/application-phase4/data/config', out / 'binaries/data/config', dirs_exist_ok=True)
shutil.copytree(root / 'wasm/dist/application-phase4/data/l10n', out / 'binaries/data/l10n', dirs_exist_ok=True)
command = [str(out / 'build/bin/premake5.exe'), '--without-atlas', '--without-tests',
           '--without-lobby', '--without-miniupnpc', '--without-pch', '--without-dap-interface',
           '--without-nvtt', 'vs2022']
subprocess.run(command, cwd=out / 'build/premake', check=True,
               env=dict(os.environ, HOSTTYPE='amd64'))
print('NATIVE_PHASE4_PREPARED_NOT_COMPILED', flush=True)
