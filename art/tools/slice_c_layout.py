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
    CAMERA, FLOOR, PEBBLES, ROCK_SCALE, WOOD_GIRTH, WOOD_Z_SHIFT, gauss2, smoothstep, vnoise,
)

# ------------------------------------------------------------ hardscape
# Composition B, re-spaced for the runtime frame (composition polish): the
# hero root sweeps lower and farther toward the centre, the boulder stands
# apart from rock_07 so the root base reads between them, and a surface root
# plus a trail of buried stones carry the hardscape diagonally into the
# open water instead of ending at the left third.

ROCKS = [
    # source, x, z, scale, yaw, sink, tilt, triangle target (indices 0-3 are scanned, see SCANNED_ROCKS)
    ('rock13', -3.0, -1.15, 0.7, 150, 0.36, -5, 2400),    # rock_07, primary, rear left
    ('rock11', -1.4, -0.95, 0.6, 35, 0.38, 6, 2400),      # boulder_01, primary, centre-left
    ('rock10', -1.95, 0.12, 0.36, -40, 0.42, 3, 1300),    # rock_09, front secondary
    ('rock09', -3.05, 0.05, 0.34, 70, 0.42, -8, 1300),    # rock_09, front left
    ('rock12', -0.7, 0.1, 0.22, 10, 0.42, 6, 700),        # transition toward the centre
    ('rock08', -2.6, 0.62, 0.16, 120, 0.42, 0, 600),      # transition, front
    ('rock12', -3.5, -0.7, 0.26, 40, 0.45, 8, 600), ('rock08', -2.75, -0.45, 0.16, 200, 0.45, -6, 500),
    ('rock09', -0.85, -0.7, 0.22, -70, 0.45, 5, 600), ('rock08', -1.9, -0.35, 0.14, 15, 0.45, 10, 450),
    ('rock12', -2.5, 0.38, 0.17, 95, 0.45, -4, 450), ('rock08', -1.3, 0.45, 0.18, 250, 0.45, 6, 450),
    ('rock09', -3.55, 0.2, 0.18, 10, 0.45, -5, 450),
]
# Buried stone trail from the hardscape toward the centre (x, z, scale), shrinking.
TRAIL_STONES = [(-0.3, -0.25, 0.3), (0.15, -0.55, 0.22), (0.55, -0.85, 0.16), (0.9, -1.1, 0.11)]

WOOD = [
    # hero sweep: lower, longer diagonal from lower left into the centre
    ([(-2.45, None, -0.45), (-2.05, -0.6, -0.48), (-1.4, -0.22, -0.58), (-0.6, 0.18, -0.7),
      (0.25, 0.48, -0.82), (1.1, 0.66, -0.92)], 0.125, 0.012),
    # steep rise, a little lower so the pair reads less like antlers
    ([(-2.5, None, -0.55), (-2.3, -0.5, -0.7), (-1.98, 0.1, -0.85), (-1.62, 0.58, -1.0),
      (-1.25, 0.92, -1.1), (-1.05, 1.05, -1.15)], 0.085, 0.012),
    # back left arm, below the icon column
    ([(-2.6, None, -0.7), (-2.85, -0.5, -1.0), (-3.05, 0.05, -1.3), (-3.1, 0.35, -1.5)], 0.06, 0.014),
]
ROOTS = [
    [(-2.45, -1.2, -0.45), (-2.9, None, -0.1), (-3.45, None, 0.2)],
    [(-2.4, -1.2, -0.4), (-2.0, None, 0.0), (-1.6, None, 0.3)],
    [(-2.5, -1.2, -0.5), (-2.85, None, -0.9), (-3.35, None, -1.2)],
    [(-2.35, -1.2, -0.45), (-1.95, None, -0.8), (-1.45, None, -1.15)],
    # surface root running out along the floor toward the centre
    [(-2.3, -1.2, -0.4), (-1.55, None, -0.3), (-0.75, None, -0.45)],
]
HARDSCAPE_FOOTPRINTS = [
    # x, z, radius: soil zone, contact darkening and shoulders
    (-3.0, -1.15, 1.3), (-1.4, -0.95, 1.1), (-1.95, 0.12, 0.8), (-3.05, 0.05, 0.75),
    (-0.7, 0.1, 0.45), (-2.6, 0.62, 0.4), (-2.45, -0.75, 0.9),
    (-0.3, -0.25, 0.32), (0.15, -0.55, 0.26), (0.55, -0.85, 0.2),
]

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
    shoulder_right = 0.08 * gauss2(x, z, -0.5, -0.55, 1.2, 0.8)
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
    # organic edge: broad tongues plus finer fraying
    edge = (0.38 * vnoise(x * 0.8, z * 1.1, 33) + 0.24 * vnoise(x * 1.6, z * 1.6, 31)
            + 0.12 * vnoise(x * 3.7, z * 3.7, 32))
    return smoothstep(0.3, 0.6, near + edge)


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
    # one primary mass in front of the rock/root base
    # (in front of the flat front stones so it hides their bases, never on them)
    (-2.35, 0.9, 1.15), (-1.95, 0.72, 1.1), (-2.85, 0.82, 1.05), (-2.15, 0.35, 0.95),
    (-1.6, 0.62, 0.95), (-3.3, 0.55, 1.0), (-2.6, 1.0, 0.85), (-1.75, 0.3, 0.85),
    # fewer, smaller seams behind (dark gaps between them)
    (-2.2, -0.28, 0.85), (-2.8, -0.42, 0.8), (-1.0, -0.45, 0.75), (-3.4, -0.55, 0.75),
    # transition group 1: against the transition stone, in front of the boulder
    (-0.85, 0.42, 0.7), (-0.5, 0.35, 0.6),
    # transition group 2: small, beside the head of the stone trail
    (0.0, -0.3, 0.55),
]
LEAF_GAP_SEED = 20260925
LEAF_KEEP_FROM = len(LEAF_SPOTS) - 3   # transition groups are never gapped
