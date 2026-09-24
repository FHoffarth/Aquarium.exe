"""Natural Environment Stage 1: acquire the approved look-dev sources and
record their provenance (offline hardscape material-presence test only).

Raw files land in art/source/ (gitignored, never shipped). Everything needed
to re-acquire and verify them is committed under art/provenance/stage1/.

  python art/tools/fetch_stage1_sources.py

Poly Haven (CC0) sources are downloaded here. Sketchfab downloads require a
logged-in account, so the two CC BY 4.0 roots are downloaded manually by the
project owner into art/source/sketchfab/<uid>/ (the original archive, or its
extracted files); this script then verifies they are present, hashes every
file and records author, source URL, license and license URL from Sketchfab's
public model API. Each CC BY 4.0 asset used in production later must appear
in THIRD_PARTY_NOTICES with the same fields.
"""

import datetime
import hashlib
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
PH_DIR = ROOT / 'art' / 'source' / 'polyhaven'
SF_DIR = ROOT / 'art' / 'source' / 'sketchfab'
PROVENANCE = ROOT / 'art' / 'provenance' / 'stage1'
USER_AGENT = 'Aquarium.exe asset acquisition (dev tooling)'
RESOLUTION = '4k'     # look-dev; runtime textures will be baked down later

POLYHAVEN_MODELS = ['rock_09', 'rock_07', 'boulder_01']
SKETCHFAB_MODELS = {
    # uid: short label (manual download by the project owner)
    '5fe23ea13be54e56b99325e2fb0bf681': 'decorative_driftwood_yelizegi',
    '31ac4c155b074b5ab9b73396aa165eb5': 'rathtrevor_beached_tree_root_lesterm',
}


def fetch_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def file_record(path, url=None, expected_md5=None):
    data = path.read_bytes()
    md5 = hashlib.md5(data).hexdigest()
    if expected_md5 and md5 != expected_md5:
        raise RuntimeError(f'MD5 mismatch for {path}: {md5} != {expected_md5}')
    record = {
        'localPath': path.relative_to(ROOT).as_posix(),
        'bytes': len(data),
        'md5': md5,
        'sha256': hashlib.sha256(data).hexdigest(),
    }
    if url:
        record['url'] = url
        record['originalFilename'] = url.rsplit('/', 1)[1]
    return record


def download(url, destination, expected_md5):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request) as response:
            destination.write_bytes(response.read())
    return file_record(destination, url, expected_md5)


def acquire_polyhaven(asset_id, today):
    info = fetch_json(f'https://api.polyhaven.com/info/{asset_id}')
    files = fetch_json(f'https://api.polyhaven.com/files/{asset_id}')
    (PROVENANCE / f'{asset_id}.info.json').write_text(json.dumps(info, indent=2) + '\n')
    bundle = files['gltf'][RESOLUTION]['gltf']
    target = PH_DIR / asset_id
    records = [download(bundle['url'], target / bundle['url'].rsplit('/', 1)[1], bundle['md5'])]
    for relative, entry in bundle['include'].items():
        records.append(download(entry['url'], target / relative, entry['md5']))
    print(f'{asset_id}: {len(records)} files, {sum(r["bytes"] for r in records) / 1e6:.1f} MB')
    return {
        'source': 'Poly Haven',
        'sourcePage': f'https://polyhaven.com/a/{asset_id}',
        'name': info.get('name'),
        'creator': info.get('authors'),
        'license': 'CC0-1.0',
        'licenseUrl': 'https://polyhaven.com/license',
        'attributionRequired': False,
        'dateAcquired': today,
        'resolution': RESOLUTION,
        'sourcePolycount': info.get('polycount'),
        'files': records,
    }


def record_sketchfab(uid, label, today):
    model = fetch_json(f'https://api.sketchfab.com/v3/models/{uid}')
    (PROVENANCE / f'sketchfab_{label}.model.json').write_text(json.dumps(model, indent=2) + '\n')
    folder = SF_DIR / uid
    files = sorted(p for p in folder.rglob('*') if p.is_file()) if folder.exists() else []
    status = 'present' if files else 'awaiting manual download'
    print(f'{label}: {status} ({len(files)} files)')
    return {
        'source': 'Sketchfab',
        'sourcePage': model.get('viewerUrl'),
        'name': model.get('name'),
        'creator': {'displayName': model['user'].get('displayName'), 'username': model['user'].get('username'),
                    'profileUrl': model['user'].get('profileUrl')},
        'license': 'CC-BY-4.0',
        'licenseUrl': model['license'].get('url'),
        'attributionRequired': True,
        'attribution': f'"{model.get("name")}" by {model["user"].get("displayName")} '
                       f'({model.get("viewerUrl")}), licensed under CC BY 4.0 '
                       f'(https://creativecommons.org/licenses/by/4.0/). Modified.',
        'dateAcquired': today if files else None,
        'acquisition': 'manual download by the project owner (Sketchfab requires login)',
        'sourceFaceCount': model.get('faceCount'),
        'sourceVertexCount': model.get('vertexCount'),
        'status': status,
        'files': [file_record(p) for p in files],
    }


def main():
    PROVENANCE.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    acquisitions = {asset_id: acquire_polyhaven(asset_id, today) for asset_id in POLYHAVEN_MODELS}
    for uid, label in SKETCHFAB_MODELS.items():
        acquisitions[label] = record_sketchfab(uid, label, today)
    (PROVENANCE / 'acquisitions.json').write_text(json.dumps(acquisitions, indent=2) + '\n')


if __name__ == '__main__':
    main()
