// Renderer adaptation of legacy sampler border addressing. Shader overrides
// specialize the portable filter only for textures that actually request it;
// ordinary textures retain the hardware sampling operation.
function helper(name) {
  const p=`webgpuBorder_${name}`;
  return `
override ${p}_u: u32 = 2u;
override ${p}_v: u32 = 2u;
override ${p}_mag: u32 = 1u;
override ${p}_min: u32 = 1u;
override ${p}_mip: u32 = 1u;
override ${p}_aniso: f32 = 1.0;
override ${p}_color: u32 = 0u;
override ${p}_bias: f32 = 0.0;
fn ${p}_address(value: i32, size: i32, mode: u32) -> i32 {
  if (mode == 0u) { return ((value % size) + size) % size; }
  if (mode == 1u) {
    let period = 2 * size;
    let index = ((value % period) + period) % period;
    return min(index, period - 1 - index);
  }
  return clamp(value, 0, size - 1);
}
fn ${p}_texel(position: vec2i, level: i32) -> vec4f {
  let size = vec2i(textureDimensions(${name}, level));
  if ((${p}_u == 3u && (position.x < 0 || position.x >= size.x)) ||
      (${p}_v == 3u && (position.y < 0 || position.y >= size.y))) {
    return vec4f(vec3f(select(0.0, 1.0, ${p}_color == 2u)), select(0.0, 1.0, ${p}_color != 0u));
  }
  return textureLoad(${name}, vec2i(${p}_address(position.x, size.x, ${p}_u), ${p}_address(position.y, size.y, ${p}_v)), level);
}
fn ${p}_level(uv: vec2f, level: i32, linear: bool) -> vec4f {
  let position = uv * vec2f(textureDimensions(${name}, level));
  if (!linear) { return ${p}_texel(vec2i(floor(position)), level); }
  let base = vec2i(floor(position - 0.5));
  let weight = fract(position - 0.5);
  return mix(mix(${p}_texel(base, level), ${p}_texel(base + vec2i(1, 0), level), weight.x),
             mix(${p}_texel(base + vec2i(0, 1), level), ${p}_texel(base + vec2i(1, 1), level), weight.x), weight.y);
}
fn ${p}_lod(uv: vec2f, lod: f32, linear: bool) -> vec4f {
  let maximum = i32(textureNumLevels(${name})) - 1;
  let bounded = clamp(lod, 0.0, f32(maximum));
  if (${p}_mip == 0u) { return ${p}_level(uv, i32(floor(bounded + 0.5)), linear); }
  let level = i32(floor(bounded));
  return mix(${p}_level(uv, level, linear), ${p}_level(uv, min(level + 1, maximum), linear), fract(bounded));
}
fn ${p}_gradient(uv: vec2f, dx: vec2f, dy: vec2f, bias: f32) -> vec4f {
  let size = vec2f(textureDimensions(${name}, 0));
  let x = dx * size;
  let y = dy * size;
  // Singular values of the footprint, including skewed texture gradients.
  let a = dot(x, x);
  let b = dot(x, y);
  let c = dot(y, y);
  let discriminant = sqrt(max(0.0, (a-c)*(a-c) + 4.0*b*b));
  let major = sqrt(max(0.0, 0.5*(a+c+discriminant)));
  let minor = sqrt(max(0.0, 0.5*(a+c-discriminant)));
  let magnifying = major <= 1.0;
  let linear = select(${p}_min != 0u, ${p}_mag != 0u, magnifying);
  let footprint = max(max(minor, major / ${p}_aniso), 0.000001);
  let lod = log2(footprint) + ${p}_bias + bias;
  let taps = i32(clamp(ceil(major / max(footprint, 1.0)), 1.0, ${p}_aniso));
  var direction = vec2f(1.0, 0.0);
  if (abs(b) > 0.000001) { direction = normalize(vec2f(b, 0.5*(c-a+discriminant))); }
  else if (c > a) { direction = vec2f(0.0, 1.0); }
  let axis = dx * direction.x + dy * direction.y;
  var result = vec4f(0.0);
  for (var index = 0; index < taps; index++) {
    let offset = (f32(index) + 0.5) / f32(taps) - 0.5;
    result += ${p}_lod(uv + axis * offset, lod, linear);
  }
  return result / f32(taps);
}
fn ${p}_sample(uv: vec2f) -> vec4f {
  if (${p}_u != 3u && ${p}_v != 3u) { return textureSample(${name}, ${name}_sampler, uv); }
  return ${p}_gradient(uv, dpdx(uv), dpdy(uv), 0.0);
}
fn ${p}_grad(uv: vec2f, dx: vec2f, dy: vec2f) -> vec4f {
  if (${p}_u != 3u && ${p}_v != 3u) { return textureSampleGrad(${name}, ${name}_sampler, uv, dx, dy); }
  return ${p}_gradient(uv, dx, dy, 0.0);
}
fn ${p}_biasSample(uv: vec2f, bias: f32) -> vec4f {
  if (${p}_u != 3u && ${p}_v != 3u) { return textureSampleBias(${name}, ${name}_sampler, uv, bias); }
  return ${p}_gradient(uv, dpdx(uv), dpdy(uv), bias);
}
fn ${p}_explicit(uv: vec2f, lod: f32) -> vec4f {
  if (${p}_u != 3u && ${p}_v != 3u) { return textureSampleLevel(${name}, ${name}_sampler, uv, lod); }
  return ${p}_lod(uv, lod + ${p}_bias, select(${p}_min != 0u, ${p}_mag != 0u, lod <= 0.0));
}
`;
}

export function adaptBorderSampling(code,textures,stage) {
  if(stage==='vertex' || stage==='compute')return {code,textures:[]};
  const used=[];
  for(const texture of textures){
    if(texture.depth || texture.cube)continue;
    const name=texture.name;
    // Naga preserves reflected texture/sampler names. Match only calls that
    // reference that pair; expressions following the pair remain unchanged.
    const expression=new RegExp(`\\b(textureSample(?:Grad|Bias|Level)?)\\(\\s*${name}\\s*,\\s*${name}_sampler\\s*,`,'g');
    let matched=false;
    code=code.replace(expression,(_,operation)=>{
      matched=true;
      const suffix={textureSample:'sample',textureSampleGrad:'grad',textureSampleBias:'biasSample',textureSampleLevel:'explicit'}[operation];
      return `webgpuBorder_${name}_${suffix}(`;
    });
    if(matched){used.push(name);code+='\n'+helper(name);}
  }
  return {code,textures:used};
}

export function borderConstants(names,findTexture) {
  const constants={};
  for(const name of names){
    const s=findTexture(name)?.samplerState;
    if(!s || (s[3]!==3 && s[4]!==3))continue;
    const values={u:s[3],v:s[4],mag:s[0],min:s[1],mip:s[2],aniso:s[6],color:s[9]??0,bias:s[10]??0};
    for(const [key,value] of Object.entries(values))constants[`webgpuBorder_${name}_${key}`]=value;
  }
  return constants;
}
