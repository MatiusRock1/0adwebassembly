"""Record upstream resources and named Git contributors; create no artwork."""
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
root = Path('/build/0ad')
evidence = Path('/evidence')
manifest = json.loads((evidence/'assets/input-manifest.json').read_text())
paths = {'binaries/data/mods/public/' + f['path'] for f in manifest['files']}
paths.update(str(p.relative_to(root)) for p in (root/'binaries/data/mods/mod/art').rglob('*') if p.is_file())
paths.update(['binaries/data/mods/public/maps/scenarios/pathfinding_terrain_demo.xml','binaries/data/mods/public/maps/scenarios/pathfinding_terrain_demo.pmp'])

def record(relative):
    p = root/relative
    result = subprocess.run(['git','log','-3','--format=%H|%an|%ad|%s','--date=short','--',relative],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
    history = []
    for line in result.stdout.splitlines():
        commit,author,date,subject = line.split('|',3)
        history.append(dict(commit=commit,author=author,date=date,subject=subject))
    embedded_authors = []
    if p.suffix == '.dae':
        try:
            xml = ET.parse(p)
            embedded_authors = [(n.text or '').strip() for n in xml.findall('.//{*}asset/{*}contributor/{*}author') if n.text]
        except ET.ParseError:
            pass
    is_art = '/art/' in relative
    return dict(path=relative,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        sourceCommit='40b8794eecb9618da69e10bacffa8814c561aa51',
        licence='CC-BY-SA-3.0' if is_art else 'MAP_SPECIFIC_FILE_ABSENT',
        copyright='Wildfire Games' if is_art else None,
        embeddedAuthors=embedded_authors,recordedGitContributors=history,
        transformation='Original native archive builder for meshes, animations and textures; engine-base resources copied unchanged')

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    records = list(pool.map(record, sorted(paths)))
report = dict(sourceURL='https://gitea.wildfiregames.com/0ad/0ad.git',
    sourceCommit='40b8794eecb9618da69e10bacffa8814c561aa51',files=records,
    attributionURL='https://www.wildfiregames.com/',licenceURL='https://creativecommons.org/licenses/by-sa/3.0/',
    authorshipMethod='Embedded Collada author metadata and the last three recorded Git contributors. Git history is provenance and does not establish that the latest contributor created the artwork.',
    mapLicenceStatus='The pinned LICENSE.md refers to a maps/LICENSE.txt that is absent, including in reachable history. This uncertainty is recorded; no map-specific licence is invented. Local evaluation only; review before redistribution.',
    filesWithoutRecordedContributor=[r['path'] for r in records if not r['recordedGitContributors']])
(evidence/'asset-provenance.json').write_text(json.dumps(report,indent=2))
licences = evidence/'licences'
licences.mkdir(exist_ok=True)
for source,name in [(root/'LICENSE.md','upstream-LICENSE.md'),(root/'license_gpl-2.0.txt','license_gpl-2.0.txt'),(root/'binaries/data/mods/public/art/LICENSE.txt','public-art-LICENSE.txt')]:
    if source.is_file(): shutil.copy2(source,licences/name)
print('UPSTREAM_RESOURCE_PROVENANCE_RECORDED',len(records),flush=True)
