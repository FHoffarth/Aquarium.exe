"""Slice B composition data and terrain functions (pure Python, no Blender).

Shared by build_slice_b.py (Blender) and prepare_textures_slice_b.py (NumPy)
so geometry, cards and the baked substrate agree exactly.

Runtime translation of the approved Aquascape Hero Frame Pass 2
(composition B, branch claude/aquascape-hero-frame @ 9c2db27, frozen
reference). Coordinates are habitat units (x right, y up, z toward the
camera). Differences from the offline frame are deliberate runtime choices:
the driftwood sits 0.3 further back so it stays behind the fish swim volume
(z -0.65..0.65; the simulation has no obstacle avoidance), and vegetation
that was dense geometry offline becomes camera-facing cards or baked
substrate colour here.
"""

import math

FLOOR = -1.45
CAMERA = (0.0, 0.06, 6.2)
WOOD_Z_SHIFT = -0.3


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def gauss2(x, z, cx, cz, sx, sz):
    return math.exp(-(((x - cx) / sx) ** 2 + ((z - cz) / sz) ** 2))


def _hash(ix, iz, seed):
    h = (ix * 374761393 + iz * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def vnoise(x, z, seed=0):
    """Smooth 2D value noise in [-1, 1]."""
    x0, z0 = math.floor(x), math.floor(z)
    fx, fz = x - x0, z - z0
    sx, sz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a = _hash(x0, z0, seed) + (_hash(x0 + 1, z0, seed) - _hash(x0, z0, seed)) * sx
    b = _hash(x0, z0 + 1, seed) + (_hash(x0 + 1, z0 + 1, seed) - _hash(x0, z0 + 1, seed)) * sx
    return (a + (b - a) * sz) * 2.0 - 1.0


# ------------------------------------------------------------ terrain

MOUND = (0.36, -2.3, -0.5, 1.5, 1.0)
PATH = [(0.2, 2.2), (0.55, 1.2), (1.05, 0.3), (1.55, -0.6), (2.0, -1.6), (2.3, -2.6)]
SUBSTRATE_X = (-9.0, 9.0)
SUBSTRATE_Z = (-6.0, 2.7)


SUBSTRATE_V_EXPONENT = 0.7


def substrate_v(z):
    """Texture v for a substrate depth: front rows get most texels (the rear
    floor fades into water anyway). v = 0 at the front edge."""
    w = (SUBSTRATE_Z[1] - z) / (SUBSTRATE_Z[1] - SUBSTRATE_Z[0])
    return max(0.0, min(1.0, w)) ** SUBSTRATE_V_EXPONENT


def substrate_z(v):
    return SUBSTRATE_Z[1] - (v ** (1.0 / SUBSTRATE_V_EXPONENT)) * (SUBSTRATE_Z[1] - SUBSTRATE_Z[0])


def path_distance(x, z):
    best = 9.0
    for (ax, az), (bx, bz) in zip(PATH, PATH[1:]):
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)))
        best = min(best, math.hypot(x - ax - t * dx, z - az - t * dz))
    return best


def path_mask(x, z):
    """The sand clearing: narrow, broken by carpet tongues, fading before the back."""
    width = 0.3 + 0.18 * smoothstep(-2.0, 2.0, z)
    wobble = 0.22 * vnoise(x * 0.9, z * 0.9, 3) + 0.07 * vnoise(x * 4, z * 4, 1)
    core = 1.0 - smoothstep(width * 0.45, width, path_distance(x, z) + wobble)
    broken = smoothstep(-0.45, 0.05, vnoise(x * 1.4, z * 1.4, 8))
    return core * (0.35 + 0.65 * broken) * smoothstep(-1.9, -0.6, z)


def substrate_height(x, z):
    amp, cx, cz, sx, sz = MOUND
    back = 0.75 * smoothstep(0.6, -3.3, z) ** 1.4
    mound = amp * gauss2(x, z, cx, cz, sx, sz)
    shoulder = 0.12 * gauss2(x, z, cx + 1.4, cz + 0.3, 1.2, 1.0)
    right_low = -0.06 * smoothstep(-0.5, 3.0, x) * smoothstep(-2.5, 1.0, z)
    clearing = -0.035 * path_mask(x, z)
    undulation = 0.03 * vnoise(x * 0.7, z * 0.7, 5) + 0.01 * vnoise(x * 3, z * 3, 6)
    return back + mound + shoulder + right_low + clearing + undulation


def surface_y(x, z):
    return FLOOR + substrate_height(x, z)


def carpet_coverage(x, z):
    """Foreground carpet: dense around the hardscape base and front left,
    thinning to the right, organic edges and islands, never on the clearing."""
    left = 1.0 - smoothstep(-1.0, 3.2, x)
    front = 0.35 + 0.65 * smoothstep(-2.3, 0.2, z)
    base = 0.25 + 0.75 * left
    n = vnoise(x * 0.9, z * 1.3, 11) + 0.5 * vnoise(x * 2.6, z * 3.1, 12) + 0.25 * vnoise(x * 7, z * 7, 13)
    organic = smoothstep(-0.3, 0.25, n + 0.3 * left)
    clearing = 1.0 - smoothstep(0.1, 0.5, path_mask(x, z))
    return base * front * organic * clearing


# ------------------------------------------------------------ hardscape

ROCK_SCALE = 1.45
ROCKS = [
    # source, x, z, scale, yaw, sink, tilt, triangle target
    ('rock13', -2.95, -1.1, 0.7, 150, 0.36, -5, 2400),    # primary, rear left
    ('rock11', -1.7, -1.0, 0.6, 35, 0.38, 6, 2400),       # primary, rear centre-left
    ('rock10', -2.05, 0.1, 0.36, -40, 0.42, 3, 1300),     # secondary, front
    ('rock09', -3.05, 0.05, 0.34, 70, 0.42, -8, 1300),    # secondary, front left
    ('rock12', -1.05, 0.35, 0.2, 10, 0.42, 6, 700),       # transition
    ('rock08', -2.6, 0.62, 0.16, 120, 0.42, 0, 600),      # transition
    # secondary stones around the primaries' bases
    ('rock12', -3.5, -0.7, 0.26, 40, 0.45, 8, 600), ('rock08', -2.45, -0.72, 0.2, 200, 0.45, -6, 500),
    ('rock09', -1.15, -0.7, 0.24, -70, 0.45, 5, 600), ('rock08', -2.15, -0.55, 0.16, 15, 0.45, 10, 450),
    ('rock12', -2.5, 0.38, 0.17, 95, 0.45, -4, 450), ('rock08', -1.55, 0.38, 0.18, 250, 0.45, 6, 450),
    ('rock09', -3.55, 0.2, 0.18, 10, 0.45, -5, 450),
]
PEBBLES = [(-0.2, 0.95, 0.09), (0.15, 0.75, 0.06), (-0.95, 1.1, 0.075), (0.45, 1.35, 0.05),
           (-1.35, 0.35, 0.1), (-0.05, 0.2, 0.07), (1.25, -0.6, 0.06), (1.7, 0.4, 0.045),
           (-3.5, 0.3, 0.1), (-2.35, 0.9, 0.08), (0.8, -1.4, 0.05), (2.6, -1.1, 0.07)]

WOOD_GIRTH = 2.3
WOOD = [
    # Three primary gestures: hero sweep, steep rise, low back-left arm.
    ([(-2.45, None, -0.45), (-2.1, -0.55, -0.5), (-1.5, -0.05, -0.6), (-0.8, 0.4, -0.75),
      (-0.1, 0.72, -0.85), (0.5, 0.88, -0.95)], 0.12, 0.012),
    ([(-2.5, None, -0.55), (-2.3, -0.5, -0.7), (-1.95, 0.15, -0.85), (-1.5, 0.7, -1.0),
      (-1.0, 1.1, -1.1), (-0.72, 1.24, -1.15)], 0.085, 0.012),
    ([(-2.6, None, -0.7), (-2.85, -0.5, -1.0), (-3.05, 0.05, -1.3), (-3.1, 0.35, -1.5)], 0.06, 0.014),
]
ROOTS = [
    [(-2.45, -1.2, -0.45), (-2.9, None, -0.1), (-3.45, None, 0.2)],
    [(-2.4, -1.2, -0.4), (-2.0, None, 0.0), (-1.6, None, 0.3)],
    [(-2.5, -1.2, -0.5), (-2.85, None, -0.9), (-3.35, None, -1.2)],
    [(-2.35, -1.2, -0.45), (-1.95, None, -0.8), (-1.45, None, -1.15)],
]
HARDSCAPE_FOOTPRINTS = [
    # x, z, radius: contact darkening and coarse grit on the substrate
    (-2.95, -1.1, 1.3), (-1.7, -1.0, 1.1), (-2.05, 0.1, 0.8), (-3.05, 0.05, 0.75),
    (-1.05, 0.35, 0.45), (-2.6, 0.62, 0.4), (-2.45, -0.75, 0.9),
]

# ------------------------------------------------------------ vegetation

BROADLEAF_SPOTS = [(-2.35, 0.55, 1.0), (-1.6, 0.5, 0.9), (-2.8, 0.5, 0.85), (-1.3, 0.65, 0.75),
                   (-3.35, 0.4, 0.85), (-2.05, 0.7, 0.7), (-2.15, -0.2, 1.0),
                   (-2.75, -0.35, 0.9), (-1.35, -0.4, 0.8), (-3.45, -0.5, 0.8),
                   (-2.25, -0.62, 0.9), (-2.7, -0.62, 0.8), (-1.95, -0.4, 0.8), (-1.3, -0.7, 0.75),
                   (-3.3, -0.85, 0.8), (-1.15, -1.0, 0.7)]
CRYPT_GROUPS = [(0.35, 0.8, 1), (1.25, 0.25, 2), (0.75, -0.6, 2), (1.7, -0.1, 1)]
HAIRGRASS_CLUSTERS = [(0.9, 0.9, 7), (1.9, 0.35, 9), (2.8, 0.9, 6), (3.4, 0.2, 5), (0.35, -0.35, 6),
                      (1.2, -0.9, 8), (2.2, -1.3, 7), (-0.5, -1.1, 6), (3.1, -1.0, 6), (-0.2, 1.35, 4),
                      (1.55, 1.75, 4), (-1.0, -1.6, 5)]
# Background stem masses: centre x, z, half width, peak height, clumps, card kinds.
STEM_MASSES = [
    (-2.55, -2.35, 1.1, 2.9, 11, (0, 3, 0)),
    (-1.25, -2.65, 0.8, 2.1, 7, (2, 0)),
    (-0.15, -2.95, 0.6, 1.35, 5, (1, 3)),
    (1.75, -2.9, 0.55, 0.95, 4, (3, 1)),
    (3.3, -2.55, 0.8, 1.6, 6, (0, 2)),
    (-3.7, -1.75, 0.35, 1.3, 3, (3,)),
    (-1.9, -1.7, 0.5, 1.15, 4, (1, 2)),
    (0.75, -3.3, 1.4, 0.55, 6, (3, 1)), (2.6, -3.35, 1.2, 0.5, 5, (1,)), (-4.4, -3.2, 0.9, 1.4, 4, (0,)),
    (4.6, -3.1, 0.9, 1.1, 4, (3,)),
]
RIBBON_CLUMPS = [(3.05, -2.35, 14, (1.8, 2.8)), (3.85, -2.05, 8, (1.1, 1.9)), (2.35, -2.95, 9, (2.1, 3.0)),
                 (4.4, -2.9, 8, (2.2, 3.2)), (-3.35, -2.95, 9, (1.9, 2.7)), (-1.7, -3.1, 5, (2.0, 2.6))]
