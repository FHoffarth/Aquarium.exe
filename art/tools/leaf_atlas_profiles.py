"""Stage 2 (offline): extract per-leaf outlines from the ambientCG leaf and
blade atlases so each photographed leaf becomes a tight mesh (little alpha
area, low overdraw) instead of a transparent card.

  python art/tools/leaf_atlas_profiles.py

Writes art/work/stage2/leaf_profiles.json: for every leaf in each atlas, its
base-to-tip axis and, for N rows along that axis, the left/right extent of
the opaque region in atlas UV (glTF/Blender UV: v measured from the bottom).
"""

import json
import pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'art' / 'source' / 'ambientcg'
OUT = ROOT / 'art' / 'work' / 'stage2' / 'leaf_profiles.json'
ROWS = 14
# Atlas: which image axis runs base -> tip. 'up' = base at image bottom.
ATLASES = {
    'LeafSet022': 'up', 'LeafSet003': 'up', 'LeafSet001': 'up',
    'Foliage001': 'up', 'Foliage008': 'right', 'LeafSet002': 'up',
}


def components(mask):
    """Connected components of a boolean mask (4-connected), as index arrays."""
    height, width = mask.shape
    labels = np.zeros(mask.shape, dtype=np.int32)
    current = 0
    parts = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if labels[y0, x0]:
            continue
        current += 1
        stack = [(y0, x0)]
        labels[y0, x0] = current
        ys, xs = [], []
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = current
                    stack.append((ny, nx))
        parts.append((np.array(ys), np.array(xs)))
    return parts


def profile(asset, axis):
    opacity = Image.open(SOURCE / asset / f'{asset}_2K-JPG_Opacity.jpg').convert('L')
    size = opacity.size[0]
    small = np.asarray(opacity.resize((512, 512), Image.BILINEAR)) > 110
    scale = size / 512
    leaves = []
    for ys, xs in components(small):
        if len(ys) < 150:
            continue
        # Base -> tip along the image axis; rows sample the perpendicular extent.
        if axis == 'up':
            along_min, along_max = ys.max(), ys.min()          # base = bottom (large y)
            rows = []
            for i in range(ROWS + 1):
                a = along_min + (along_max - along_min) * i / ROWS
                band = np.abs(ys - a) <= 1.5
                if band.any():
                    lo, hi = xs[band].min(), xs[band].max() + 1
                else:
                    lo = hi = xs.mean()
                rows.append([float(a), float(lo), float(hi)])
            to_uv = lambda a, c: (c * scale / size, 1.0 - a * scale / size)   # noqa: E731
        else:  # 'right': base = left (small x)
            along_min, along_max = xs.min(), xs.max()
            rows = []
            for i in range(ROWS + 1):
                a = along_min + (along_max - along_min) * i / ROWS
                band = np.abs(xs - a) <= 1.5
                if band.any():
                    lo, hi = ys[band].min(), ys[band].max() + 1
                else:
                    lo = hi = ys.mean()
                rows.append([float(a), float(lo), float(hi)])
            to_uv = lambda a, c: (a * scale / size, 1.0 - c * scale / size)   # noqa: E731
        length_px = abs(along_max - along_min) * scale
        width_px = max(r[2] - r[1] for r in rows) * scale
        leaves.append({
            'length_px': length_px,
            'aspect': width_px / max(length_px, 1),
            # per row: t along base->tip, UV of left edge, UV of centre, UV of right edge
            'rows': [{'t': i / ROWS,
                      'left': to_uv(a, lo), 'centre': to_uv(a, (lo + hi) / 2), 'right': to_uv(a, hi),
                      'half_width': (hi - lo) * scale / 2 / max(length_px, 1)}
                     for i, (a, lo, hi) in enumerate(rows)],
        })
    leaves.sort(key=lambda leaf: -leaf['length_px'])
    return leaves


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {asset: profile(asset, axis) for asset, axis in ATLASES.items()}
    OUT.write_text(json.dumps(data, indent=1))
    for asset, leaves in data.items():
        print(asset, len(leaves), 'leaves; aspects', [round(leaf['aspect'], 2) for leaf in leaves])


if __name__ == '__main__':
    main()
