#!/usr/bin/env bash
set -euo pipefail
root=/spike/0ad-source
obj=/spike/mozjs-128.13.0/build-wasm
mkdir -p /spike/headless/objects /spike/headless/include /spike/evidence/headless
cp -a /build/0ad/source "$root"
cp -a /usr/include/boost /usr/include/fmt /spike/headless/include/
python3 - "$root" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
path = root / 'lib/sysdep/arch.h'
text = path.read_text()
text = text.replace('// ensure exactly one architecture has been detected', '#if defined(__wasm32__)\n# define ARCH_WASM32 1\n#else\n# define ARCH_WASM32 0\n#endif\n\n// ensure exactly one architecture has been detected')
text = text.replace('ARCH_LOONG64+ARCH_RISCV64)', 'ARCH_LOONG64+ARCH_RISCV64+ARCH_WASM32)')
path.write_text(text)
PY
flags=(-std=c++20 -pthread -O0 -g -ffunction-sections -fdata-sections
  -DFMT_HEADER_ONLY -DNDEBUG -DCONFIG_ENABLE_PCH=0
  -DCONFIG2_AUDIO=0 -DCONFIG2_NVTT=0 -DCONFIG2_LOBBY=0
  -I/spike/headless/adapters -I"$root" -I"$root/pch/scriptinterface" -I/spike/headless/include
  -I"$obj/dist/include")
status=0
for source in Context Interface Conversions Exceptions JSON ModuleLoader Promises Stats StructuredClone; do
  echo "Compiling actual scriptinterface/$source.cpp"
  if ! em++ "${flags[@]}" -c "$root/scriptinterface/$source.cpp" -o "/spike/headless/objects/$source.o" > "/spike/evidence/headless/$source.log" 2>&1; then
    status=1
    tail -25 "/spike/evidence/headless/$source.log"
  fi
done
for source in ps/CStr ps/Errors ps/Filesystem lib/utf8 lib/secure_crt lib/status lib/sysdep/rtl/gcc/gcc; do
  name=${source//\//_}
  echo "Compiling support $source.cpp"
  if ! em++ "${flags[@]}" -c "$root/$source.cpp" -o "/spike/headless/objects/$name.o" > "/spike/evidence/headless/$name.log" 2>&1; then
    status=1
    tail -20 "/spike/evidence/headless/$name.log"
  fi
done
em++ "${flags[@]}" -DWSECURE_CRT -c "$root/lib/secure_crt.cpp" -o /spike/headless/objects/lib_wsecure_crt.o > /spike/evidence/headless/lib_wsecure_crt.log 2>&1 || status=1
em++ "${flags[@]}" -c /spike/headless-platform.cpp -o /spike/headless/objects/platform.o > /spike/evidence/headless/platform.log 2>&1 || status=1
echo "$status" > /spike/evidence/headless/compile-exit-code.txt
exit 0
