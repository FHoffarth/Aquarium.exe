"""Prepare Slice B runtime textures (run after build_slice_b.py).

  python art/tools/prepare_textures_slice_b.py

Rock, wood and moss maps reuse the Slice A grading (prepare_textures.py) and
are written to habitat/assets/slice-b/textures/ so the two slices stay
independent (either can ship or fall back alone). New here: the card atlas
(background stem clumps + carpet relief) and a unique baked substrate that
carries the carpet coverage, the broken sand clearing, hardscape contact
darkening and the fade into deep water, all from slice_b_layout.py.
"""

import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import prepare_textures as P  # noqa: E402
import slice_b_layout as L  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = ROOT / 'art' / 'work' / 'slice-b'
OUT = ROOT / 'habitat' / 'assets' / 'slice-b' / 'textures'
P.OUT = OUT

CARD_ATLAS = (2048, 768)       # must match build_slice_b.py
STEM_TILE = (256, 512)
CARPET_TILE = (512, 256)
SUBSTRATE_SIZE = (2048, 1024)
FIELD_SIZE = (512, 256)        # layout functions are evaluated here, then upscaled


def card_atlas():
    width, height = CARD_ATLAS
    atlas = np.zeros((height, width, 4), dtype=np.float32)
    tiles = [(f'stem_{i}', i * STEM_TILE[0], 0, STEM_TILE) for i in range(8)]
    tiles += [(f'carpet_{i}', i * CARPET_TILE[0], STEM_TILE[1], CARPET_TILE) for i in range(4)]
    for name, x, y, (w, h) in tiles:
        tile = Image.open(WORK / 'cards' / f'{name}.png').convert('RGBA').resize((w, h), Image.LANCZOS)
        data = np.asarray(tile, dtype=np.float32) / 255.0
        rgb, alpha = data[..., :3], data[..., 3]
        # Tiles hold near-albedo colour; darken toward aquatic greens so the
        # runtime light, not the tile, sets the brightness.
        rgb = P.grade_hsv_fast(rgb, hue=0.3, hue_mix=0.2, sat=1.05, val=0.72)
        rgb = P.dilate_color_under_alpha(rgb, alpha, passes=8)
        atlas[y:y + h, x:x + w] = P.rgba(rgb, alpha)
    P.save(P.to_image(atlas, 'RGBA'), 'cards_albedo.webp', quality=92)


def field(function):
    fw, fh = FIELD_SIZE
    x0, x1 = L.SUBSTRATE_X
    out = np.zeros((fh, fw), dtype=np.float32)
    for row in range(fh):
        # Image row 0 is texture v = 0 (flipY = false): the front edge.
        z = L.substrate_z((row + 0.5) / fh)
        for column in range(fw):
            out[row, column] = function(x0 + (column + 0.5) / fw * (x1 - x0), z)
    image = Image.fromarray(out, 'F').resize(SUBSTRATE_SIZE, Image.BICUBIC)
    return np.clip(np.asarray(image, dtype=np.float32), 0.0, 1.0)


def world_grid():
    width, height = SUBSTRATE_SIZE
    x0, x1 = L.SUBSTRATE_X
    xs = x0 + (np.arange(width) + 0.5) / width * (x1 - x0)
    zs = np.array([L.substrate_z((row + 0.5) / height) for row in range(height)], dtype=np.float32)
    return np.meshgrid(xs, zs)


def world_tiled(image_rgb, tile_units, grid, offset=(0.0, 0.0)):
    """Samples a tileable texture at world positions (the v axis is non-linear)."""
    gx, gz = grid
    tile_px = image_rgb.shape[0]
    u = ((gx / tile_units + offset[0]) % 1.0 * tile_px).astype(np.int32) % tile_px
    v = ((gz / tile_units + offset[1]) % 1.0 * tile_px).astype(np.int32) % tile_px
    return image_rgb[v, u]


def substrate():
    width, height = SUBSTRATE_SIZE
    grid = world_grid()
    gravel = {k: world_tiled(P.as_rgb(P.resized(P.source('gravelly_sand', k), (1024, 1024))), 2.4, grid)
              for k in ('diff', 'nor_gl')}
    sand = {k: world_tiled(P.as_rgb(P.resized(P.source('coast_sand_03', k), (1024, 1024))), 2.1, grid, (0.37, 0.61))
            for k in ('diff', 'nor_gl')}
    carpet = world_tiled(P.as_rgb(Image.open(WORK / 'cards' / 'carpet_top.png').convert('RGB')), 1.1, grid)

    clearing = field(L.path_mask)[..., None] * 0.85
    coverage = field(L.carpet_coverage)[..., None]

    def contact(x, z):
        best = 0.0
        for hx, hz, radius in L.HARDSCAPE_FOOTPRINTS:
            d = ((x - hx) ** 2 + ((z - hz) * 1.3) ** 2) ** 0.5
            best = max(best, max(0.0, 1.0 - d / radius))
        return best
    near = field(contact)[..., None]
    depth = field(lambda x, z: L.smoothstep(-2.7, 0.2, z))[..., None]

    ground = gravel['diff'] * (1 - clearing) + sand['diff'] * clearing
    ground = P.grade_hsv_fast(ground, hue=0.08, hue_mix=0.25, sat=0.8, val=0.5)
    leaves = P.grade_hsv_fast(carpet, hue=0.3, hue_mix=0.25, sat=1.0, val=0.62)
    albedo = ground * (1 - coverage) + leaves * coverage
    albedo *= 1.0 - 0.55 * near ** 0.8
    tone = 0.85 + 0.3 * P.value_noise(width, height, (14, 6), 3)[..., None]
    albedo *= tone
    # Rear floor dissolves into deep water (the runtime haze does the rest).
    water = np.array([0.012, 0.05, 0.058], dtype=np.float32)
    albedo = albedo * (0.12 + 0.88 * depth ** 1.4) + water * (1 - depth ** 1.4)
    P.save(P.to_image(albedo), 'substrate_albedo.webp', quality=88)

    normal = gravel['nor_gl'] * (1 - clearing) + sand['nor_gl'] * clearing
    flat = np.array([0.5, 0.5, 1.0], dtype=np.float32)
    normal = normal * (1 - coverage * 0.7) + flat * coverage * 0.7
    vec = normal * 2.0 - 1.0
    vec /= np.linalg.norm(vec, axis=2, keepdims=True) + 1e-6
    P.save(P.to_image(vec * 0.5 + 0.5), 'substrate_normal.webp', quality=90)


def main():
    P.rocks()
    P.wood()
    P.moss()
    card_atlas()
    substrate()
    summary = {path.name: Image.open(path).size for path in sorted(OUT.glob('*.webp'))}
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
