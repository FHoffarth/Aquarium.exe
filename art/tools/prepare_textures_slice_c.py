"""Prepare Slice C runtime textures (run after build_slice_c.py).

  python art/tools/prepare_textures_slice_c.py

Writes WebP textures to habitat/assets/slice-c/textures/ (loaded with
flipY = false: image row 0 is texture v = 0).

- Scanned rocks: albedo + OpenGL normal per source, no roughness maps. The
  runtime uses one matte roughness for all stone, which removes rock_07's
  glossy flecks (its source roughness map is a uniform ~0.30) and saves
  texture memory. Albedo is graded to the approved offline candidate.
- Wood: bark_willow_02 graded to the waterlogged driftwood brown of the
  approved Stage 1 B treatment, with the fibre-aligned crack pattern baked
  into the colour (same tile space as the runtime root UVs).
- Leaves: LeafSet022 colour + opacity -> one RGBA atlas, graded darker and
  cooler (aquatic), colour dilated under alpha; OpenGL normal.
- Substrate: unique baked floor from slice_c_layout.py: irregular dark
  soil/gravel zone around the hardscape, finer sand as breathing room,
  hardscape contact darkening, the floor's tonal hierarchy (key on the left,
  darker right and front edge) and the fade into water before the crest.
"""

import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import prepare_textures as P  # noqa: E402
import slice_c_layout as L  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'art' / 'source' / 'polyhaven'
ACG = ROOT / 'art' / 'source' / 'ambientcg'
OUT = ROOT / 'habitat' / 'assets' / 'slice-c' / 'textures'
P.OUT = OUT

SUBSTRATE_SIZE = (2048, 1024)
SUBSTRATE_NORMAL_SIZE = (1024, 512)
FIELD_SIZE = (512, 256)
WATER = np.array([0.010, 0.044, 0.052], dtype=np.float32)   # albedo the floor fades into


def scan(asset, kind):
    return Image.open(SRC / asset / 'textures' / f'{asset}_{kind}_4k.jpg')


def hue_shift(rgb, shift, sat=1.0, val=1.0):
    """HSV adjust like Blender's Hue/Saturation node (hue offset, not target)."""
    maxc, minc = rgb.max(axis=2), rgb.min(axis=2)
    delta = maxc - minc
    safe = np.maximum(delta, 1e-6)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(maxc == r, (g - b) / safe % 6.0,
                 np.where(maxc == g, (b - r) / safe + 2.0, (r - g) / safe + 4.0)) / 6.0
    h = np.where(delta > 1e-6, h, 0.0)
    s = np.where(maxc > 1e-6, delta / np.maximum(maxc, 1e-6), 0.0)
    h = (h + shift) % 1.0
    s = np.clip(s * sat, 0, 1)
    v = np.clip(maxc * val, 0, 1)
    i = np.floor(h * 6.0).astype(int) % 6
    f = h * 6.0 - np.floor(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    out = np.zeros_like(rgb)
    for k, (cr, cg, cb) in enumerate([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]):
        mask = i == k
        for channel, value in enumerate((cr, cg, cb)):
            out[..., channel] = np.where(mask, value, out[..., channel])
    return out


# ---------------------------------------------------------------- hardscape

def rocks():
    # rock_07 is the largest stone surface on screen and its UV islands use
    # only half the map: 2K colour (1K normal) keeps its pitting readable.
    for name, asset, size, normal_size, sat, val in (('rock07', 'rock_07', 2048, 1024, 0.75, 0.9),
                                                     ('boulder', 'boulder_01', 1024, 1024, 0.75, 0.95),
                                                     ('rock09', 'rock_09', 512, 512, 0.75, 1.0)):
        rgb = P.as_rgb(P.resized(scan(asset, 'diff'), (size, size)))
        rgb = P.grade_hsv_fast(rgb, sat=sat, val=val)
        # Tame isolated bright specks (they read as glints under the key).
        luminance = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        ceiling = np.percentile(luminance, 99.5)
        rgb *= np.minimum(1.0, ceiling / np.maximum(luminance, 1e-4))[..., None]
        P.save(P.to_image(rgb), f'{name}_albedo.webp')
        P.save(P.resized(scan(asset, 'nor_gl'), (normal_size, normal_size)), f'{name}_normal.webp', quality=92)
    rgb = P.as_rgb(P.resized(P.source('rock_moss_set_02', 'diff'), (512, 512)))
    P.save(P.to_image(P.grade_hsv_fast(rgb, sat=0.65, val=0.72)), 'stones_albedo.webp')
    P.save(P.resized(P.source('rock_moss_set_02', 'nor_gl'), (512, 512)), 'stones_normal.webp', quality=92)


def voronoi_edges(width, height, cells_u, cells_v, seed=7):
    """Tileable distance-to-edge (F2 - F1) in isotropic cell space."""
    rng = np.random.default_rng(seed)
    points = rng.random((cells_v, cells_u, 2))
    u = (np.arange(width) + 0.5) / width * cells_u
    v = (np.arange(height) + 0.5) / height * cells_v
    gu, gv = np.meshgrid(u, v)
    cu, cv = np.floor(gu).astype(int), np.floor(gv).astype(int)
    d1 = np.full(gu.shape, 9.0)
    d2 = np.full(gu.shape, 9.0)
    for dv in (-1, 0, 1):
        for du in (-1, 0, 1):
            nu, nv = cu + du, cv + dv
            p = points[nv % cells_v, nu % cells_u]
            d = np.hypot(nu + p[..., 0] - gu, nv + p[..., 1] - gv)
            d2 = np.where(d < d1, d1, np.minimum(d2, d))
            d1 = np.minimum(d1, d)
    return (d2 - d1) * 0.5


def wood():
    size = 1024
    rgb = P.as_rgb(P.resized(P.source('bark_willow_02', 'diff'), (size, size)))
    rgb = P.grade_hsv_fast(rgb, sat=0.55, val=0.42)
    rgb *= np.array([0.92, 0.76, 0.6], dtype=np.float32)
    # Offline crack pattern: Voronoi edges on UV x (6, 0.9) at scale 4.
    edges = voronoi_edges(size, size, 24, 4)
    crack = 0.6 + 0.4 * np.clip(edges / 0.035, 0.0, 1.0)
    rgb *= crack[..., None]
    # Runtime light is flatter than the offline key: lift slightly.
    P.save(P.to_image(np.clip(rgb * 1.1, 0, 1)), 'wood_albedo.webp')
    P.save(P.resized(P.source('bark_willow_02', 'nor_gl'), (512, 512)), 'wood_normal.webp', quality=92)


def leaves():
    size = 1024
    color = Image.open(ACG / 'LeafSet022' / 'LeafSet022_2K-JPG_Color.jpg')
    opacity = Image.open(ACG / 'LeafSet022' / 'LeafSet022_2K-JPG_Opacity.jpg').convert('L')
    rgb = P.as_rgb(P.resized(color, (size, size)))
    alpha = P.as_alpha(P.resized(opacity, (size, size)))
    # Darker, cooler, aquatic (approved candidate grade: hue +0.035, sat 1.1).
    rgb = hue_shift(rgb, 0.05, sat=1.0, val=0.4)
    rgb = P.dilate_color_under_alpha(rgb, alpha, passes=10)
    P.save(P.to_image(P.rgba(rgb, alpha), 'RGBA'), 'leaves_albedo.webp', quality=92)
    normal = Image.open(ACG / 'LeafSet022' / 'LeafSet022_2K-JPG_NormalGL.jpg').convert('RGB')
    P.save(P.resized(normal, (512, 512)), 'leaves_normal.webp', quality=90)


# ---------------------------------------------------------------- substrate

def field(function, size):
    fw, fh = FIELD_SIZE
    x0, x1 = L.SUBSTRATE_X
    out = np.zeros((fh, fw), dtype=np.float32)
    for row in range(fh):
        z = L.substrate_z((row + 0.5) / fh)
        for column in range(fw):
            out[row, column] = function(x0 + (column + 0.5) / fw * (x1 - x0), z)
    image = Image.fromarray(out, 'F').resize(size, Image.BICUBIC)
    return np.clip(np.asarray(image, dtype=np.float32), 0.0, 1.0)


def world_grid(size):
    width, height = size
    x0, x1 = L.SUBSTRATE_X
    xs = x0 + (np.arange(width) + 0.5) / width * (x1 - x0)
    zs = np.array([L.substrate_z((row + 0.5) / height) for row in range(height)], dtype=np.float32)
    return np.meshgrid(xs, zs)


def world_tiled(image_rgb, tile_units, grid, offset=(0.0, 0.0)):
    gx, gz = grid
    tile_px = image_rgb.shape[0]
    u = ((gx / tile_units + offset[0]) % 1.0 * tile_px).astype(np.int32) % tile_px
    v = ((gz / tile_units + offset[1]) % 1.0 * tile_px).astype(np.int32) % tile_px
    return image_rgb[v, u]


def substrate():
    size = SUBSTRATE_SIZE
    grid = world_grid(size)
    gravel = world_tiled(P.as_rgb(P.resized(P.source('gravelly_sand', 'diff'), (1024, 1024))), 1.9, grid)
    sand = world_tiled(P.as_rgb(P.resized(P.source('coast_sand_03', 'diff'), (1024, 1024))), 2.1, grid, (0.37, 0.61))
    soil = field(L.soil_mask, size)[..., None]
    near = field(L.hardscape_near, size)[..., None]
    light = field(L.floor_light, size)[..., None]
    fade = field(L.depth_fade, size)[..., None]

    soil_rgb = P.grade_hsv_fast(gravel, hue=0.07, hue_mix=0.3, sat=0.7, val=0.28)
    sand_rgb = P.grade_hsv_fast(sand, hue=0.1, hue_mix=0.3, sat=0.45, val=0.56)
    albedo = sand_rgb * (1 - soil) + soil_rgb * soil
    albedo *= 1.0 - 0.5 * near ** 0.9                      # contact darkening at the rock/root bases
    albedo *= 0.88 + 0.24 * P.value_noise(size[0], size[1], (18, 8), 4)[..., None]
    albedo *= light
    albedo = albedo * fade + WATER * (1 - fade)
    P.save(P.to_image(albedo), 'substrate_albedo.webp', quality=88)

    ngrid = world_grid(SUBSTRATE_NORMAL_SIZE)
    gravel_n = world_tiled(P.as_rgb(P.resized(P.source('gravelly_sand', 'nor_gl'), (1024, 1024))), 1.9, ngrid)
    sand_n = world_tiled(P.as_rgb(P.resized(P.source('coast_sand_03', 'nor_gl'), (1024, 1024))), 2.1, ngrid,
                         (0.37, 0.61))
    soil_small = field(L.soil_mask, SUBSTRATE_NORMAL_SIZE)[..., None]
    normal = sand_n * (1 - soil_small) + gravel_n * soil_small
    vec = normal * 2.0 - 1.0
    vec /= np.linalg.norm(vec, axis=2, keepdims=True) + 1e-6
    P.save(P.to_image(vec * 0.5 + 0.5), 'substrate_normal.webp', quality=90)


def main():
    rocks()
    wood()
    leaves()
    substrate()
    summary = {path.name: Image.open(path).size for path in sorted(OUT.glob('*.webp'))}
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
