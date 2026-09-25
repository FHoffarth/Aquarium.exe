"""Natural Environment Stage 2 (offline plant material study): acquire the
approved ambientCG CC0 sources and record their provenance.

Raw downloads land in art/source/ambientcg/ (gitignored, never shipped).
Provenance (download URL, sizes, SHA-256 of the archive and of every
extracted file, license) is committed under art/provenance/stage2/.

  python art/tools/fetch_stage2_sources.py

These are SOURCE material for camera-specific clusters, not runtime assets.
"""

import datetime
import hashlib
import io
import json
import pathlib
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'art' / 'source' / 'ambientcg'
PROVENANCE = ROOT / 'art' / 'provenance' / 'stage2'
USER_AGENT = 'Mozilla/5.0 (Aquarium.exe asset acquisition, dev tooling)'
ATTRIBUTE = '2K-JPG'

# Approved in chat for the Stage 2 study (family in comment).
ASSETS = [
    'LeafSet022', 'LeafSet003', 'LeafSet001',      # broad / medium leaf mass
    'Foliage001', 'Foliage008', 'LeafSet002',      # tall / background mass
    'Moss004', 'Moss002',                          # moss / low transition
]


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request) as response:
        return response.read()


def main():
    PROVENANCE.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    info = json.loads(fetch('https://ambientcg.com/api/v2/full_json?id=' + ','.join(ASSETS)
                            + '&include=downloadData,tagData'))
    (PROVENANCE / 'ambientcg.full_json.json').write_text(json.dumps(info, indent=2) + '\n')
    acquisitions = {}
    for asset in info['foundAssets']:
        asset_id = asset['assetId']
        downloads = [d for folder in asset['downloadFolders'].values()
                     for category in folder['downloadFiletypeCategories'].values()
                     for d in category['downloads']]
        chosen = next(d for d in downloads if d['attribute'] == ATTRIBUTE)
        data = fetch(chosen['downloadLink'])
        target = SOURCE / asset_id
        target.mkdir(parents=True, exist_ok=True)
        archive = target / chosen['fileName']
        archive.write_bytes(data)
        files = []
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            for name in bundle.namelist():
                content = bundle.read(name)
                (target / name).parent.mkdir(parents=True, exist_ok=True)
                (target / name).write_bytes(content)
                files.append({'file': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
        acquisitions[asset_id] = {
            'source': 'ambientCG',
            'sourcePage': f'https://ambientcg.com/view?id={asset_id}',
            'name': asset.get('displayName'),
            'creator': 'ambientCG (Lennart Demes)',
            'license': 'CC0-1.0',
            'licenseUrl': 'https://docs.ambientcg.com/license/',
            'attributionRequired': False,
            'dateAcquired': today,
            'variant': ATTRIBUTE,
            'downloadUrl': chosen['downloadLink'],
            'archive': {'file': archive.relative_to(ROOT).as_posix(), 'bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest()},
            'files': files,
        }
        print(f'{asset_id}: {len(data) / 1e6:.1f} MB, {len(files)} files')
    (PROVENANCE / 'acquisitions.json').write_text(json.dumps(acquisitions, indent=2) + '\n')


if __name__ == '__main__':
    main()
