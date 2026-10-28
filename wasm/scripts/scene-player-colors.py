"""Explicit presentation dependency for scenes without a desktop CGame owner."""
import difflib
from pathlib import Path

def apply_bridge(root):
    header = root / 'renderer/RenderModifiers.h'
    source = root / 'renderer/RenderModifiers.cpp'
    before_h, before_cpp = header.read_text(), source.read_text()
    if 'SetScenePlayerColors' in before_h:
        return ''
    after_h = before_h.replace('#include <cstdint>', '#include <cstdint>\n#include <vector>\n\n// Empty restores the original desktop CGame color provider.\nvoid SetScenePlayerColors(const std::vector<CColor>& colors);')
    code = '''
namespace {
std::vector<CColor> scenePlayerColors;
const CColor& ScenePlayerColor(int player)
{
 if (scenePlayerColors.empty()) { ENSURE(g_Game); return g_Game->GetPlayerColor(player); }
 static const CColor brokenColor(1,0,1,1);
 if (player<0 || static_cast<size_t>(player)>=scenePlayerColors.size()) return brokenColor;
 return scenePlayerColors[player];
}
}
void SetScenePlayerColors(const std::vector<CColor>& colors) { scenePlayerColors=colors; }
'''
    after_cpp = before_cpp.replace('g_Game->GetPlayerColor(0)', 'ScenePlayerColor(0)').replace('g_Game->GetPlayerColor(model->GetPlayerID())', 'ScenePlayerColor(model->GetPlayerID())')
    # Insert after includes/externs, before the original first implementation.
    marker = 'LitRenderModifier::LitRenderModifier()'
    assert marker in after_cpp and after_cpp != before_cpp
    after_cpp = after_cpp.replace(marker, code + '\n' + marker, 1)
    header.write_text(after_h); source.write_text(after_cpp)
    return ''.join(difflib.unified_diff(before_h.splitlines(True), after_h.splitlines(True), fromfile='a/source/renderer/RenderModifiers.h', tofile='b/source/renderer/RenderModifiers.h')) + ''.join(difflib.unified_diff(before_cpp.splitlines(True), after_cpp.splitlines(True), fromfile='a/source/renderer/RenderModifiers.cpp', tofile='b/source/renderer/RenderModifiers.cpp'))

if __name__ == '__main__':
    import sys
    Path(sys.argv[2]).write_text(apply_bridge(Path(sys.argv[1])))
