#!/usr/bin/env bash
set -euo pipefail
root=/spike/0ad-source
obj=/spike/mozjs-128.13.0/build-wasm
mkdir -p /spike/evidence/simulation /spike/simulation/objects
cp -a /usr/include/unicode /spike/headless/include/
cp -a /usr/include/libxml2/libxml /spike/headless/include/
python3 - "$root" <<'PY'
from pathlib import Path
import sys, difflib
root = Path(sys.argv[1])
path = root / 'simulation2/system/ComponentManager.cpp'
before = path.read_text()
after = before.replace('JSI_VFS::RegisterScriptFunctions_ReadOnlySimulation(m_ScriptInterface);', '// Headless fixture loads its script from C++; JS VFS APIs are excluded.')
after = after.replace('RegisterComponentInterface_##name(m_ScriptInterface);', 'if constexpr (IID_##name == IID_Test1 || IID_##name == IID_Test2) RegisterComponentInterface_##name(m_ScriptInterface);')
after = after.replace('RegisterComponentType_##name(*this);', 'if constexpr (CID_##name == CID_Test1A || CID_##name == CID_Test1B || CID_##name == CID_Test2A || CID_##name == CID_Test1Scripted || CID_##name == CID_Test2Scripted) RegisterComponentType_##name(*this);')
path.write_text(after)
Path('/spike/evidence/simulation/headless-component-registration.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/simulation2/system/ComponentManager.cpp', tofile='b/simulation2/system/ComponentManager.cpp')))
PY
flags=(-std=c++20 -pthread -O0 -g -ffunction-sections -fdata-sections
  -DFMT_HEADER_ONLY -DNDEBUG -DCONFIG_ENABLE_PCH=0 -DCONFIG2_AUDIO=0
  -I/spike/headless/adapters -I"$root" -I"$root/pch/scriptinterface"
  -I/spike/headless/include -I"$obj/dist/include")
status=0
for source in simulation2/system/ComponentManager simulation2/system/SimContext simulation2/system/IComponent simulation2/system/DynamicSubscription simulation2/system/ParamNode simulation2/scripting/ScriptComponent simulation2/scripting/MessageTypeConversions simulation2/components/CCmpTest simulation2/components/ICmpTest simulation2/scripting/EngineScriptConversions simulation2/serialization/ISerializer lib/file/vfs/vfs_util lib/regex
do
  name=${source//\//_}
  if ! em++ "${flags[@]}" -c "$root/$source.cpp" -o "/spike/simulation/objects/$name.o" > "/spike/evidence/simulation/$name.log" 2>&1; then
    status=1
    tail -25 "/spike/evidence/simulation/$name.log"
  fi
done
echo "$status" > /spike/evidence/simulation/compile-exit-code.txt
