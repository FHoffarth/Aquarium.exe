"""Write habitat/assets/manifest.json: every shipped asset with SHA-256 and provenance.

Run last:  python art/tools/build_manifest.py

Runtime verifies each file against this manifest before use, and
tests/habitat/asset-manifest.test.mjs verifies it against the repository.
Descriptive labels only: vegetation is visually transformed source material,
not a claim about any real species.
"""

import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'habitat' / 'assets'
ACQUISITIONS = ROOT / 'art' / 'provenance' / 'polyhaven' / 'acquisitions.json'
LICENSE_EVIDENCE = [
    'art/licenses/CC0-1.0-legalcode.txt',
    'art/licenses/polyhaven-license.txt',
    'art/licenses/polyhaven-license-page.html',
]

# Shipped file -> (role, label, derived-from source ids, modifications)
SHIPPED = {
    'slice-a/environment.glb': (
        'geometry', 'Slice A planted-corner environment geometry',
        ['rock_moss_set_02', 'dry_branches_medium_01', 'moss_01', 'anthurium_botany_01', 'fern_02',
         'shrub_sorrel_01', 'nettle_plant'],
        'Assembled by art/tools/build_slice_a.py: 6 rocks decimated to ~2.6k tris each plus 12 '
        'pebble copies; three branches re-posed, radially thickened and joined into one driftwood '
        'form, decimated to 7.5k tris; moss sprigs scattered onto up-facing hardscape; broad-leaf '
        'plants decimated to ~1.5k tris each and fern clumps re-placed; plant UVs remapped into a '
        '2x1 atlas; camera-facing vegetation cards; original substrate terrain mesh; per-vertex '
        'contact occlusion baked in Cycles; materials stripped (assigned at runtime).'),
    'slice-a/textures/cards_albedo.webp': (
        'texture', 'Carpet + stem vegetation card atlas (colour + alpha)', ['shrub_sorrel_01', 'nettle_plant'],
        'Tiles rendered in Blender (Cycles, uniform white light) from the habitat camera angle: '
        'carpet clumps of leafy sprigs with flower geometry removed, and two tall stems; packed '
        'into a 2048x1024 atlas, colour graded (one stem variant bronze-red), colour dilated '
        'under alpha, WebP.'),
    'slice-a/textures/rock_albedo.webp': ('texture', 'Rock colour', ['rock_moss_set_02'], 'Downscaled 2K -> 1K (Lanczos), saturation x0.85 and value x0.9, WebP.'),
    'slice-a/textures/rock_normal.webp': ('texture', 'Rock normal (OpenGL)', ['rock_moss_set_02'], 'OpenGL normal map downscaled 2K -> 1K (Lanczos), WebP.'),
    'slice-a/textures/rock_orm.webp': ('texture', 'Rock roughness in G', ['rock_moss_set_02'], '2K roughness -> 1K, packed into G of an ORM map, WebP.'),
    'slice-a/textures/wood_albedo.webp': ('texture', 'Driftwood colour', ['dry_branches_medium_01'], '2K -> 1K, re-graded from grey weathered wood to dark brown, WebP.'),
    'slice-a/textures/wood_normal.webp': ('texture', 'Driftwood normal (OpenGL)', ['dry_branches_medium_01'], 'OpenGL normal map downscaled 2K -> 1K (Lanczos), WebP.'),
    'slice-a/textures/wood_orm.webp': ('texture', 'Driftwood AO/roughness/metal', ['dry_branches_medium_01'], 'ARM map downscaled 2K -> 1K (Lanczos), WebP.'),
    'slice-a/textures/moss_albedo.webp': ('texture', 'Moss colour + alpha', ['moss_01'], '2K diffuse + alpha -> 512 RGBA, hue graded, colour dilated under alpha, WebP.'),
    'slice-a/textures/moss_normal.webp': ('texture', 'Moss normal (OpenGL)', ['moss_01'], 'OpenGL normal map downscaled 2K -> 512 (Lanczos), WebP.'),
    'slice-a/textures/plants_albedo.webp': ('texture', 'Broad-leaf + fern vegetation atlas (colour + alpha)', ['anthurium_botany_01', 'fern_02'], 'Two 2K diffuse+alpha maps -> 1K tiles in a 2048x1024 atlas, colour graded toward aquatic greens, colour dilated under alpha, WebP.'),
    'slice-a/textures/plants_normal.webp': ('texture', 'Vegetation atlas normal (OpenGL)', ['anthurium_botany_01', 'fern_02'], 'Two 2K normal maps -> 512 tiles in a 1024x512 atlas, WebP.'),
    'slice-a/textures/substrate_albedo.webp': ('texture', 'Substrate colour (unique, baked)', ['gravelly_sand', 'coast_sand_03'], 'Both 2K diffuse maps tiled at aquarium grain scale and blended by a hardscape-proximity mask into one unique 2048x1024 floor texture, with baked contact occlusion and tonal variation, WebP.'),
    'slice-a/textures/substrate_normal.webp': ('texture', 'Substrate normal (OpenGL, unique)', ['gravelly_sand', 'coast_sand_03'], 'Both 2K normal maps tiled and blended with the same mask, renormalised, WebP.'),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    acquisitions = json.loads(ACQUISITIONS.read_text())
    used = sorted({source for _, _, sources, _ in SHIPPED.values() for source in sources})
    sources = {}
    for asset_id in used:
        record = acquisitions[asset_id]
        sources[asset_id] = {
            'sourceAssetName': record['name'],
            'source': record['source'],
            'sourcePage': record['sourcePage'],
            'creator': record['creator'],
            'license': record['license'],
            'licenseUrl': record['licenseUrl'],
            'dateAcquired': record['dateAcquired'],
            'originalFiles': [
                {'filename': f['originalFilename'], 'url': f['url'], 'sha256': f['sha256']}
                for f in record['files']
            ],
            'status': 'GREEN',
        }
    files = []
    for relative, (role, label, derived, modifications) in SHIPPED.items():
        path = ASSETS / relative
        files.append({
            'file': relative,
            'role': role,
            'label': label,
            'bytes': path.stat().st_size,
            'sha256': sha256(path),
            'license': 'CC0-1.0',
            'status': 'GREEN',
            'derivedFrom': derived,
            'modifications': modifications,
        })
    shipped_on_disk = sorted(p.relative_to(ASSETS).as_posix() for p in ASSETS.rglob('*')
                             if p.is_file() and p.name != 'manifest.json')
    missing = sorted(set(shipped_on_disk) - set(SHIPPED))
    if missing:
        raise SystemExit(f'Unlisted shipped files: {missing}')
    manifest = {
        'schema': 1,
        'policy': 'Every shipped art file is GREEN (CC0 source + our modifications) and verified by SHA-256 at load time.',
        'licenseEvidence': LICENSE_EVIDENCE,
        'files': files,
        'sources': sources,
    }
    (ASSETS / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'manifest: {len(files)} files, {len(sources)} sources')


if __name__ == '__main__':
    main()
