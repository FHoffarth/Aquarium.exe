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
# Acquisition records: Poly Haven (Slices A/B), and the Natural Environment
# study's Poly Haven (stage1) and ambientCG (stage2) sources for Slice C.
ACQUISITIONS = [
    ROOT / 'art' / 'provenance' / 'polyhaven' / 'acquisitions.json',
    ROOT / 'art' / 'provenance' / 'stage1' / 'acquisitions.json',
    ROOT / 'art' / 'provenance' / 'stage2' / 'acquisitions.json',
]
LICENSE_EVIDENCE = [
    'art/licenses/CC0-1.0-legalcode.txt',
    'art/licenses/polyhaven-license.txt',
    'art/licenses/polyhaven-license-page.html',
    'art/licenses/ambientcg-license-page.html',
]

# Shipped file -> (role, label, derived-from source ids, modifications)
SHIPPED = {
    'lush/environment_albedo.webp': (
        'texture', 'Approved 6dfd62d planted freshwater environment without posed review fish',
        ['rock_07', 'boulder_01', 'rock_09', 'LeafSet022', 'bark_willow_02'],
        'Lossless WebP of the approved 1920x1080 Blender scene at frame 1 with only posed fish '
        'and still-frame suspended particles hidden. Same vegetation, substrate, wood, camera, '
        'lighting and water materials as 6dfd62d. Rendered by art/tools/export_lush_runtime_plate.py '
        'from the saved approved Blender scene; no external assets added.'),
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
    'slice-b/environment.glb': (
        'geometry', 'Slice B aquascape environment geometry (Hero Frame Pass 2 translation)',
        ['rock_moss_set_02', 'moss_01'],
        'Assembled by art/tools/build_slice_b.py: 13 rocks (two primaries, two front secondaries, '
        'transition and secondary stones) decimated to 450-2400 tris each plus 12 pebble copies, '
        'partly buried; moss sprigs scattered onto hardscape near branch joints and low surfaces; '
        'original procedural driftwood root (three gestures, surface roots, stubs; own geometry, '
        'no source mesh), original procedural leaf geometry (broad-leaf rosettes, epiphytes, small '
        'rosettes, hairgrass, ribbon plants) with vertex colour and sway weights; camera-facing '
        'cards; original substrate terrain; per-vertex contact shading; materials stripped.'),
    'slice-b/textures/cards_albedo.webp': (
        'texture', 'Background stem-clump and carpet-relief card atlas (colour + alpha)', [],
        'Original: procedural stem plants and carpet leaves generated and rendered in Blender '
        '(EEVEE, uniform light) from the habitat camera angle by art/tools/build_slice_b.py; packed '
        'into a 2048x768 atlas, graded, colour dilated under alpha, WebP.', 'art/tools/build_slice_b.py'),
    'slice-b/textures/rock_albedo.webp': ('texture', 'Rock colour', ['rock_moss_set_02'], 'Downscaled 2K -> 1K (Lanczos), saturation x0.85 and value x0.9, WebP.'),
    'slice-b/textures/rock_normal.webp': ('texture', 'Rock normal (OpenGL)', ['rock_moss_set_02'], 'OpenGL normal map downscaled 2K -> 1K (Lanczos), WebP.'),
    'slice-b/textures/rock_orm.webp': ('texture', 'Rock roughness in G', ['rock_moss_set_02'], '2K roughness -> 1K, packed into G of an ORM map, WebP.'),
    'slice-b/textures/wood_albedo.webp': ('texture', 'Driftwood bark colour', ['dry_branches_medium_01'], '2K -> 1K, re-graded from grey weathered wood to dark brown, WebP. Used as bark on the original procedural root.'),
    'slice-b/textures/wood_normal.webp': ('texture', 'Driftwood bark normal (OpenGL)', ['dry_branches_medium_01'], 'OpenGL normal map downscaled 2K -> 1K (Lanczos), WebP.'),
    'slice-b/textures/wood_orm.webp': ('texture', 'Driftwood bark AO/roughness/metal', ['dry_branches_medium_01'], 'ARM map downscaled 2K -> 1K (Lanczos), WebP.'),
    'slice-b/textures/moss_albedo.webp': ('texture', 'Moss colour + alpha', ['moss_01'], '2K diffuse + alpha -> 512 RGBA, hue graded, colour dilated under alpha, WebP.'),
    'slice-b/textures/moss_normal.webp': ('texture', 'Moss normal (OpenGL)', ['moss_01'], 'OpenGL normal map downscaled 2K -> 512 (Lanczos), WebP.'),
    'slice-b/textures/substrate_albedo.webp': ('texture', 'Substrate colour (unique, baked)', ['gravelly_sand', 'coast_sand_03'], 'Both 2K diffuse maps sampled at aquarium grain scale in world space (non-linear depth mapping) and blended by the sand-clearing mask, with an original procedural carpet layer by coverage mask, hardscape contact darkening, tonal variation and a fade into deep water toward the rear (art/tools/prepare_textures_slice_b.py), WebP.'),
    'slice-b/textures/substrate_normal.webp': ('texture', 'Substrate normal (OpenGL, unique)', ['gravelly_sand', 'coast_sand_03'], 'Both 2K normal maps sampled in world space, blended by the clearing mask, flattened under the carpet, renormalised, WebP.'),
    'slice-c/environment.glb': (
        'geometry', 'Slice C natural environment geometry (approved Natural Environment vocabulary)',
        ['rock_07', 'boulder_01', 'rock_09', 'rock_moss_set_02', 'LeafSet022'],
        'Assembled by art/tools/build_slice_c.py: scanned rocks rock_07 (3.6k tris), boulder_01 (5.2k) '
        'and two rock_09 (1.9k each) welded and decimated from 27.8k/124k/23.3k source faces, placed '
        'in the approved hierarchy and partly buried; rock_moss_set_02 secondaries, transition '
        'stones and partly buried fragments decimated to 110-700 tris; the original procedural '
        'Composition B driftwood root (own geometry, no source mesh); photographed broad leaves cut '
        'along each leaf outline of the LeafSet022 atlas into tight curved strips (8 rows, UVs into '
        'the atlas) composed into camera-specific clusters at the hardscape seams; original '
        'procedural ribbon, fine stem, fan and low grass silhouettes from art/tools/slice_c_growth.py; '
        'substrate terrain falling away behind the hardscape; per-vertex contact shading and sway '
        'weights; materials stripped.'),
    'slice-c/textures/rock07_albedo.webp': ('texture', 'Scanned rock A colour', ['rock_07'], '4K diffuse -> 2K (Lanczos), saturation x0.75, value x0.9, isolated bright specks clamped to the 99.5th luminance percentile, WebP.'),
    'slice-c/textures/rock07_normal.webp': ('texture', 'Scanned rock A normal (OpenGL)', ['rock_07'], '4K OpenGL normal map -> 1K (Lanczos), WebP. Source roughness not shipped (a uniform ~0.30 caused glints).'),
    'slice-c/textures/boulder_albedo.webp': ('texture', 'Scanned boulder colour', ['boulder_01'], '4K diffuse -> 1K (Lanczos), saturation x0.75, value x0.95, bright specks clamped, WebP.'),
    'slice-c/textures/boulder_normal.webp': ('texture', 'Scanned boulder normal (OpenGL)', ['boulder_01'], '4K OpenGL normal map -> 1K (Lanczos), WebP.'),
    'slice-c/textures/rock09_albedo.webp': ('texture', 'Scanned front stone colour', ['rock_09'], '4K diffuse -> 512 (Lanczos), saturation x0.75, bright specks clamped, WebP.'),
    'slice-c/textures/rock09_normal.webp': ('texture', 'Scanned front stone normal (OpenGL)', ['rock_09'], '4K OpenGL normal map -> 512 (Lanczos), WebP.'),
    'slice-c/textures/stones_albedo.webp': ('texture', 'Secondary stone colour', ['rock_moss_set_02'], '2K diffuse -> 512 (Lanczos), saturation x0.65, value x0.72, WebP.'),
    'slice-c/textures/stones_normal.webp': ('texture', 'Secondary stone normal (OpenGL)', ['rock_moss_set_02'], '2K OpenGL normal map -> 512 (Lanczos), WebP.'),
    'slice-c/textures/wood_albedo.webp': ('texture', 'Driftwood bark colour (willow bark, waterlogged grade)', ['bark_willow_02'], '2K diffuse -> 1K, saturation x0.55, value x0.42, warm multiply (0.92, 0.76, 0.6), original fibre-aligned Voronoi crack pattern baked in, lifted x1.1 for the runtime light, WebP. Used as bark on the original procedural root.'),
    'slice-c/textures/wood_normal.webp': ('texture', 'Driftwood bark normal (OpenGL)', ['bark_willow_02'], '2K OpenGL normal map -> 512 (Lanczos), WebP.'),
    'slice-c/textures/leaves_albedo.webp': ('texture', 'Broad-leaf atlas colour + alpha', ['LeafSet022'], '2K colour + opacity -> 1K RGBA, hue +0.05, value x0.4 (darker, cooler), colour dilated under alpha, WebP.'),
    'slice-c/textures/leaves_normal.webp': ('texture', 'Broad-leaf atlas normal (OpenGL)', ['LeafSet022'], '2K OpenGL normal map -> 512 (Lanczos), WebP.'),
    'slice-c/textures/substrate_albedo.webp': ('texture', 'Substrate colour (unique, baked)', ['gravelly_sand', 'coast_sand_03'], 'Both 2K diffuse maps sampled at aquarium grain scale in world space (non-linear depth mapping): an irregular dark soil/gravel zone around the hardscape and finer sand elsewhere (art/tools/slice_c_layout.py masks), hardscape contact darkening, tonal variation, the floor light hierarchy and a fade into water before the floor falls away (art/tools/prepare_textures_slice_c.py), 2048x1024 WebP.'),
    'slice-c/textures/substrate_normal.webp': ('texture', 'Substrate normal (OpenGL, unique)', ['gravelly_sand', 'coast_sand_03'], 'Both 2K normal maps sampled in world space, blended by the soil mask, renormalised, 1024x512 WebP.'),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    acquisitions = {}
    for path in ACQUISITIONS:
        acquisitions.update(json.loads(path.read_text()))
    used = sorted({source for spec in SHIPPED.values() for source in spec[2]})
    sources = {}
    for asset_id in used:
        record = acquisitions[asset_id]
        creator = record['creator']
        if isinstance(creator, str):          # ambientCG records name the creator as text
            creator = {creator: 'All'}
        if 'archive' in record:               # ambientCG: files extracted from one archive
            original = [{'filename': f['file'], 'url': record['downloadUrl'], 'sha256': f['sha256']}
                        for f in record['files']]
        else:
            original = [{'filename': f['originalFilename'], 'url': f['url'], 'sha256': f['sha256']}
                        for f in record['files']]
        sources[asset_id] = {
            'sourceAssetName': record['name'],
            'source': record['source'],
            'sourcePage': record['sourcePage'],
            'creator': creator,
            'license': record['license'],
            'licenseUrl': record['licenseUrl'],
            'dateAcquired': record['dateAcquired'],
            'originalFiles': original,
            'status': 'GREEN',
        }
    files = []
    for relative, (role, label, derived, modifications, *generator) in SHIPPED.items():
        path = ASSETS / relative
        origin = {'origin': 'original', 'generator': generator[0]} if generator else {'origin': 'derived'}
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
            **origin,
        })
    shipped_on_disk = sorted(p.relative_to(ASSETS).as_posix() for p in ASSETS.rglob('*')
                             if p.is_file() and p.name != 'manifest.json')
    missing = sorted(set(shipped_on_disk) - set(SHIPPED))
    if missing:
        raise SystemExit(f'Unlisted shipped files: {missing}')
    manifest = {
        'schema': 1,
        'policy': 'Every shipped art file is GREEN (CC0 source + our modifications, or original Aquarium.exe procedural art generated by a named in-repo tool) and verified by SHA-256 at load time.',
        'licenseEvidence': LICENSE_EVIDENCE,
        'files': files,
        'sources': sources,
    }
    (ASSETS / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'manifest: {len(files)} files, {len(sources)} sources')


if __name__ == '__main__':
    main()
