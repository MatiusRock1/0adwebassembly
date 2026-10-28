"""Resolve real CDP samples against their archived Emscripten symbol map."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory',type=Path)
args=parser.parse_args()
symbols_path=args.directory/'engine-symbols.txt'
symbols={}
for line in symbols_path.read_text().splitlines():
    index,_,name=line.partition(':')
    symbols[int(index)]=re.sub(r'\\([0-9a-fA-F]{2})',lambda m:chr(int(m[1],16)),name)
report=dict(diagnosticOnly=True,symbolsSHA256=hashlib.sha256(symbols_path.read_bytes()).hexdigest(),profiles=[])
for path in sorted(args.directory.glob('*.cpuprofile')):
    profile=json.loads(path.read_text());nodes={node['id']:node for node in profile['nodes']}
    parents={child:node['id'] for node in profile['nodes'] for child in node.get('children',[])}
    def name(index):
        frame=nodes[index]['callFrame'];match=re.fullmatch(r'wasm-function\[(\d+)\]',frame['functionName'])
        return symbols.get(int(match[1]),frame['functionName']) if match else frame['functionName']
    own=Counter();inclusive=Counter();waits=Counter()
    update_own=Counter();update_inclusive=Counter();update_groups=Counter()
    for index,delta in zip(profile['samples'],profile['timeDeltas']):
        sampled=name(index);own[sampled]+=delta;stack=set()
        is_wait=sampled=='emscripten_futex_wait';wait_site=None;fallback=None
        while True:
            function=name(index);stack.add(function)
            if is_wait:
                if wait_site is None and 'WebGPU::' in function and any(part in function for part in ['::SwapChain::','::Context::','::Shader::','CDevice::']):wait_site=function
                if wait_site is None and any(part in function for part in ['CSoundBase::','CSoundManager::','CSoundManagerWorker::','CReplayLogger::']):wait_site=function
                if fallback is None and any(part in function for part in ['CGame::Update(','CRenderer::RenderFrame(','main(']):fallback=function
            if index not in parents:break
            index=parents[index]
        if is_wait:waits[wait_site or fallback or '(other futex wait)']+=delta
        for function in stack:inclusive[function]+=delta
        if any('CGame::Update(' in function for function in stack):
            update_own[sampled]+=delta
            for function in stack:update_inclusive[function]+=delta
            update_groups['AI' if any('CAIWorker::' in function for function in stack) else 'other-update']+=delta
    def top(counter):return [dict(function=key,seconds=value/1e6) for key,value in counter.most_common(45)]
    report['profiles'].append(dict(file=path.name,seconds=sum(profile['timeDeltas'])/1e6,self=top(own),inclusive=top(inclusive),futexWaitSites=top(waits),
        gameUpdate=dict(groupsSeconds={key:value/1e6 for key,value in update_groups.items()},self=top(update_own),inclusive=top(update_inclusive),
            scope='Sampled wall stack residence under CGame::Update, not exclusive CPU time or physical-frame attribution. AI group requires CAIWorker on that same stack.')))
(args.directory/'analysis.json').write_text(json.dumps(report,indent=2))
for item in report['profiles']:
    if any('WebGPU' in row['function'] for row in item['self'][:15]):
        print(item['file'],json.dumps(item['inclusive'][:22],indent=2))
