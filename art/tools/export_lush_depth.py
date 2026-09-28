"""Export camera-ray depth for the locked lush scene, without changing it.

Run with Blender against art/work/lush-reference/lush-water-reference.blend.
The half-resolution float array is used only to grade the approved plate.
"""

import pathlib
import time

import bpy
import numpy as np
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'art/work/lush-reference/camera-depth-half.npy'
BACKGROUND_OUTPUT = ROOT / 'art/work/lush-reference/background-mask-half.npy'
WIDTH, HEIGHT = 960, 540
scene = bpy.context.scene
camera = scene.camera
depsgraph = bpy.context.evaluated_depsgraph_get()
corners = camera.data.view_frame(scene=scene)
left = min(v.x for v in corners)
right = max(v.x for v in corners)
bottom = min(v.y for v in corners)
top = max(v.y for v in corners)
forward = corners[0].z
rotation = camera.matrix_world.to_3x3()
origin = camera.matrix_world.translation
depth = np.full((HEIGHT, WIDTH), np.inf, dtype=np.float32)
background = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
excluded = ('hero-', 'sparse water particle ')
started = time.monotonic()

for row in range(HEIGHT):
    y = top + (bottom - top) * ((row + 0.5) / HEIGHT)
    for column in range(WIDTH):
        x = left + (right - left) * ((column + 0.5) / WIDTH)
        direction = (rotation @ Vector((x, y, forward))).normalized()
        ray_origin = origin.copy()
        travelled = 0.0
        for _ in range(5):
            hit, location, _normal, _face, obj, _matrix = scene.ray_cast(
                depsgraph, ray_origin, direction, distance=100.0)
            if not hit:
                break
            distance = (location - ray_origin).length
            travelled += distance
            if not obj.name.startswith(excluded):
                depth[row, column] = travelled
                background[row, column] = obj.name == 'blue water background'
                break
            ray_origin = ray_origin + direction * (distance + 0.001)
            travelled += 0.001
    if row % 90 == 0:
        print(f'depth row {row}/{HEIGHT}, elapsed {time.monotonic()-started:.1f}s', flush=True)

np.save(OUTPUT, depth)
np.save(BACKGROUND_OUTPUT, background)
valid = depth[np.isfinite(depth)]
print(f'Wrote {OUTPUT}; valid={valid.size}/{depth.size}; '
      f'distance percentiles={np.percentile(valid, [1, 10, 50, 90, 99])}; '
      f'elapsed={time.monotonic()-started:.1f}s', flush=True)
print(f'Background pixels: {background.sum()}/{background.size}', flush=True)
