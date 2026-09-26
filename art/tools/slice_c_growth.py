"""Original, camera-aware planted masses for the Slice C aquarium.

Four silhouettes share one vertex-coloured mesh: flowing ribbons, fine
branching stems, small fern-like fans, and irregular foreground grass.
No external plant image or model is used.
"""

import math
import random

import bmesh
from mathutils import Vector


def build_growth(layout, shared):
    rng = random.Random(20260926)
    v = shared.B
    bm = bmesh.new()
    col = bm.loops.layers.float_color.new('Col')
    camera = v(*layout.CAMERA)
    up = Vector((0, 0, 1))

    def face(points, colour):
        f = bm.faces.new([bm.verts.new(p) for p in points])
        for loop in f.loops:
            loop[col] = (*colour, 1.0)

    def colour(family, shade=1.0):
        palettes = {
            'ribbon': [(0.20, 0.43, 0.24), (0.32, 0.49, 0.22), (0.15, 0.37, 0.26)],
            'stem': [(0.20, 0.44, 0.25), (0.28, 0.43, 0.19), (0.18, 0.38, 0.31)],
            'fan': [(0.18, 0.48, 0.31), (0.31, 0.52, 0.25), (0.24, 0.42, 0.27)],
            'grass': [(0.16, 0.39, 0.23), (0.25, 0.46, 0.22), (0.18, 0.34, 0.25)],
        }
        base = rng.choice(palettes[family])
        jitter = rng.uniform(0.82, 1.16) * shade * 0.55
        return tuple(min(1.0, c * jitter) for c in base)

    def ribbon(x, z, height, width, lean, family='ribbon'):
        base = v(x, layout.surface_y(x, z) - 0.035, z)
        phase = rng.uniform(0, math.tau)
        toward = (camera - base).normalized()
        right = up.cross(toward).normalized()
        tint = colour(family, rng.uniform(0.9, 1.1))
        previous = None
        for i in range(11):
            t = i / 10
            center = base + up * height * t
            center += right * (lean * t * t + 0.055 * math.sin(5 * t + phase) * t)
            center += toward * (0.09 * math.sin(3.5 * t + phase) * t)
            side = (right * math.cos(t * 2.4 + phase * 0.22)
                    + toward * math.sin(t * 2.4 + phase * 0.22)).normalized()
            half = width * (0.22 + 0.78 * math.sin(math.pi * (0.08 + 0.87 * t)) ** 0.8) / 2
            pair = (center - side * half, center + side * half)
            if previous:
                face((previous[0], previous[1], pair[1], pair[0]), tint)
            previous = pair

    def lance(base, direction, length, width, tint):
        direction.normalize()
        view = (camera - base).normalized()
        side = direction.cross(view)
        if side.length < 0.01:
            side = direction.cross(v(0, 1, 0))
        side.normalize()
        mid = base + direction * length * 0.53
        tip = base + direction * length
        face((base, mid - side * width, tip, mid + side * width), tint)

    def fine_stem(x, z, height, fan=False):
        base = v(x, layout.surface_y(x, z) - 0.03, z)
        phase = rng.uniform(0, math.tau)
        bend = rng.uniform(-0.18, 0.18)
        tint = colour('fan' if fan else 'stem', rng.uniform(0.78, 1.07))
        levels = 12 if fan else 13
        for k in range(2, levels + 1):
            t = k / levels
            center = base + v(bend * t * t, height * t, math.sin(phase + t * 4) * 0.06 * t)
            angle = phase + k * 2.39996
            for side_index in (-1, 1):
                theta = angle + side_index * (1.0 if fan else 1.35)
                spread = (0.24 if fan else 0.16) * (1 - 0.55 * t) * rng.uniform(0.8, 1.2)
                direction = v(math.cos(theta) * spread,
                              (0.12 if fan else 0.09) + 0.09 * t,
                              math.sin(theta) * spread * 0.45)
                lance(center, direction, direction.length,
                      (0.035 if fan else 0.022) * (1 - 0.4 * t), tint)

    # Peaks are staggered and cross depth layers. They leave a large central
    # swimming opening and rise behind, beside, and in front of the wood.
    masses = [
        (-4.65, -1.45, 0.42, 2.7, 37, 'ribbon'),
        (-3.95, -1.85, 0.45, 2.9, 43, 'stem'),
        (-3.15, -1.9, 0.52, 2.65, 54, 'fan'),
        (-2.25, -1.8, 0.42, 2.2, 42, 'stem'),
        (-1.35, -1.82, 0.39, 1.65, 29, 'fan'),
        (-0.35, -2.0, 0.31, 0.9, 16, 'stem'),
        (3.15, -1.8, 0.43, 1.45, 29, 'fan'),
        (4.0, -1.72, 0.49, 2.25, 46, 'stem'),
        (4.7, -1.4, 0.45, 2.7, 35, 'ribbon'),
    ]
    for cx, cz, spread, peak, count, kind in masses:
        for _ in range(count):
            x = cx + rng.gauss(0, spread * 0.56)
            z = cz + rng.gauss(0, spread * 0.4)
            dome = max(0.45, 1 - 0.32 * abs(x - cx) / spread)
            h = peak * dome * rng.uniform(0.58, 1.12)
            if kind == 'ribbon':
                ribbon(x, z, h, rng.uniform(0.035, 0.075), rng.uniform(-0.35, 0.35))
            else:
                fine_stem(x, z, h, fan=kind == 'fan')

    # A few short, deep clumps bridge the two planted banks below the swim lane.
    for cx, cz, peak, count in [(0.55, -2.05, 0.52, 7), (1.55, -2.12, 0.66, 9),
                                (2.35, -1.95, 0.82, 14)]:
        for _ in range(count):
            x, z = cx + rng.gauss(0, 0.27), cz + rng.gauss(0, 0.16)
            fine_stem(x, z, peak * rng.uniform(0.55, 1.12), fan=True)

    # Distinct ribbon islands break the small-leaf backdrop near the root.
    for cx, cz, count, peak in [(-3.55, -0.88, 35, 2.05), (-1.45, -1.25, 30, 1.75),
                                (3.4, -1.0, 27, 1.65), (4.25, -0.45, 27, 2.05)]:
        for _ in range(count):
            x, z = cx + rng.gauss(0, 0.25), cz + rng.gauss(0, 0.18)
            ribbon(x, z, peak * rng.uniform(0.58, 1.12), rng.uniform(0.035, 0.085),
                   rng.uniform(-0.5, 0.5))

    # Low, broken transition plants cover rock bases without making a hedge.
    low = [(-3.9, 0.9, 0.55, 46), (-2.75, 1.2, 0.62, 60), (-1.6, 0.85, 0.52, 49),
           (-0.5, 0.35, 0.38, 28), (0.5, -0.65, 0.3, 12),
           (2.75, 0.72, 0.46, 37), (3.85, 1.15, 0.56, 54), (4.65, 0.5, 0.5, 40)]
    for cx, cz, spread, count in low:
        for _ in range(count):
            x = cx + rng.gauss(0, spread * 0.55)
            z = cz + rng.gauss(0, spread * 0.35)
            h = rng.uniform(0.16, 0.48)
            ribbon(x, z, h, rng.uniform(0.018, 0.045), rng.uniform(-0.22, 0.22), 'grass')

    bm.normal_update()
    growth = shared.mesh_object('slice-c-growth', bm)
    growth.data.color_attributes.active_color = growth.data.color_attributes['Col']
    shared.set_sway_by_height(growth, scale=0.65, exponent=1.4)
    return growth
