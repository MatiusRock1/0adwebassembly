// Differential against the original, unchanged simulation module.
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const source=readFileSync('binaries/data/mods/public/simulation/ai/common-api/map-module.js','utf8');
const {InfoMap}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const rows=JSON.parse(readFileSync(process.argv[2],'utf8'));
if(process.argv[3]==='obstruction'){
  for(const [width,x,y,radius,seed,result] of rows){
    const map=new InfoMap({passabilityMap:{width,height:width,cellSize:4}},'passability');
    for(let i=0;i<map.length;++i)map.map[i]=(i*37+seed)%17;
    const actual=map.isObstructedTile(x,y,radius);
    assert.deepEqual(actual,result<0?null:{x:result%width,y:Math.floor(result/width)});
  }
  console.log(JSON.stringify({passed:true,obstructionCases:rows.length,performanceAcceptance:false}));
  process.exit(0);
}
let bytes=0;
for(const [width,height,cx,cy,distance,strength,maximum,type,seed,result] of rows){
  const map=new InfoMap({passabilityMap:{width,height,cellSize:4}},'passability');
  for(let i=0;i<map.length;++i)map.map[i]=(i*37+seed)%256;
  map.maxVal=maximum;
  map.addInfluence(cx,cy,distance,strength,['linear','quadratic','constant'][type]);
  assert.deepEqual(result,Array.from(map.map));bytes+=result.length;
}
console.log(JSON.stringify({passed:true,cases:rows.length,bytesCompared:bytes,performanceAcceptance:false}));
