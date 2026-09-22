"""Acquire the approved Slice A source assets and record their provenance.

Raw downloads land in art/source/ (gitignored, never shipped). Everything
needed to re-acquire and verify them is committed under art/provenance/:
the Poly Haven asset info at acquisition time, every file URL, the
publisher's MD5, our SHA-256, and the acquisition date.

Usage: python art/tools/fetch_sources.py
"""

import datetime
import hashlib
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / 'art' / 'source' / 'polyhaven'
PROVENANCE_DIR = ROOT / 'art' / 'provenance' / 'polyhaven'
USER_AGENT = 'Aquarium.exe asset acquisition (dev tooling)'
RESOLUTION = '2k'

# Approved GREEN set (Slice A). rock_moss_set_01 and ambientCG Gravel043
# are approved only as fallbacks and are intentionally not fetched.
MODELS = {
    'dry_branches_medium_01': [],
    'rock_moss_set_02': [],
    'anthurium_botany_01': ['Alpha'],
    'fern_02': ['Alpha'],
    'shrub_sorrel_01': ['Alpha'],
    'nettle_plant': ['Alpha'],
    'moss_01': ['Alpha'],
}
TEXTURES = {
    'gravelly_sand': ['Diffuse', 'nor_gl', 'arm', 'Displacement'],
    'coast_sand_03': ['Diffuse', 'nor_gl', 'arm', 'Displacement'],
}
MAP_FORMAT = {'Alpha': 'png', 'Displacement': 'png'}


def fetch_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def download(url, destination, expected_md5):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request) as response:
            destination.write_bytes(response.read())
    data = destination.read_bytes()
    md5 = hashlib.md5(data).hexdigest()
    if expected_md5 and md5 != expected_md5:
        raise RuntimeError(f'MD5 mismatch for {url}: {md5} != {expected_md5}')
    return {
        'url': url,
        'originalFilename': url.rsplit('/', 1)[1],
        'localPath': destination.relative_to(ROOT).as_posix(),
        'bytes': len(data),
        'md5': md5,
        'sha256': hashlib.sha256(data).hexdigest(),
    }


def map_entry(files, map_name):
    fmt = MAP_FORMAT.get(map_name, 'jpg')
    return files[map_name][RESOLUTION][fmt]


def acquire(asset_id, files, gltf, extra_maps):
    target = SOURCE_DIR / asset_id
    records = []
    if gltf:
        bundle = files['gltf'][RESOLUTION]['gltf']
        records.append(download(bundle['url'], target / bundle['url'].rsplit('/', 1)[1], bundle['md5']))
        for relative, entry in bundle['include'].items():
            records.append(download(entry['url'], target / relative, entry['md5']))
    for map_name in extra_maps:
        entry = map_entry(files, map_name)
        records.append(download(entry['url'], target / 'textures' / entry['url'].rsplit('/', 1)[1], entry['md5']))
    return records


def main():
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    acquisitions = {}
    for asset_id, extra in [*((a, (m, True)) for a, m in MODELS.items()),
                            *((a, (m, False)) for a, m in TEXTURES.items())]:
        maps, is_model = extra
        info = fetch_json(f'https://api.polyhaven.com/info/{asset_id}')
        files = fetch_json(f'https://api.polyhaven.com/files/{asset_id}')
        (PROVENANCE_DIR / f'{asset_id}.info.json').write_text(json.dumps(info, indent=2) + '\n')
        records = acquire(asset_id, files, is_model, maps)
        acquisitions[asset_id] = {
            'source': 'Poly Haven',
            'sourcePage': f'https://polyhaven.com/a/{asset_id}',
            'name': info.get('name'),
            'creator': info.get('authors'),
            'license': 'CC0-1.0',
            'licenseUrl': 'https://polyhaven.com/license',
            'dateAcquired': today,
            'resolution': RESOLUTION,
            'files': records,
        }
        total = sum(record['bytes'] for record in records)
        print(f'{asset_id}: {len(records)} files, {total / 1e6:.1f} MB')
    (PROVENANCE_DIR / 'acquisitions.json').write_text(json.dumps(acquisitions, indent=2) + '\n')


if __name__ == '__main__':
    main()
