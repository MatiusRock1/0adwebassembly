"""Translate original shader variants offline: adapted GLSL -> SPIR-V -> WGSL.

Art and original shader files are never overwritten. Each generated variant
retains source/tool hashes and reflection. A failed variant is not shipped.
"""
import argparse
import concurrent.futures
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET

STREAMS = dict(pos=0, normal=1, color=2, **{f'uv{i}':3+i for i in range(8)})
BUILD_FINGERPRINT=''


def run(command):
    p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError(' '.join(map(str, command)) + '\n' + p.stdout + p.stderr)
    return p.stdout


def remove_line_records(path):
    # Preserve OpName/member names for reflection, but Naga 24 does not accept
    # debug OpLine records among type declarations emitted by glslc -g.
    raw=path.read_bytes();words=struct.unpack('<'+'I'*(len(raw)//4),raw)
    output=list(words[:5]);offset=5
    while offset<len(words):
        length=words[offset]>>16;opcode=words[offset]&65535
        if not length:raise ValueError('Invalid SPIR-V instruction length')
        if opcode not in [8,317]:output.extend(words[offset:offset+length])
        offset+=length
    path.write_bytes(struct.pack('<'+'I'*len(output),*output))


def prepare_source(source, output):
    shutil.copytree(source, output, dirs_exist_ok=True)
    text = (source / 'common/uniform.h').read_text()
    text = text.replace('layout (push_constant) uniform DrawUniforms', 'layout (std140, set = 0, binding = 1) uniform DrawUniforms')
    (output / 'common/uniform.h').write_text(text)
    vertex=output/'common/vertex.h'
    vertex_text=re.sub(r'\bposition\b','webgpuClipPosition',vertex.read_text())
    # WebGPU keeps NDC +Y upwards (unlike Vulkan). Its texture origin is still
    # upper-left; only the depth conversion from the original GL is required.
    vertex_text=vertex_text.replace('webgpuClipPosition.y = -webgpuClipPosition.y;', '')
    vertex.write_text(vertex_text)
    for path in output.rglob('*'):
        if path.suffix in ['.vs','.fs','.cs']:
            text=path.read_text()
            text=re.sub(r'#version\s+\d+[^\n]*', '#version 450', text)
            if path.name=='model_common.fs':
                # The original relief loop varies per fragment. Compute texture
                # gradients before that branch and use explicit gradients within
                # it, retaining the original height samples and iteration count.
                text=text.replace('float h = SAMPLE_2D(GET_DRAW_TEXTURE_2D(normTex), coord).a;',
                    'vec2 webgpuDx = dFdx(coord); vec2 webgpuDy = dFdy(coord);\n    float h = textureGrad(GET_DRAW_TEXTURE_2D(normTex), coord, webgpuDx, webgpuDy).a;')
                text=text.replace('h = SAMPLE_2D(GET_DRAW_TEXTURE_2D(normTex), coord).a;',
                    'h = textureGrad(GET_DRAW_TEXTURE_2D(normTex), coord, webgpuDx, webgpuDy).a;')
                text=text.replace('SAMPLE_2D(GET_DRAW_TEXTURE_2D(normTex), coord - move)',
                    'textureGrad(GET_DRAW_TEXTURE_2D(normTex), coord - move, webgpuDx, webgpuDy)')
            if path.name=='water_high.fs':
                # Keep the original invisible-water output, but select it after
                # sampling so neighbouring fragments retain valid derivatives.
                early=r'\s*if \(los < 0\.001\)\s*\{\s*OUTPUT_FRAGMENT_SINGLE_COLOR\(vec4\(0\.0, 0\.0, 0\.0, 1\.0\)\);\s*return;\s*\}'
                text,count=re.subn(early,'',text)
                assert count==1,'Original invisible-water branch changed'
                output='OUTPUT_FRAGMENT_SINGLE_COLOR(vec4(applyDebugColor(color * los, 1.0, refrColor.a, 0.0), refrColor.a));'
                text=text.replace(output,'if (los < 0.001) { OUTPUT_FRAGMENT_SINGLE_COLOR(vec4(0.0, 0.0, 0.0, 1.0)); } else { '+output+' }')
                sky='SAMPLE_CUBE(GET_DRAW_TEXTURE_CUBE(skyCube), (vec4(eye, 0.0) * skyBoxRot).xyz).rgb'
                text=text.replace('if (refTex.a < 0.4)', 'vec3 webgpuSky = '+sky+';\n\tif (refTex.a < 0.4)')
                text=text.replace('mix('+sky+', refTex.rgb, refTex.a)','mix(webgpuSky, refTex.rgb, refTex.a)')
            if path.name=='compute_upscale_fsr.cs':
                # Naga 24's SPIR-V reader lacks OpImageGather. Preserve GLSL's
                # four texel/component ordering with clamped level-zero fetches.
                helper='''
vec4 webgpuGather(sampler2D source, vec2 uv, int component) {
  ivec2 size = textureSize(source, 0);
  ivec2 base = ivec2(floor(uv * vec2(size) - 0.5));
  return vec4(texelFetch(source, clamp(base+ivec2(0,1),ivec2(0),size-1),0)[component],
              texelFetch(source, clamp(base+ivec2(1,1),ivec2(0),size-1),0)[component],
              texelFetch(source, clamp(base+ivec2(1,0),ivec2(0),size-1),0)[component],
              texelFetch(source, clamp(base,ivec2(0),size-1),0)[component]);
}
'''
                text=text.replace('AF4 FsrEasuRF',helper+'\nAF4 FsrEasuRF').replace('textureGather(', 'webgpuGather(')
            path.write_text(text)


def split_samplers(text):
    """Split combined GLSL samplers, including helper function parameters."""
    samplers={};functions={}
    def uniform(match):
        binding=int(match[2]);kind=match[3];name=match[4];samplers[name]=kind
        image='textureCube' if kind=='samplerCube' else 'texture2D'
        return f'layout(set=1,binding={binding*2}) uniform {image} {name}; layout(set=1,binding={binding*2+1}) uniform sampler {name}_sampler;'
    text=re.sub(r'layout\s*\(\s*set\s*=\s*(1)\s*,\s*binding\s*=\s*(\d+)\s*\)\s*uniform\s+(sampler2DShadow|sampler2D|samplerCube)\s+(\w+)\s*;',uniform,text)
    def declaration(match):
        name=match[1];parameters=match[2].split(',') if match[2].strip() else []
        positions=[];rewritten=[]
        for index,param in enumerate(parameters):
            sampler=re.search(r'\b(sampler2DShadow|sampler2D|samplerCube)\s+(\w+)\b',param)
            if sampler:
                kind,var=sampler.groups();samplers[var]=kind;positions.append(index)
                image='textureCube' if kind=='samplerCube' else 'texture2D'
                rewritten.append(re.sub(r'\b'+kind+r'\s+'+var+r'\b',f'{image} {var}, sampler {var}_sampler',param))
            else:rewritten.append(param)
        if positions:functions[name]=positions
        return name+'('+','.join(rewritten)+') {'
    text=re.sub(r'\b(\w+)\s*\(([^{};]*)\)\s*\{',declaration,text)
    for name,positions in functions.items():
        changes=[]
        for match in re.finditer(r'\b'+re.escape(name)+r'\s*\(',text):
            start=match.end();depth=1;end=start
            while end<len(text) and depth:
                depth += (text[end]=='(')-(text[end]==')');end+=1
            body=text[start:end-1]
            if re.search(r'\b(?:texture2D|textureCube)\s+\w+',body):continue
            args=[];last=0;depth=0
            for i,c in enumerate(body):
                depth+=(c=='(')-(c==')')
                if c==',' and depth==0:args.append(body[last:i]);last=i+1
            args.append(body[last:])
            for i in reversed(positions):
                var=args[i].strip()
                if not re.fullmatch(r'\w+',var):raise ValueError(f'Unsupported sampler helper argument {name}: {var}')
                args[i]=var+', '+var+'_sampler'
            changes.append((start,end-1,','.join(args)))
        for start,end,value in reversed(changes):text=text[:start]+value+text[end:]
    for name,kind in samplers.items():
        text=re.sub(r'\b(texture(?:Proj|Lod|Grad|Offset|Gather|Size|QueryLevels)?|texelFetch)\s*\(\s*\(*\s*'+re.escape(name)+r'\s*\)*\s*([,)])',
                    lambda m:m[1]+'('+kind+'('+name+', '+name+'_sampler)'+m[2],text)
    return text


def reflect_member(member):
    kind = member['type']
    matrix = re.match(r'mat(\d)(?:x(\d))?$', kind)
    vector = re.match(r'[iub]?vec(\d)$',kind)
    result = dict(name=member['name'],offset=member['offset'],type=kind)
    if matrix: result.update(columns=int(matrix[1]),rows=int(matrix[2] or matrix[1]))
    elif vector: result.update(columns=1,rows=int(vector[1]))
    else: result.update(columns=1,rows=1)
    for left,right in [('array_stride','arrayStride'),('matrix_stride','matrixStride')]:
        if left in member: result[right]=member[left]
    if 'array' in member:result['array']=member['array']
    return result


def compile_variant(name, xml, defines, source, output):
    key=json.dumps(dict(sorted(defines.items())),separators=(',',':'))
    identity=hashlib.sha256((name+key).encode()).hexdigest()
    cache=output/identity;cache.mkdir(parents=True,exist_ok=True)
    cached=cache/'variant.json'
    if cached.exists():
        record=json.loads(cached.read_text())
        if record['fingerprint']==BUILD_FINGERPRINT:return key,record['variant']
    variant=dict(code={},uniforms=[],textures=[],inputs=[],storage=[],sourceHashes={},buildFingerprint=BUILD_FINGERPRINT)
    uniforms={};textures={}
    streams={s.attrib['attribute']:STREAMS[s.attrib['name']] for s in xml.findall('.//stream')}
    flags=dict(defines)
    flags.update({d.attrib['name']:d.attrib['value'] for d in xml.findall('./define')})
    flags.update(USE_SPIRV='1',USE_DESCRIPTOR_INDEXING='0')
    for stage in ['vertex','fragment','compute']:
        node=xml.find(stage)
        if node is None:continue
        visibility={'vertex':1,'fragment':2,'compute':4}[stage]
        path=source/node.attrib['file'].removeprefix('glsl/')
        spv=cache/(stage+'.spv');wgsl=cache/(stage+'.wgsl')
        command=['glslc','-std=450core','--target-env=vulkan1.1','-fshader-stage='+stage,'-I'+str(source)]
        command += [f'-D{k}={v}' for k,v in sorted(flags.items())]
        command += [f'-DSTAGE_{stage.upper()}=1',str(path)]
        preprocessed=split_samplers(run(command+['-E']))
        generated=cache/(stage+'.glsl');generated.write_text(preprocessed)
        run(['glslc','--target-env=vulkan1.1','-g','-O','-fshader-stage='+stage,str(generated),'-o',str(spv)])
        remove_line_records(spv)
        run(['spirv-val','--target-env','vulkan1.1',str(spv)])
        reflection=json.loads(run(['spirv-cross',str(spv),'--reflect']))
        (cache/(stage+'-reflection.json')).write_text(json.dumps(reflection,indent=2))
        # Keep Vulkan clip coordinates; the original vertex macro already
        # converts OpenGL depth/Y to the WebGPU/Vulkan coordinate convention.
        run(['naga','--keep-coordinate-space',str(spv),str(wgsl)])
        code=wgsl.read_text()
        # Naga 24 loses NonWritable decorations on SSBO members. Restore the
        # access mode from the validated SPIR-V reflection, by block type.
        for buffer in reflection.get('ssbos',[]):
            if buffer.get('readonly',False):
                block=reflection['types'][buffer['type']]['name']
                code=re.sub(r'(var<storage, )read_write(>\s+\w+\s*:\s*'+re.escape(block)+r'\s*;)',r'\1read\2',code)
        variant['code'][stage]=code
        if stage == 'fragment':
            # A depth-only pass must still execute the original alpha discard.
            # Privatize colour outputs so the fragment entry has no colour targets.
            depth_source=re.sub(r'layout\s*\(\s*location\s*=\s*\d+\s*\)\s*out\s+', '', preprocessed)
            depth_glsl=cache/'fragment-depth.glsl'
            depth_spv=cache/'fragment-depth.spv'
            depth_wgsl=cache/'fragment-depth.wgsl'
            depth_glsl.write_text(depth_source)
            run(['glslc','--target-env=vulkan1.1','-g','-O','-fshader-stage=fragment',str(depth_glsl),'-o',str(depth_spv)])
            remove_line_records(depth_spv)
            run(['spirv-val','--target-env','vulkan1.1',str(depth_spv)])
            run(['naga','--keep-coordinate-space',str(depth_spv),str(depth_wgsl)])
            variant['code']['fragmentDepth']=depth_wgsl.read_text()
        variant['sourceHashes'][node.attrib['file']]=hashlib.sha256(path.read_bytes()).hexdigest()
        for block in reflection.get('ubos',[]):
            binding=block['binding']
            item=dict(binding=binding,size=block['block_size'],visibility=visibility,
                      members=[reflect_member(m) for m in reflection['types'][block['type']]['members']])
            if binding in uniforms:
                assert uniforms[binding]['members']==item['members'], 'Shared uniform layout mismatch'
                uniforms[binding]['visibility'] |= visibility
            else:uniforms[binding]=item
        for texture in reflection.get('separate_images',[]):
            binding=texture['binding'];kind=texture['type']
            item=dict(binding=binding,name=texture['name'],depth='Shadow' in kind,cube='Cube' in kind,visibility=visibility)
            # SPIRV-Cross reports texture2D for comparison images too; WGSL
            # reflects the actual depth type after usage analysis.
            if re.search(r'var\s+'+re.escape(texture['name'])+r'\s*:\s*texture_depth_',variant['code'][stage]):item['depth']=True
            if binding in textures:textures[binding]['visibility']|=visibility
            else:textures[binding]=item
        if stage=='vertex':
            for attribute in reflection.get('inputs',[]):
                if attribute['name'] in streams:variant['inputs'].append(dict(stream=streams[attribute['name']],location=attribute['location'],type=attribute['type']))
        for buffer in reflection.get('ssbos',[]):variant['storage'].append(dict(name=buffer['name'],type='storageBuffer',group=buffer['set'],binding=buffer['binding'],readonly=buffer.get('readonly',False),visibility=visibility))
        for image in reflection.get('images',[]):variant['storage'].append(dict(name=image['name'],type='storageTexture',group=image['set'],binding=image['binding'],readonly=image.get('readonly',False),format={'rgba8':'rgba8unorm','rgba16f':'rgba16float','rgba32f':'rgba32float'}.get(image.get('format'),image.get('format')),visibility=visibility))
    variant['uniforms']=sorted(uniforms.values(),key=lambda u:u['binding'])
    variant['textures']=sorted(textures.values(),key=lambda t:t['binding'])
    cached.write_text(json.dumps(dict(fingerprint=BUILD_FINGERPRINT,variant=variant),separators=(',',':')))
    return key,variant


def main():
    global BUILD_FINGERPRINT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('/phase45-build/shaders'))
    parser.add_argument('--requests',type=Path)
    parser.add_argument('--only',nargs='*')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    source=args.output/'original-glsl'
    for mod in ['mod','public']:
        original=Path('/build/0ad/binaries/data/mods')/mod/'shaders/glsl'
        if original.is_dir():shutil.copytree(original,source,dirs_exist_ok=True)
    adapted=args.output/'adapted-glsl';prepare_source(source,adapted)
    identity=hashlib.sha256(Path(__file__).read_bytes())
    for path in sorted(adapted.rglob('*')):
        if path.is_file():identity.update(path.relative_to(adapted).as_posix().encode());identity.update(path.read_bytes())
    BUILD_FINGERPRINT=identity.hexdigest()
    catalog_path=args.output/'webgpu-shaders.json'
    catalog=json.loads(catalog_path.read_text()) if catalog_path.exists() else dict(programs={})
    catalog['provenance']=dict(gamePin='40b8794eecb9618da69e10bacffa8814c561aa51',
        adaptationSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        buildFingerprint=BUILD_FINGERPRINT,
        originalSources={path.relative_to(source).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source.rglob('*')) if path.is_file()},
        tools=Path('/phase45-tools/binaries.sha256').read_text())
    report=dict(passed=[],failed=[],phase45Accepted=False)
    requests=json.loads(args.requests.read_text()) if args.requests else []
    if not requests:
        requests=[dict(name='glsl/'+path.stem,defines={}) for path in sorted(source.glob('*.xml')) if path.stem not in ['compute_skinning','minimap','dof']]
        requests += [dict(name='glsl/compute_skinning',defines={'MAX_BONES':str(count)}) for count in [64,192]]
        requests += [dict(name='glsl/minimap',defines={flag:'1'}) for flag in ['MINIMAP_BASE','MINIMAP_LOS','MINIMAP_POINT']]
        requests += [dict(name='glsl/minimap',defines={'MINIMAP_POINT':'1','USE_GPU_INSTANCING':'1'}),dict(name='glsl/dof',defines={'BLUR_FOV':'3'})]
        requests += [dict(name='glsl/bloom',defines={flag:'1'}) for flag in ['BLOOM_NOP','BLOOM_PASS_H','BLOOM_PASS_V']]
        for mod in ['mod','public']:
            effects=Path('/build/0ad/binaries/data/mods')/mod/'shaders/effects'
            for path in sorted(effects.rglob('*.xml')):
                tree=ET.parse(path).getroot()
                for technique in tree.findall('technique'):
                    for shader_pass in technique.findall('pass'):
                        shader=shader_pass.get('shader')
                        if not shader or not (source/(shader+'.xml')).exists():continue
                        flags={d.attrib['name']:d.attrib['value'] for node in [tree,technique,shader_pass] for d in node.findall('define')}
                        if shader=='minimap' and not any(k.startswith('MINIMAP_') for k in flags):continue
                        requests.append(dict(name='glsl/'+shader,defines=flags))
        requests=list({json.dumps(r,sort_keys=True):r for r in requests}.values())
        for name,program in catalog['programs'].items():
            for key in program['variants']:
                requests.append(dict(name=name,defines=json.loads(key)))
        requests=list({json.dumps(r,sort_keys=True):r for r in requests}.values())
    jobs={}
    for request in requests:
        name=request['name'];short=name.split('/')[-1]
        if args.only and short not in args.only:continue
        xml_path=source/(short+'.xml')
        if not xml_path.is_file():report['failed'].append(dict(name=name,error='Original program XML missing'));continue
        xml=ET.parse(xml_path).getroot()
        # Relevant define names are found recursively through includes; only
        # Include numeric substitutions (MAX_BONES, etc.) as well as conditionals.
        visited=set();conditions=set()
        def visit(path):
            if path in visited:return
            visited.add(path);text=path.read_text()
            conditions.update(re.findall(r'\b[A-Z][A-Z0-9_]+\b',text))
            for expression in re.findall(r'^\s*#\s*(?:if|elif|ifdef|ifndef)\s+([^\n]+)',text,re.M):
                conditions.update(re.findall(r'\b[A-Z][A-Z0-9_]+\b',expression))
            for included in re.findall(r'#include\s+"([^"]+)"',text):visit(source/included)
        for stage in ['vertex','fragment','compute']:
            if xml.find(stage) is not None:visit(source/xml.find(stage).attrib['file'].removeprefix('glsl/'))
        fixed={d.attrib['name'] for d in xml.findall('./define')}
        relevant=sorted(conditions-{'USE_SPIRV','USE_DESCRIPTOR_INDEXING','STAGE_VERTEX','STAGE_FRAGMENT','STAGE_COMPUTE','GL_ES'}-fixed)
        defines={k:str(v) for k,v in request['defines'].items() if k in relevant}
        jobs[(name,json.dumps(defines,sort_keys=True))]=(name,xml,defines,relevant)
    print(len(jobs),'unique shader variants; two compiler jobs',flush=True)
    def compile_job(job):
        name,xml,defines,relevant=job
        try:return job,compile_variant(name,xml,defines,adapted,args.output/'variants'),None
        except Exception as error:return job,None,str(error)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
      for index,(job,result,error) in enumerate(pool.map(compile_job,jobs.values()),1):
        name,xml,defines,relevant=job
        if error is None:
            key,variant=result
            program=catalog['programs'].setdefault(name,dict(defines=relevant,variants={}))
            program['defines']=relevant;program['variants'][key]=variant
            report['passed'].append(dict(name=name,key=key))
        else:report['failed'].append(dict(name=name,defines=defines,error=error))
        if error or index%10==0:
            print(index,'/',len(jobs),name,'FAILED' if error else 'OK',flush=True)
            (args.output/'translation-progress.json').write_text(json.dumps(dict(completed=index,total=len(jobs),passed=len(report['passed']),failed=report['failed']),indent=2))
            catalog_path.write_text(json.dumps(catalog,separators=(',',':')))
    catalog_path.write_text(json.dumps(catalog,separators=(',',':')))
    (args.output/'translation-report.json').write_text(json.dumps(report,indent=2))
    shutil.copytree('/phase45-tools',args.output/'tools',dirs_exist_ok=True)
    print(len(report['passed']),'passed;',len(report['failed']),'failed',flush=True)
    return bool(report['failed'])


if __name__=='__main__':raise SystemExit(main())
