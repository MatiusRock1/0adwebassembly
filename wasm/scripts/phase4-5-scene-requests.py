"""Derive shader requests from original material/effect declarations.

Contexts preserve the default scene configuration, preload and LOS paths.
Water options come from the original TerrainRenderer::RenderFancyWater.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

base=Path('/build/0ad/binaries/data/mods')
effects={}
for mod in ['mod','public']:
    for path in (base/mod/'shaders/effects').rglob('*.xml'):
        effects[path.relative_to(base/mod/'shaders/effects').with_suffix('').as_posix()]=ET.parse(path).getroot()
shadow=dict(USE_SHADOW='1',USE_SHADOW_SAMPLER='1',SHADOWS_CASCADE_COUNT='1',RENDER_DEBUG_MODE='RENDER_DEBUG_MODE_NONE')
contexts=[{},dict(RENDER_DEBUG_MODE='RENDER_DEBUG_MODE_NONE'),shadow,{**shadow,'USE_SHADOW_PCF':'1'}]
contexts += [{**context,'IGNORE_LOS':'1'} for context in contexts]
requests=[]
for mod in ['mod','public']:
    for path in (base/mod/'art/materials').glob('*.xml'):
        material=ET.parse(path).getroot()
        defines={d.attrib['name']:d.attrib['value'] for d in material.findall('define')}
        defines.update({t.attrib['define']:'1' for t in material.findall('required_texture') if t.get('define')})
        for shader in material.findall('shader'):
            if shader.attrib['pass'] in ['wireframe','wireframe_solid']:continue
            effect=effects.get(shader.attrib['effect'])
            if effect is None:continue
            for technique in effect.findall('technique'):
                for shader_pass in technique.findall('pass'):
                    program=shader_pass.get('shader')
                    if not program:continue
                    extra={d.attrib['name']:d.attrib['value'] for node in [effect,technique,shader_pass] for d in node.findall('define')}
                    for context in contexts:
                        for instancing in [False,True]:
                            flags={**defines,**context,**extra}
                            if instancing:flags['USE_INSTANCING']='1'
                            programs=['terrain_base','terrain_blend','terrain_decal'] if program=='terrain_base' else [program]
                            for resolved in programs:requests.append(dict(name='glsl/'+resolved,defines=flags))
water_flags=['USE_REAL_DEPTH','USE_FANCY_EFFECTS','USE_REFRACTION','USE_REFLECTION']
for context in contexts:
    # IGNORE_LOS is used by overlay/model effects, not fancy water: the
    # original water vertex shader always calculates LOS coordinates.
    if 'IGNORE_LOS' in context:continue
    for mask in range(1<<len(water_flags)):
        flags={**context,**{name:'1' for bit,name in enumerate(water_flags) if mask&(1<<bit)}}
        requests.append(dict(name='glsl/water_high',defines=flags))
requests=list({json.dumps(r,sort_keys=True):r for r in requests}.values())
output=Path('/phase45-build/scene-requests.json');output.write_text(json.dumps(requests,indent=2))
print(len(requests),'requests derived from original materials/effects',flush=True)
