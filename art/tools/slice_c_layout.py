"""Slice C composition data and terrain functions (pure Python, no Blender).

The Natural Environment runtime slice: the approved offline candidate
(branch claude/natural-env-stage1, docs/natural-env-candidate-report.md)
translated for the real-time habitat. Shared by build_slice_c.py (Blender)
and prepare_textures_slice_c.py (NumPy) so geometry and the baked substrate
agree exactly.

Everything not redefined here is Slice B's composition (slice_b_layout.py):
the rock hierarchy, the Composition B root (three gestures, surface roots,
stubs, WOOD_Z_SHIFT behind the fish volume) and the camera. Slice C changes
the vegetation vocabulary and the floor:

- no moss, no background plant wall, no carpet, no sand path;
- the floor rises only into low soil shoulders at the hardscape base and then
  falls away behind it, so the rear substrate drops out of view into dark
  water instead of ending in a lit horizon line;
- an irregular dark soil/gravel zone surrounds the hardscape, with finer sand
  kept only as breathing room in front and to the right.
"""

import math

from slice_b_layout import (  # noqa: F401  (re-exported for build_slice_c.py)
    CAMERA, FLOOR, HARDSCAPE_FOOTPRINTS, PEBBLES, ROCK_SCALE, ROCKS, ROOTS, WOOD, WOOD_GIRTH, WOOD_Z_SHIFT,
    gauss2, smoothstep, vnoise,
)

SUBSTRATE_X = (-9.0, 9.0)
SUBSTRATE_Z = (-6.0, 2.7)
SUBSTRATE_V_EXPONENT = 0.6

# The camera looks slightly upward (runtime scene: lookAt(0, CAMERA_TARGET_Y, 0))
# so the floor takes less of the frame; the fish volume stays fully in view.
CAMERA_TARGET_Y = 0.24

# Scanned hardscape (Stage 1): ROCKS index -> Poly Haven source, target height.
# Other ROCKS entries stay rock_moss_set_02 secondaries.
SCANNED_ROCKS = {
    0: ('rock_07', 1.35),      # primary, rear left
    1: ('boulder_01', 1.2),    # primary, rear centre-left
    2: ('rock_09', 0.5),       # secondary, front
    3: ('rock_09', 0.42),      # secondary, front left
}
SCANNED_SINK_BONUS = 0.06      # scanned rocks sit a little deeper than offline


def substrate_v(z):
    w = (SUBSTRATE_Z[1] - z) / (SUBSTRATE_Z[1] - SUBSTRATE_Z[0])
    return max(0.0, min(1.0, w)) ** SUBSTRATE_V_EXPONENT


def substrate_z(v):
    return SUBSTRATE_Z[1] - (v ** (1.0 / SUBSTRATE_V_EXPONENT)) * (SUBSTRATE_Z[1] - SUBSTRATE_Z[0])


def crest_z(x):
    """Where the floor starts to fall away behind the hardscape: irregular in
    x so the drop never reads as a straight line."""
    return -2.35 + 0.45 * vnoise(x * 0.35, 0.0, 21) + 0.18 * vnoise(x * 1.1, 0.0, 22)


def hardscape_near(x, z):
    best = 0.0
    for hx, hz, radius in HARDSCAPE_FOOTPRINTS:
        d = math.hypot(x - hx, (z - hz) * 1.25)
        best = max(best, max(0.0, 1.0 - d / (radius * 1.25)))
    return best


def substrate_height(x, z):
    mound = 0.34 * gauss2(x, z, -2.3, -0.6, 1.45, 0.95)
    # Soil shoulders around the rock bases: the hardscape grows out of the floor.
    shoulders = 0.07 * hardscape_near(x, z) ** 1.5
    shoulder_right = 0.08 * gauss2(x, z, -0.9, -0.6, 1.0, 0.8)
    # Behind the hardscape a low rise, then the floor falls away into depth.
    crest = crest_z(x)
    rise = 0.22 * smoothstep(0.8, -1.6, z)
    fall = -1.05 * smoothstep(crest, crest - 2.6, z) ** 1.3
    right_low = -0.07 * smoothstep(-0.5, 3.0, x) * smoothstep(-2.5, 1.0, z)
    undulation = 0.03 * vnoise(x * 0.7, z * 0.7, 5) + 0.012 * vnoise(x * 3, z * 3, 6)
    return mound + shoulders + shoulder_right + rise + fall + right_low + undulation


def surface_y(x, z):
    return FLOOR + substrate_height(x, z)


def path_mask(x, z):
    """Slice C has no sand path; kept for Slice B helpers that expect it."""
    return 0.0


def soil_mask(x, z):
    """Dark soil / coarse gravel zone around the hardscape: irregular,
    noise-broken edge, strongest at the rock and root bases."""
    near = 0.0
    for hx, hz, radius in HARDSCAPE_FOOTPRINTS:
        d2 = (x - hx) ** 2 + ((z - hz) * 1.2) ** 2
        near = max(near, math.exp(-d2 / (1.35 * radius * radius)))
    # the left third behind/under the hardscape stays soil
    near = max(near, 0.8 * (1.0 - smoothstep(-3.2, -1.2, x)) * smoothstep(1.2, -0.2, z))
    edge = 0.32 * vnoise(x * 1.3, z * 1.3, 31) + 0.14 * vnoise(x * 3.7, z * 3.7, 32)
    return smoothstep(0.28, 0.58, near + edge)


def floor_light(x, z):
    """Baked tonal hierarchy of the floor: brighter only where the key lands
    (left-centre front of the hardscape), darker to the right and front edge,
    and fading into the water colour before the crest."""
    key = gauss2(x, z, -1.1, 0.3, 2.2, 1.4)
    right = smoothstep(-0.8, 3.8, x)
    front = smoothstep(1.0, 2.7, z)
    return max(0.0, 0.6 + 0.4 * key - 0.45 * right - 0.3 * front)


def depth_fade(x, z):
    """1 = floor colour, 0 = water: gone before the floor starts to fall."""
    crest = crest_z(x)
    return smoothstep(crest - 0.2, crest + 1.6, z)


# ------------------------------------------------------------ vegetation

# LeafSet022 cluster spots (x, z, scale): strongest mass at the left hardscape
# base and seams, falling off toward the centre; nothing in the right half,
# nothing on rock tops or alone on open sand. Grown from the approved
# candidate's spots, tucked against rocks/root.
LEAF_SPOTS = [
    (-2.35, 0.55, 1.0), (-1.6, 0.5, 0.95), (-2.8, 0.5, 0.9), (-1.3, 0.62, 0.8),
    (-3.35, 0.42, 0.9), (-2.05, 0.7, 0.75), (-2.15, -0.22, 1.0), (-2.75, -0.38, 0.95),
    (-1.35, -0.42, 0.85), (-3.45, -0.52, 0.9), (-2.25, -0.64, 0.9), (-2.7, -0.64, 0.85),
    (-1.95, -0.42, 0.85), (-1.3, -0.72, 0.75), (-3.3, -0.88, 0.85), (-1.15, -1.02, 0.7),
    # falloff toward the centre, against the transition stone
    (-0.85, 0.5, 0.6), (-0.95, 0.15, 0.5),
]
LEAF_GAP_SEED = 20260925
