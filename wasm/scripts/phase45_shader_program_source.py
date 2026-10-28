"""Add WebGL parallel program polling to the GLES-patched ShaderProgram.cpp.

The browser build adapts this file for GLSL ES (parallax loop bound, shadow
PCF helper). Copying the raw workspace file instead drops those adaptations,
so the parallel-compile blocks are inserted into the patched text. They must
match the WASM_PARALLEL_SHADER_COMPILE blocks in source/renderer/backend/gl.
"""
import re
from pathlib import Path

_WORKSPACE = Path(__file__).resolve().parents[2] / 'source/renderer/backend/gl/ShaderProgram.cpp'
_BLOCK = re.compile(r'#if defined\(WASM_PARALLEL_SHADER_COMPILE\)\n.*?#endif\n', re.S)
_ANCHORS = ['#include "precompiled.h"\n', '\tglCompileShader(shader);\n', '\tglLinkProgram(m_Program);\n']


def parallel_compile_source(patched, workspace=None):
    """Return the patched GLES text with the workspace's parallel blocks inserted."""
    workspace = (workspace or _WORKSPACE.read_text()).replace('\r\n', '\n')
    patched = patched.replace('\r\n', '\n')
    blocks = _BLOCK.findall(workspace)
    if len(blocks) != len(_ANCHORS):
        raise RuntimeError('Unexpected WASM_PARALLEL_SHADER_COMPILE blocks in ShaderProgram.cpp')
    if 'WASM_PARALLEL_SHADER_COMPILE' in patched:
        raise RuntimeError('Patched ShaderProgram.cpp already contains parallel compile blocks')
    if 'phase4BilinearShadow' not in patched or 'i < 20; ++i) { if (i >= iter) break;' not in patched:
        raise RuntimeError('ShaderProgram.cpp lacks the browser GLES adaptations')
    for anchor, block in zip(_ANCHORS, blocks):
        if patched.count(anchor) != 1:
            raise RuntimeError('Unexpected ShaderProgram.cpp anchor: ' + anchor.strip())
        # The workspace places each block directly after its anchor line.
        patched = patched.replace(anchor, anchor + block)
    return patched
