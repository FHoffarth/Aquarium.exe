"""Prepare optimized Slice A runtime textures from approved CC0 sources.

Run after build_slice_a.py (which writes art/work/slice-a/ bake inputs):
  python art/tools/prepare_textures.py

Writes WebP textures to habitat/assets/slice-a/textures/. glTF UV convention:
textures are loaded with flipY = false, so image row 0 is texture v = 0.
"""

import json
import pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'art' / 'source' / 'polyhaven'
WORK = ROOT / 'art' / 'work' / 'slice-a'
OUT = ROOT / 'habitat' / 'assets' / 'slice-a' / 'textures'

# Must match build_slice_a.py substrate extent and composition.
SUBSTRATE_X = (-5.0, 5.0)
SUBSTRATE_Z = (-1.8, 2.8)
SUBSTRATE_SIZE = (2048, 1024)
HARDSCAPE_FOOTPRINTS = [
    # x, z, radius (habitat units): coarse grit gathers around these.
    # Keep in sync with ROCKS / WOOD in build_slice_a.py.
    (-2.75, -0.95, 0.95), (-3.45, -0.7, 0.75), (-1.85, 0.25, 0.75),
    (-0.55, 0.45, 0.5), (-0.1, 0.12, 0.4), (2.35, -0.5, 0.6),
    (-2.4, -0.85, 0.8),
]


def source(asset, suffix):
    return Image.open(SRC / asset / 'textures' / f'{asset}_{suffix}_2k.{"png" if suffix == "alpha" else "jpg"}')


def as_rgb(image):
    return np.asarray(image.convert('RGB'), dtype=np.float32) / 255.0


def as_alpha(image):
    data = np.asarray(image, dtype=np.float32)
    return data / (65535.0 if data.max() > 255 else 255.0)


def to_image(array, mode='RGB'):
    return Image.fromarray(np.clip(array * 255.0 + 0.5, 0, 255).astype(np.uint8), mode)


def save(image, name, quality=90, lossless=False):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    image.save(path, 'WEBP', quality=quality, method=6, lossless=lossless, exact=True)
    return path


def resized(image, size):
    return image.resize(size, Image.LANCZOS)


def grade_hsv_fast(rgb, hue=None, hue_mix=0.0, sat=1.0, val=1.0):
    maxc = rgb.max(axis=2)
    minc = rgb.min(axis=2)
    v = maxc
    delta = maxc - minc
    s = np.where(maxc > 1e-6, delta / np.maximum(maxc, 1e-6), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    safe = np.maximum(delta, 1e-6)
    h = np.where(maxc == r, (g - b) / safe % 6.0,
                 np.where(maxc == g, (b - r) / safe + 2.0, (r - g) / safe + 4.0)) / 6.0
    h = np.where(delta > 1e-6, h, 0.0)
    if hue is not None:
        h = h + (hue - h) * hue_mix
    s = np.clip(s * sat, 0, 1)
    v = np.clip(v * val, 0, 1)
    i = np.floor(h * 6.0).astype(int) % 6
    f = h * 6.0 - np.floor(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    choices = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]
    out = np.zeros_like(rgb)
    for k, (cr, cg, cb) in enumerate(choices):
        mask = i == k
        out[..., 0] = np.where(mask, cr, out[..., 0])
        out[..., 1] = np.where(mask, cg, out[..., 1])
        out[..., 2] = np.where(mask, cb, out[..., 2])
    return out


def rgba(rgb, alpha):
    return np.concatenate([rgb, alpha[..., None]], axis=2)


def dilate_color_under_alpha(rgb, alpha, passes=12):
    """Bleed leaf colour into transparent texels so mip/alpha-coverage edges stay green."""
    known = alpha > 0.5
    color = rgb.copy()
    for _ in range(passes):
        grown = known.copy()
        acc = np.zeros_like(color)
        count = np.zeros(known.shape, dtype=np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            shifted_known = np.roll(known, (dy, dx), axis=(0, 1))
            shifted_color = np.roll(color, (dy, dx), axis=(0, 1))
            add = shifted_known & ~known
            acc[add] += shifted_color[add]
            count[add] += 1
            grown |= shifted_known
        fill = (count > 0) & ~known
        color[fill] = acc[fill] / count[fill][:, None]
        known = grown
    return color


# ---------------------------------------------------------------- hardscape

def rocks():
    albedo = resized(source('rock_moss_set_02', 'diff'), (1024, 1024))
    rgb = grade_hsv_fast(as_rgb(albedo), sat=0.85, val=0.9)
    save(to_image(rgb), 'rock_albedo.webp')
    save(resized(source('rock_moss_set_02', 'nor_gl'), (1024, 1024)), 'rock_normal.webp', quality=92)
    rough = as_alpha(resized(source('rock_moss_set_02', 'rough'), (1024, 1024)).convert('L'))
    orm = np.stack([np.ones_like(rough), rough, np.zeros_like(rough)], axis=2)
    save(to_image(orm), 'rock_orm.webp')


def wood():
    rgb = as_rgb(resized(source('dry_branches_medium_01', 'diff'), (1024, 1024)))
    luminance = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    # Grey weathered branch -> dark waterlogged driftwood brown.
    brown = luminance[..., None] * np.array([0.78, 0.55, 0.38], dtype=np.float32) * 1.05
    graded = rgb * 0.22 + brown * 0.78
    save(to_image(graded), 'wood_albedo.webp')
    save(resized(source('dry_branches_medium_01', 'nor_gl'), (1024, 1024)), 'wood_normal.webp', quality=92)
    save(resized(source('dry_branches_medium_01', 'arm'), (1024, 1024)), 'wood_orm.webp')


def moss():
    rgb = as_rgb(resized(source('moss_01', 'diff'), (512, 512)))
    alpha = as_alpha(resized(source('moss_01', 'alpha'), (512, 512)))
    rgb = grade_hsv_fast(rgb, hue=0.27, hue_mix=0.35, sat=0.95, val=0.95)
    rgb = dilate_color_under_alpha(rgb, alpha)
    save(to_image(rgba(rgb, alpha), 'RGBA'), 'moss_albedo.webp', quality=92)
    save(resized(source('moss_01', 'nor_gl'), (512, 512)), 'moss_normal.webp', quality=92)


# ------------------------------------------------------------- vegetation

def plant_atlas():
    tiles = []
    normals = []
    for asset, hue, mix, sat, val in (('anthurium_botany_01', 0.36, 0.25, 0.9, 0.82),
                                      ('fern_02', 0.3, 0.2, 0.95, 0.95)):
        rgb = as_rgb(resized(source(asset, 'diff'), (1024, 1024)))
        alpha = as_alpha(resized(source(asset, 'alpha'), (1024, 1024)))
        rgb = grade_hsv_fast(rgb, hue=hue, hue_mix=mix, sat=sat, val=val)
        rgb = dilate_color_under_alpha(rgb, alpha)
        tiles.append(rgba(rgb, alpha))
        normals.append(as_rgb(resized(source(asset, 'nor_gl'), (512, 512))))
    save(to_image(np.concatenate(tiles, axis=1), 'RGBA'), 'plants_albedo.webp', quality=92)
    save(to_image(np.concatenate(normals, axis=1)), 'plants_normal.webp', quality=92)


CARD_ATLAS = (2048, 1024)
# Tile rectangles (x, y, w, h) in atlas pixels, y from the top. Must match
# CARD_TILES in build_slice_a.py.
CARD_TILES = {
    'carpet_0': (0, 0, 512, 256), 'carpet_1': (512, 0, 512, 256),
    'carpet_2': (0, 256, 512, 256), 'carpet_3': (512, 256, 512, 256),
    'stem_0': (1024, 0, 512, 1024), 'stem_1': (1536, 0, 512, 1024),
}
CARD_GRADES = {
    'carpet': dict(hue=0.31, hue_mix=0.3, sat=1.0, val=0.74),
    'stem_0': dict(hue=0.31, hue_mix=0.3, sat=1.2, val=0.95),
    'stem_1': dict(hue=0.03, hue_mix=0.55, sat=1.35, val=0.9),   # bronze-red accent
}


def card_atlas():
    width, height = CARD_ATLAS
    atlas = np.zeros((height, width, 4), dtype=np.float32)
    for name, (x, y, w, h) in CARD_TILES.items():
        tile = Image.open(WORK / 'cards' / f'{name}.png').convert('RGBA').resize((w, h), Image.LANCZOS)
        data = np.asarray(tile, dtype=np.float32) / 255.0
        rgb, alpha = data[..., :3], data[..., 3]
        grade = CARD_GRADES['carpet'] if name.startswith('carpet') else CARD_GRADES[name]
        rgb = grade_hsv_fast(rgb, **grade)
        rgb = dilate_color_under_alpha(rgb, alpha, passes=8)
        atlas[y:y + h, x:x + w] = rgba(rgb, alpha)
    save(to_image(atlas, 'RGBA'), 'cards_albedo.webp', quality=92)


# --------------------------------------------------------------- substrate

def value_noise(width, height, cells, seed):
    rng = np.random.default_rng(seed)
    grid = rng.random((cells[1] + 2, cells[0] + 2)).astype(np.float32)
    small = Image.fromarray((grid * 255).astype(np.uint8), 'L')
    return np.asarray(small.resize((width, height), Image.BICUBIC), dtype=np.float32) / 255.0


def tiled_layer(asset, tile_units, texels_per_unit, offset):
    width, height = SUBSTRATE_SIZE
    tile_w = int(round(tile_units * texels_per_unit[0]))
    tile_h = int(round(tile_units * texels_per_unit[1]))
    layers = {}
    for key in ('diff', 'nor_gl', 'arm'):
        tile = as_rgb(resized(source(asset, key), (tile_w, tile_h)))
        reps = (height // tile_h + 2, width // tile_w + 2, 1)
        big = np.tile(tile, reps)
        oy, ox = int(offset[1] * tile_h) % tile_h, int(offset[0] * tile_w) % tile_w
        layers[key] = big[oy:oy + height, ox:ox + width]
    return layers


def substrate():
    width, height = SUBSTRATE_SIZE
    span_x = SUBSTRATE_X[1] - SUBSTRATE_X[0]
    span_z = SUBSTRATE_Z[1] - SUBSTRATE_Z[0]
    density = (width / span_x, height / span_z)
    fine = tiled_layer('gravelly_sand', 2.4, density, (0.0, 0.0))
    coarse = tiled_layer('coast_sand_03', 2.1, density, (0.37, 0.61))

    xs = SUBSTRATE_X[0] + (np.arange(width) + 0.5) / width * span_x
    zs = SUBSTRATE_Z[0] + (np.arange(height) + 0.5) / height * span_z
    gx, gz = np.meshgrid(xs, zs)
    proximity = np.zeros_like(gx)
    for x, z, radius in HARDSCAPE_FOOTPRINTS:
        d = np.sqrt((gx - x) ** 2 + ((gz - z) * 1.3) ** 2)
        proximity = np.maximum(proximity, np.clip(1.0 - d / radius, 0.0, 1.0))
    back = np.clip((-gz - 0.2) / 0.9, 0.0, 1.0) * 0.35
    breakup = value_noise(width, height, (24, 8), 7) * 0.55 + value_noise(width, height, (80, 26), 11) * 0.45
    mask = np.clip(proximity ** 0.8 * 1.25 + back + (breakup - 0.5) * 0.55, 0.0, 1.0)
    mask = mask * mask * (3.0 - 2.0 * mask)

    m = mask[..., None]
    albedo = fine['diff'] * (1 - m) + coarse['diff'] * m
    # Contact occlusion baked by Blender (if present) darkens around hardscape.
    ao_path = WORK / 'substrate_ao.png'
    if ao_path.exists():
        ao = as_alpha(Image.open(ao_path).convert('L').resize((width, height), Image.LANCZOS))
        albedo = albedo * (0.35 + 0.65 * ao[..., None])
    # Gentle large-scale value variation so the floor does not read as one flat decal.
    tone = 0.85 + 0.3 * value_noise(width, height, (10, 4), 3)
    albedo = albedo * tone[..., None]
    # Aquarium substrate under water reads darker and warmer than dry beach sand.
    albedo = grade_hsv_fast(albedo, hue=0.08, hue_mix=0.25, sat=1.05, val=0.52)
    # Fade toward the rear so the floor dissolves into dark water instead of
    # ending on a hard horizon line (fixed camera: rear rows are far away).
    depth_fade = np.clip((gz + 1.55) / 2.1, 0.0, 1.0) ** 1.5
    water = np.array([0.02, 0.09, 0.11], dtype=np.float32)
    albedo = albedo * (0.06 + 0.94 * depth_fade[..., None]) + water * (1 - depth_fade[..., None]) * 0.35
    save(to_image(albedo), 'substrate_albedo.webp', quality=88)

    normal = fine['nor_gl'] * (1 - m) + coarse['nor_gl'] * m
    vec = normal * 2.0 - 1.0
    vec /= np.linalg.norm(vec, axis=2, keepdims=True) + 1e-6
    save(to_image(vec * 0.5 + 0.5), 'substrate_normal.webp', quality=90)
    np.save(WORK / 'substrate_mask.npy', mask.astype(np.float16))


def main():
    rocks()
    wood()
    moss()
    plant_atlas()
    card_atlas()
    substrate()
    summary = {path.name: Image.open(path).size for path in sorted(OUT.glob('*.webp'))}
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
