"""Compare matched original captures against the predeclared pixel contract.

Image decoding uses the existing browser; no image packages, generated art,
desktop capture or performance measurements are involved.
"""
import argparse
import base64
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import CDP_URL

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--webgpu',type=Path,required=True)
parser.add_argument('--webgl','--reference',dest='webgl',type=Path,required=True)
parser.add_argument('--reference-backend',choices=['webgl','native'],default='webgl')
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--contract',type=Path,default=Path(__file__).resolve().parents[1]/'scenario/phase4-5-visual-contract.json')
args=parser.parse_args();args.evidence.parent.mkdir(parents=True,exist_ok=True)
contract=json.loads(args.contract.read_text())
report=dict(passed=False,visualParityAccepted=False,phase45Accepted=False,referenceBackend=args.reference_backend,contract=contract,captures=[])
try:
    gpu=json.loads((args.webgpu/'report.json').read_text())
    gl=json.loads((args.webgl/'report.json').read_text())
    assert gpu['passed'] and gl['passed'],'Both capture runs must pass'
    assert gpu['renderer']['backend']=='webgpu' and gl['renderer']['backend']==args.reference_backend
    keys=['attributes','simulationSHA256','graphicsSettings','camera','visualContract']
    if args.reference_backend=='webgl':keys.append('browserVersion')
    for key in keys:
        assert gpu[key]==gl[key],('Mismatched comparison prerequisite',key)
    with BenchmarkLock(),sync_playwright() as p:
        browser=p.chromium.connect_over_cdp(CDP_URL);page=browser.contexts[0].new_page()
        try:
            for name in contract['captures']:
                images=[base64.b64encode((directory/name).read_bytes()).decode('ascii') for directory in (args.webgpu,args.webgl)]
                measured=page.evaluate('''async({images,threshold})=>{
                  const bitmaps=[];
                  try {
                    for(const encoded of images){
                      const bytes=Uint8Array.from(atob(encoded),value=>value.charCodeAt(0));
                      bitmaps.push(await createImageBitmap(new Blob([bytes],{type:'image/png'})));
                    }
                    const [a,b]=bitmaps;
                    if(a.width!==b.width || a.height!==b.height)throw Error('Image dimensions differ');
                    const pixels=bitmaps.map(bitmap=>{
                      const canvas=new OffscreenCanvas(bitmap.width,bitmap.height),ctx=canvas.getContext('2d');
                      ctx.drawImage(bitmap,0,0);return ctx.getImageData(0,0,bitmap.width,bitmap.height).data;
                    });
                    let sum=0,outliers=0,maximum=0;
                    for(let index=0;index<pixels[0].length;index+=4){
                      let local=0;for(let channel=0;channel<3;channel++){
                        const difference=Math.abs(pixels[0][index+channel]-pixels[1][index+channel]);
                        sum+=difference;local=Math.max(local,difference);
                      }
                      maximum=Math.max(maximum,local);if(local>threshold)outliers++;
                    }
                    const count=a.width*a.height;
                    return {width:a.width,height:a.height,pixels:count,meanAbsoluteRGBDifference:sum/(3*count),
                      outlierPixelFraction:outliers/count,maximumChannelDifference:maximum};
                  } finally {for(const bitmap of bitmaps)bitmap.close();}
                }''',dict(images=images,threshold=contract['perPixelMaximumChannelDifference']))
                measured.update(file=name,passed=measured['meanAbsoluteRGBDifference']<=contract['maximumMeanAbsoluteRGBDifference'] and
                    measured['outlierPixelFraction']<=contract['maximumOutlierPixelFraction'])
                report['captures'].append(measured)
                print(json.dumps(measured),flush=True)
        finally:page.close()
    report['passed']=all(capture['passed'] for capture in report['captures'])
    report['scope']='Numerical pixel gate only. Inspect original shadows, materials, fog, text and sampler edges before accepting visual parity.'
except Exception as error:report['failure']=str(error)
finally:args.evidence.write_text(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
