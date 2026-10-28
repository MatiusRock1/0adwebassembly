// Preserve the original skinning shader's arithmetic and output bytes while
// binding the original shared allocation once. Two writable storage bindings
// to the same buffer require scratch copies in the generic WebGPU path.
export function sharedSkinningCode(code) {
  const position=/@group\(1\)\s*@binding\(2\)\s*var<storage,\s*read_write>\s+(\w+):\s*OutputPositions;/;
  const normal=/@group\(1\)\s*@binding\(3\)\s*var<storage,\s*read_write>\s+(\w+):\s*OutputNormalsTangents;/;
  const p=code.match(position),n=code.match(normal);
  const layout='outputPositions: array<vec4<f32>>';
  if(!p || !n || !code.includes(layout))throw new Error('Unsupported original skinning storage layout');
  let result=code.replace(normal,'').replace(layout,'outputPositions: array<vec4<u32>>');
  const assignment=new RegExp(`(${p[1]}\\.outputPositions\\[[^\\n]+?\\]\\s*=\\s*)([^\\n]+);`,'g');
  let writes=0;
  result=result.replace(assignment,(_all,target,value)=>{writes++;return `${target}bitcast<vec4<u32>>(${value});`;});
  if(writes!==1)throw new Error('Unsupported original skinning position assignment');
  result=result.replaceAll(`${n[1]}.outputPackedNT`,`${p[1]}.outputPositions`);
  if(new RegExp(`\\b${n[1]}\\b`).test(result))throw new Error('Unmerged original skinning normal storage');
  return result;
}
