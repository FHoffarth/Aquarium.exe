"""Build the Slice C runtime environment: the approved Natural Environment
vocabulary (docs/natural-env-candidate-report.md) translated for the
real-time habitat.

Run headless (Blender 5.2 LTS), after the sources are fetched and
leaf_atlas_profiles.py has run:
  blender -b --factory-startup -P art/tools/build_slice_c.py

Output: habitat/assets/slice-c/environment.glb (geometry only; materials are
assigned at runtime by mesh name).

Vocabulary (locked): scanned Poly Haven rock family, the Composition B root
(Slice B's procedural port, unchanged gestures) for the willow bark, and
LeafSet022 broad-leaf clusters. No moss, no background plants, no carpet.
Geometry helpers are shared with build_slice_b.py; Slice C's terrain and
composition come from slice_c_layout.py.
"""

import json
import math
import pathlib
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_slice_b as SB  # noqa: E402
import slice_c_layout as C  # noqa: E402

# Shared helpers read the terrain and composition through SB.L.
SB.L = C
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'habitat' / 'assets' / 'slice-c' / 'environment.glb'
WORK = ROOT / 'art' / 'work' / 'slice-c'
PROFILES = ROOT / 'art' / 'work' / 'stage2' / 'leaf_profiles.json'
RNG = random.Random(20260925)
# Composition study: blender ... -- --variant A|B|C writes art/work/slice-c/variants/
VARIANT = sys.argv[sys.argv.index('--variant') + 1] if '--variant' in sys.argv else 'base'
B = SB.B


def log(message):
    print(f'[slice-c] {message}', flush=True)

# Triangle targets for the scanned rocks (source: 27.8k / 124k / 23.3k faces).
SCAN_TARGETS = {'rock_07': 3600, 'boulder_01': 5200, 'rock_09': 1900}
LEAF_ROWS = 8                    # profile rows kept per leaf (source has 15)


def rename(obj, name):
    obj.name = name
    obj.data.name = name
    return obj


# ==========================================================================
# Hardscape
# ==========================================================================

def build_rocks():
    """Scanned hero rocks (own UVs and materials at runtime, one mesh each)
    plus rock_moss_set_02 secondaries, transition stones and partly buried
    fragments (one mesh)."""
    groups = {}
    scanned_sources = {}
    for index, (asset_id, target) in C.SCANNED_ROCKS.items():
        if asset_id not in scanned_sources:
            parts = list(SB.import_asset(asset_id).values())
            source = SB.join(parts, f'src-{asset_id}') if len(parts) > 1 else parts[0]
            height = SB.recenter_on_base(source)
            # glTF import splits vertices along UV seams; merged (UVs stay per
            # corner), the collapse can reach the target on dense scans.
            welded = bmesh.new()
            welded.from_mesh(source.data)
            bmesh.ops.remove_doubles(welded, verts=welded.verts, dist=1e-5)
            welded.to_mesh(source.data)
            welded.free()
            for _ in range(4):        # one collapse pass can stall on dense scans
                SB.decimate(source, SCAN_TARGETS[asset_id])
                if SB.triangle_count(source) <= SCAN_TARGETS[asset_id] * 1.05:
                    break
            scanned_sources[asset_id] = (source, height)
        source, height = scanned_sources[asset_id]
        _, x, z, _, yaw, sink, tilt, _ = C.ROCKS[index]
        rock = SB.duplicate(source, f'scan-{index}')
        scale = target / height
        rock.data.transform(Matrix.Translation(B(x, C.surface_y(x, z) - (sink + C.SCANNED_SINK_BONUS) * target, z))
                            @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
                            @ Matrix.Rotation(math.radians(tilt), 4, 'X')
                            @ Matrix.Scale(scale, 4))
        groups.setdefault(asset_id, []).append(rock)
    # Composition study C (reference: framed valley): a second, smaller
    # hardscape mass on the right from duplicates of the same scans.
    for index, (asset_id, x, z, target, yaw, sink, tilt) in enumerate(VARIANT_ROCKS.get(VARIANT, [])):
        source, height = scanned_sources[asset_id]
        rock = SB.duplicate(source, f'variant-{index}')
        rock.data.transform(Matrix.Translation(B(x, C.surface_y(x, z) - sink * target, z))
                            @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
                            @ Matrix.Rotation(math.radians(tilt), 4, 'X')
                            @ Matrix.Scale(target / height, 4))
        groups[asset_id].append(rock)
    for source, _ in scanned_sources.values():
        bpy.data.objects.remove(source)

    sources = SB.import_asset('rock_moss_set_02')
    heights = {name: SB.recenter_on_base(obj) for name, obj in sources.items()}
    stones = []
    for index, (key, x, z, scale, yaw, sink, tilt, target) in enumerate(C.ROCKS):
        if index in C.SCANNED_ROCKS:
            continue
        name = f'rock_moss_set_02_{key}'
        rock = SB.duplicate(sources[name], f'stone-{index}')
        SB.decimate(rock, target)
        scale *= C.ROCK_SCALE
        height = heights[name] * scale
        rock.data.transform(Matrix.Translation(B(x, C.surface_y(x, z) - (sink + 0.05) * height, z))
                            @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
                            @ Matrix.Rotation(math.radians(tilt), 4, 'X')
                            @ Matrix.Scale(scale, 4))
        stones.append(rock)
    # Transition stones only where they connect to the hardscape (not
    # scattered across the open sand), then partly buried fragments at the
    # hardscape base: big enough to read at 1920x1080 (>= ~8 px).
    fragment = sources['rock_moss_set_02_rock08']
    fragment_height = heights['rock_moss_set_02_rock08']
    placements = [(x, z, s, 0.5) for x, z, s in C.TRAIL_STONES]
    rng = random.Random(5150)
    primaries = C.HARDSCAPE_FOOTPRINTS[:4]
    while len(placements) < 30:
        hx, hz, radius = rng.choice(primaries)
        angle = rng.uniform(0, math.tau)
        distance = radius * rng.uniform(0.7, 1.15)
        x, z = hx + math.cos(angle) * distance, hz + math.sin(angle) * distance * 0.75
        if z > 1.0 or x > -0.6:
            continue
        placements.append((x, z, rng.uniform(0.07, 0.16), rng.uniform(0.45, 0.65)))
    for index, (x, z, scale, sink) in enumerate(placements):
        stone = SB.duplicate(fragment, f'fragment-{index}')
        SB.decimate(stone, 110)
        height = fragment_height * scale
        stone.data.transform(Matrix.Translation(B(x, C.surface_y(x, z) - sink * height, z))
                             @ Matrix.Rotation(rng.uniform(0, math.tau), 4, 'Z')
                             @ Matrix.Rotation(math.radians(rng.uniform(-25, 25)), 4, 'X')
                             @ Matrix.Scale(scale, 4))
        stones.append(stone)
    for obj in sources.values():
        bpy.data.objects.remove(obj)

    meshes = {
        'rock_07': rename(SB.join(groups['rock_07'], 'slice-c-rock-07'), 'slice-c-rock-07'),
        'boulder_01': rename(SB.join(groups['boulder_01'], 'slice-c-boulder'), 'slice-c-boulder'),
        'rock_09': rename(SB.join(groups['rock_09'], 'slice-c-rock-09'), 'slice-c-rock-09'),
        'stones': rename(SB.join(stones, 'slice-c-stones'), 'slice-c-stones'),
    }
    for obj in meshes.values():
        scan_color = scan_vertex_color(obj)
        SB.set_contact_color(obj, reach=0.4)
        if scan_color is not None:
            # glTF COLOR_0 multiplies the base colour (rock_07 carries its
            # own tone there): keep it under the contact shading.
            for item, factor in zip(obj.data.color_attributes['Col'].data, scan_color):
                item.color = tuple(c * f for c, f in zip(item.color[:3], factor)) + (1.0,)
        log(f'{obj.name}: {SB.triangle_count(obj)} triangles'
            + (' (scan vertex colour kept)' if scan_color is not None else ''))
    return list(meshes.values())


def scan_vertex_color(obj):
    """Per-vertex average of a scan's own colour attribute, if it has one."""
    mesh = obj.data
    source = next((a for a in mesh.color_attributes if a.name != 'Col'), None)
    if source is None:
        return None
    sums = [[0.0, 0.0, 0.0, 0] for _ in mesh.vertices]
    if source.domain == 'POINT':
        for index, item in enumerate(source.data):
            sums[index] = [*item.color[:3], 1]
    else:
        for loop, item in zip(mesh.loops, source.data):
            acc = sums[loop.vertex_index]
            for k in range(3):
                acc[k] += item.color[k]
            acc[3] += 1
    result = [tuple(v / max(1, acc[3]) for v in acc[:3]) for acc in sums]
    mesh.color_attributes.remove(source)
    return result


def build_wood():
    wood = rename(SB.build_wood(), 'slice-c-wood')
    log(f'wood (Composition B root): {SB.triangle_count(wood)} triangles')
    return wood


# ==========================================================================
# LeafSet022 broad-leaf clusters
# ==========================================================================

def photo_leaf(bm, uv_layer, col, profile, base, direction, face_hint, length, arch, fold, twist, curl, shade,
               rows_kept=None, tint=(1.0, 1.0, 1.0)):
    """One photographed leaf as a tight strip following the photo's own
    outline (left/centre/right per row), so alpha exists only at the rim."""
    direction = direction.normalized()
    side = direction.cross(face_hint)
    if side.length < 1e-5:
        side = direction.orthogonal()
    side.normalize()
    up = side.cross(direction).normalized()
    rows = profile['rows']
    kept = rows_kept or LEAF_ROWS
    step = (len(rows) - 1) / (kept - 1)
    picked = [rows[round(i * step)] for i in range(kept)]
    grid = []
    for row in picked:
        t = row['t']
        half = row['half_width'] * length
        rot = twist * t
        side_t = side * math.cos(rot) + up * math.sin(rot)
        up_t = up * math.cos(rot) - side * math.sin(rot)
        centre = base + direction * (length * t) + up * (-arch * length * t * t) + side * (curl * length * t * t)
        verts = [bm.verts.new(centre - side_t * half + up_t * (half * fold)),
                 bm.verts.new(centre),
                 bm.verts.new(centre + side_t * half + up_t * (half * fold))]
        # Dark internal gaps: the leaf base (inside the cluster) is shaded.
        tone = shade * (0.5 + 0.5 * C.smoothstep(0.0, 0.55, t))
        grid.append((verts, (row['left'], row['centre'], row['right']), tone))
    for (a, ua, ta), (b, ub, tb) in zip(grid, grid[1:]):
        for c in range(2):
            face = bm.faces.new((a[c], a[c + 1], b[c + 1], b[c]))
            for loop, uvc, tone in zip(face.loops, (ua[c], ua[c + 1], ub[c + 1], ub[c]), (ta, ta, tb, tb)):
                loop[uv_layer].uv = uvc
                loop[col] = (tone * 0.95 * tint[0], tone * tint[1], tone * 0.93 * tint[2], 1.0)


def build_leaves(rocks, wood):
    profiles = json.loads(PROFILES.read_text())['LeafSet022']
    rng = random.Random(C.LEAF_GAP_SEED)
    camera = B(*C.CAMERA)
    up = Vector((0, 0, 1))
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new('UVMap')
    col = bm.loops.layers.float_color.new('Col')
    count = 0

    def rosette(base, scale, leaves=None, spread=1.0):
        nonlocal count
        for _ in range(leaves or rng.randint(8, 11)):
            profile = rng.choice(profiles)
            outer = rng.random() ** 0.7                 # size hierarchy: inner small, outer large
            azimuth = rng.uniform(0, math.tau)
            out = Vector((math.cos(azimuth), math.sin(azimuth), 0))
            start = base + (out * spread * (0.3 + 0.7 * outer) + up * 0.8).normalized() * (0.03 + 0.07 * outer) * scale
            direction = (out * (0.35 + 0.55 * outer) + up * (1.0 - 0.45 * outer)
                         + Vector((rng.gauss(0, 0.15), rng.gauss(0, 0.15), 0))).normalized()
            length = (0.2 + 0.26 * outer) * scale * rng.uniform(0.85, 1.15)
            # Camera-specific cluster: leaf planes lean toward the fixed view
            # so they read as leaves, not edge-on slivers.
            view = (camera - start).normalized()
            face = (up + view * rng.uniform(0.6, 1.4)).normalized()
            photo_leaf(bm, uv_layer, col, profile, start, direction, face, length,
                       arch=rng.uniform(0.1, 0.35), fold=rng.uniform(0.05, 0.22), twist=rng.uniform(-0.5, 0.5),
                       curl=rng.uniform(-0.08, 0.08), shade=rng.uniform(0.62, 1.0))
            count += 1

    for index, (x, z, scale) in enumerate(C.LEAF_SPOTS):
        if rng.random() < 0.12 and index < C.LEAF_KEEP_FROM:
            continue                                     # a believable gap
        for _ in range(rng.choice((2, 3, 3))):
            bx, bz = x + rng.gauss(0, 0.11), z + rng.gauss(0, 0.07)
            rosette(B(bx, C.surface_y(bx, bz) - 0.015, bz), scale * rng.uniform(0.8, 1.2))
    # Seams: where the root meets the floor or stone (low joints only).
    for joint in SB.JOINTS:
        if joint.z < C.FLOOR + 0.55:
            rosette(joint + Vector((0, 0, 0.02)), rng.uniform(0.5, 0.7), leaves=rng.randint(5, 8), spread=1.3)
    # Rock/substrate seams: low points on the scanned rocks' flanks.
    tree_points = SB.sample_surfaces(rocks[:3], 5, lambda p: 1.0 if p.z < C.surface_y(p.x, -p.y) + 0.12 else 0.0,
                                     min_up=0.1)
    for point, _ in tree_points:
        rosette(point, rng.uniform(0.55, 0.8), leaves=rng.randint(5, 8), spread=1.2)
    if VARIANT != 'base':
        count += add_composition_variant(bm, uv_layer, col, profiles, rng, rosette)
    bm.normal_update()
    leaves = SB.mesh_object('slice-c-leaves', bm)
    leaves.data.color_attributes.active_color = leaves.data.color_attributes['Col']
    SB.set_sway_by_height(leaves, scale=0.6, exponent=1.3)
    log(f'leaves: {count} photographed leaves, {SB.triangle_count(leaves)} triangles')
    return leaves


# ==========================================================================
# Composition study variants (A/B/C): planted masses from the same LeafSet022
# leaves at three scales. Tall background stems (small leaf pairs along
# stems), medium broad-leaf rosettes, low foreground groups. All in the one
# leaf mesh / material, so draw calls do not change.
# ==========================================================================

GREEN, OLIVE, RED, LIGHT, DARK = (1.0, 1.0, 1.0), (1.12, 1.0, 0.7), (1.45, 0.72, 0.58), (0.92, 1.18, 0.88), (0.7, 0.8, 0.76)

# Variant C right hardscape: source, x, z, target height, yaw, sink, tilt
VARIANT_ROCKS = {
    'C': [('boulder_01', 3.7, -1.15, 1.25, 205, 0.36, 4), ('rock_07', 4.4, -0.25, 1.0, 60, 0.4, -4),
          ('rock_09', 2.9, 0.1, 0.5, 15, 0.42, 3), ('rock_09', 2.55, -0.85, 0.55, 130, 0.42, -6)],
}
# Tall background clumps: x, z, spread, height, stems, tint
VARIANT_STEMS = {
    'A': [(-4.3, -1.9, 0.3, 2.3, 12, GREEN), (-3.6, -1.7, 0.3, 2.6, 14, OLIVE), (-2.9, -2.05, 0.35, 2.4, 14, GREEN),
          (-2.2, -1.8, 0.3, 2.0, 12, RED), (-1.5, -2.1, 0.3, 1.8, 11, LIGHT), (-0.9, -1.8, 0.25, 1.3, 9, GREEN),
          (-0.3, -2.2, 0.25, 0.9, 7, DARK)],
    'B': [(-4.3, -1.9, 0.3, 2.2, 12, GREEN), (-3.5, -1.8, 0.3, 2.4, 13, OLIVE), (-2.7, -2.05, 0.3, 2.0, 12, RED),
          (-1.9, -1.9, 0.28, 1.5, 9, LIGHT),
          (4.4, -1.8, 0.3, 2.3, 13, GREEN), (3.7, -2.05, 0.3, 1.9, 12, RED), (3.1, -1.7, 0.3, 1.4, 10, LIGHT),
          (4.0, -1.2, 0.25, 1.1, 8, OLIVE)],
    'C': [(-4.4, -1.9, 0.3, 2.6, 14, GREEN), (-3.7, -2.1, 0.3, 2.4, 13, OLIVE), (-3.0, -1.8, 0.3, 2.1, 12, RED),
          (-2.3, -2.2, 0.3, 1.9, 12, GREEN), (-1.6, -1.9, 0.28, 1.5, 10, LIGHT), (-0.9, -2.15, 0.25, 1.15, 9, OLIVE),
          (-0.2, -1.9, 0.25, 0.8, 7, GREEN), (0.6, -2.2, 0.22, 0.6, 5, DARK), (1.5, -2.0, 0.25, 0.8, 6, LIGHT),
          (2.4, -2.2, 0.28, 1.4, 9, GREEN), (3.2, -2.0, 0.3, 2.0, 11, RED), (3.9, -2.2, 0.3, 2.3, 12, OLIVE),
          (4.6, -1.9, 0.3, 2.5, 13, GREEN)],
}
# Extra medium broad-leaf rosettes: x, z, scale
VARIANT_MID = {
    'A': [(-3.7, 0.85, 0.9), (-3.95, 0.2, 0.95), (-1.2, 0.9, 0.8), (-3.3, -1.45, 1.0), (-2.4, -1.5, 0.95),
          (-1.6, -1.45, 0.9)],
    'B': [(-3.7, 0.85, 0.9), (-3.3, -1.45, 1.0), (-2.4, -1.5, 0.9),
          (3.4, 0.2, 1.0), (3.0, 0.6, 0.9), (3.8, 0.5, 0.95), (2.6, 0.95, 0.7), (3.5, -0.8, 0.95)],
    'C': [(-3.7, 0.85, 0.9), (-3.3, -1.45, 1.0), (-2.4, -1.5, 0.95), (-1.6, -1.45, 0.85),
          (3.2, 0.45, 1.0), (2.5, 0.55, 0.85), (3.9, 0.55, 0.95), (3.1, -0.45, 0.9), (2.3, -0.4, 0.8),
          (4.2, -0.85, 0.95), (3.3, -1.5, 0.9)],
}
# Low foreground groups: x, z, radius x, radius z, rosettes
VARIANT_LOW = {
    'A': [(-3.2, 1.3, 0.5, 0.25, 6), (-2.2, 1.45, 0.5, 0.2, 5), (-1.1, 1.25, 0.4, 0.2, 4), (-0.3, 1.0, 0.3, 0.15, 3)],
    'B': [(-3.2, 1.3, 0.5, 0.25, 5), (-2.1, 1.45, 0.4, 0.2, 4), (2.6, 1.3, 0.4, 0.2, 4), (3.4, 1.15, 0.5, 0.25, 5)],
    'C': [(-3.3, 1.3, 0.5, 0.25, 6), (-2.3, 1.45, 0.45, 0.2, 5), (-1.4, 1.3, 0.35, 0.18, 4), (2.2, 1.3, 0.35, 0.18, 4),
          (3.0, 1.1, 0.45, 0.22, 5), (3.7, 1.4, 0.4, 0.2, 4), (1.8, -0.6, 0.3, 0.15, 3)],
}


def add_composition_variant(bm, uv_layer, col, profiles, rng, rosette):
    camera = B(*C.CAMERA)
    up = Vector((0, 0, 1))
    count = 0
    for cx, cz, spread, height, stems, tint in VARIANT_STEMS[VARIANT]:
        cz += 0.45                                       # closer: readable masses, less haze
        phase0 = rng.uniform(0, math.tau)
        for _ in range(int(stems * 1.3)):
            x, z = cx + rng.gauss(0, spread), cz + rng.gauss(0, spread * 0.6)
            dome = 1.0 - 0.35 * min(1.0, math.hypot(x - cx, z - cz) / (spread * 2))
            h = height * rng.uniform(0.72, 1.05) * dome
            position = B(x, C.surface_y(x, z) - 0.03, z)
            direction = Vector((rng.gauss(0.03, 0.07), rng.gauss(0, 0.05), 1.0)).normalized()
            steps = max(5, int(h / 0.1))
            phase = phase0 + rng.uniform(-0.6, 0.6)
            shade_stem = rng.uniform(0.7, 1.05)
            for k in range(steps):
                t = k / steps
                position = position + direction * (h / steps)
                direction = (direction + Vector((rng.gauss(0, 0.035), rng.gauss(0, 0.035), 0))).normalized()
                if t < 0.12:
                    continue                             # bare lower stem
                length = rng.uniform(0.13, 0.2) * (1.0 - 0.35 * t)
                view = (camera - position).normalized()
                face = (up + view).normalized()
                angle = phase + k * math.pi / 2          # opposite pairs, alternating
                for side in (0.0, math.pi):
                    out = Vector((math.cos(angle + side), math.sin(angle + side), 0))
                    photo_leaf(bm, uv_layer, col, rng.choice(profiles), position,
                               (out * 0.9 + up * (0.35 + 0.4 * t)).normalized(), face, length,
                               arch=0.15, fold=0.1, twist=rng.uniform(-0.4, 0.4), curl=0.0,
                               shade=shade_stem * (0.6 + 0.5 * t), rows_kept=4, tint=tint)
                    count += 1
    for x, z, scale in VARIANT_MID[VARIANT]:
        for _ in range(rng.choice((2, 3))):
            bx, bz = x + rng.gauss(0, 0.12), z + rng.gauss(0, 0.08)
            rosette(B(bx, C.surface_y(bx, bz) - 0.015, bz), scale * rng.uniform(0.8, 1.15))
    for cx, cz, rx, rz, n in VARIANT_LOW[VARIANT]:
        for _ in range(n):
            bx, bz = cx + rng.gauss(0, rx * 0.5), cz + rng.gauss(0, rz * 0.5)
            rosette(B(bx, C.surface_y(bx, bz) - 0.01, bz), rng.uniform(0.32, 0.5), leaves=rng.randint(5, 7), spread=1.4)
    log(f'variant {VARIANT}: {count} stem leaves added (plus mid/low rosettes)')
    return count


# ==========================================================================
# Substrate
# ==========================================================================

def build_substrate():
    substrate = rename(SB.build_substrate(columns=96, rows=44), 'slice-c-substrate')
    return substrate


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    WORK.mkdir(parents=True, exist_ok=True)
    rocks = build_rocks()
    wood = build_wood()
    leaves = build_leaves(rocks, wood)
    substrate = build_substrate()
    objects = rocks + [wood, leaves, substrate]
    total = sum(SB.triangle_count(obj) for obj in objects)
    log(f'total triangles: {total}')
    if VARIANT == 'base':
        bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'slice-c.blend'))
        SB.OUT = OUT
    else:
        SB.OUT = WORK / 'variants' / f'environment-{VARIANT}.glb'
    SB.export(objects)


if __name__ == '__main__':
    main()
