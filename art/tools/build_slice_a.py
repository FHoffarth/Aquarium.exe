"""Build the North-Star Slice A environment geometry from approved CC0 sources.

Run headless (Blender 5.2 LTS):
  blender -b --factory-startup -P art/tools/build_slice_a.py

Inputs:  art/source/polyhaven/<asset>/ (fetched by fetch_sources.py)
Outputs: habitat/assets/slice-a/environment.glb   geometry only, no materials
         art/work/slice-a/                         bake inputs for prepare_textures.py

Coordinates below are habitat units (x right, y up, z toward camera; floor
y = -1.45; 1 unit ~ 10 cm, so the tank reads as a 60 cm aquascape).
Materials are assigned at runtime by mesh name; this script only ships
geometry, UVs (plant/card UVs already remapped into atlas tiles), a COLOR_0
contact-occlusion term for hardscape, and a _SWAY weight for vegetation.
"""

import bisect
import itertools
import math
import pathlib
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'art' / 'source' / 'polyhaven'
WORK = ROOT / 'art' / 'work' / 'slice-a'
OUT = ROOT / 'habitat' / 'assets' / 'slice-a' / 'environment.glb'
FLOOR = -1.45
RNG = random.Random(20260922)

# --------------------------------------------------------------------------
# Hand-authored composition (habitat coordinates).
# Left-low mass, hero diagonal, center transition, open upper/right water,
# calm top-left icon region (no hardscape above y ~ 0.15 left of x ~ -0.8).
# --------------------------------------------------------------------------
ROCKS = [
    # source rock, x, z, scale, yaw(deg), sink(fraction of height)
    # Tall hardscape sits behind the fish swim volume (z -0.65..0.65): the
    # simulation has no obstacle avoidance, so fish must pass in front of it.
    ('rock_moss_set_02_rock11', -2.75, -0.95, 0.85, 35, 0.2),    # group A anchor (rear)
    ('rock_moss_set_02_rock10', -3.45, -0.7, 0.64, 140, 0.25),   # A left, overlapping anchor
    ('rock_moss_set_02_rock09', -1.85, 0.25, 0.6, -35, 0.22),    # A front-right
    ('rock_moss_set_02_rock08', -0.55, 0.45, 0.4, 60, 0.2),      # B transition
    ('rock_moss_set_02_rock12', -0.1, 0.12, 0.27, -20, 0.22),    # B small
    ('rock_moss_set_02_rock07', 2.35, -0.5, 0.48, 200, 0.22),    # right accent
]
ROCK_TRIANGLES = 2600
PEBBLES = [
    # x, z, scale  (small rock08 copies half-sunk around the groups)
    (-1.2, 0.72, 0.07), (-0.95, 0.9, 0.05), (-0.25, 0.8, 0.06), (0.2, 0.6, 0.045),
    (0.45, 0.95, 0.05), (-1.75, 0.95, 0.055), (1.95, 0.25, 0.06), (2.7, 0.05, 0.05),
    (2.1, -0.05, 0.04), (-2.6, 0.55, 0.06), (0.9, 1.1, 0.04), (-0.7, 1.2, 0.05),
]
PEBBLE_TRIANGLES = 180

# Hero wood: kitbashed branches; base buried behind group A, rising to a
# tip around x -0.9, y 0.1 (below the icon region).
WOOD = [
    # source branch, base x, base z, lean(deg from vertical toward +x),
    # twist(deg about the branch axis), yaw(deg), length scale, girth scale.
    # Girth is thickened radially: the CC0 branches are twig-proportioned and
    # read as dead sticks at hero scale.
    # Long, low-rising sweep: gains length toward the centre rather than
    # height, so the diagonal reads strongly without entering the icon region.
    ('dry_branches_medium_01_a', -2.7, -0.85, 63, 30, -4, 2.45, 2.9),
    ('dry_branches_medium_01_b', -2.35, -0.8, 76, 160, 10, 2.05, 2.7),
    ('dry_branches_medium_01_c', -2.95, -0.95, -36, 80, 10, 1.5, 2.6),
]
WOOD_TRIANGLES = 7500

BROADLEAF = [
    # source plant, x, z, scale, yaw
    ('anthurium_botany_01_a', -1.95, 0.4, 1.7, 20),
    ('anthurium_botany_01_b', -2.75, 0.15, 1.9, -40),
    ('anthurium_botany_01_c', -1.3, 0.6, 1.5, 70),
    ('anthurium_botany_04_d', -3.2, 0.35, 2.0, 10),
    ('anthurium_botany_05_e', -0.95, 0.8, 2.3, -15),
    ('anthurium_botany_06_f', -1.7, 0.95, 2.1, 120),
    ('anthurium_botany_01_c', -3.5, -0.1, 1.6, 200),
    ('anthurium_botany_04_d', -2.35, 0.7, 1.7, 95),
]
BROADLEAF_TRIANGLES = 1500
FERNS = [
    ('fern_02_b', -2.05, -0.6, 2.1, 30),
    ('fern_02_c', -1.2, -0.25, 1.8, -60),
    ('fern_02_a', -3.3, -0.35, 2.4, 90),
    ('fern_02_d', -0.75, -0.05, 2.0, 15),
    ('fern_02_b', -2.8, -0.9, 2.3, 200),
    ('fern_02_c', -1.65, -0.75, 1.9, 150),
]
MOSS_SPRIGS = 520
MOSS_SCALE = (5.0, 8.5)


def log(message):
    print(f'[slice-a] {message}', flush=True)


def to_blender(x, y, z):
    return Vector((x, -z, y))


def import_asset(asset_id):
    before = set(bpy.data.objects)
    gltf = next((SRC / asset_id).glob('*.gltf'))
    bpy.ops.import_scene.gltf(filepath=str(gltf))
    created = sorted((obj for obj in set(bpy.data.objects) - before if obj.type == 'MESH'),
                     key=lambda obj: obj.name)
    objects = {obj.name: obj for obj in created}
    for obj in objects.values():
        bake_transform(obj)
    return objects


def bake_transform(obj):
    matrix = obj.matrix_world.copy()
    obj.parent = None
    obj.data.transform(matrix)
    obj.matrix_world = Matrix.Identity(4)


def recenter_on_base(obj):
    verts = obj.data.vertices
    min_z = min(v.co.z for v in verts)
    cutoff = min_z + 0.08 * (max(v.co.z for v in verts) - min_z)
    base = [v.co for v in verts if v.co.z < cutoff]
    cx = sum(p.x for p in base) / len(base)
    cy = sum(p.y for p in base) / len(base)
    obj.data.transform(Matrix.Translation(Vector((-cx, -cy, -min_z))))


def triangle_count(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def decimate(obj, target):
    count = triangle_count(obj)
    if count <= target:
        return
    modifier = obj.modifiers.new('decimate', 'DECIMATE')
    modifier.ratio = target / count
    modifier.use_collapse_triangulate = True
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
    obj.modifiers.remove(modifier)
    old = obj.data
    obj.data = mesh
    bpy.data.meshes.remove(old)


def duplicate(obj, name):
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = name
    bpy.context.scene.collection.objects.link(copy)
    return copy


def place(obj, x, y, z, yaw_deg, scale, extra=Matrix.Identity(4)):
    matrix = (Matrix.Translation(to_blender(x, y, z))
              @ Matrix.Rotation(math.radians(yaw_deg), 4, 'Z')
              @ extra
              @ Matrix.Scale(scale, 4))
    obj.data.transform(matrix)


def join(objects, name):
    objects = [obj for obj in objects if obj]
    target = objects[0]
    with bpy.context.temp_override(active_object=target, object=target,
                                   selected_editable_objects=objects, selected_objects=objects):
        bpy.ops.object.join()
    target.name = name
    target.data.name = name
    return target


def remap_uvs(obj, offset_u, offset_v, scale_u, scale_v):
    layer = obj.data.uv_layers.active
    for loop in layer.data:
        u, v = loop.uv
        loop.uv = (offset_u + u * scale_u, offset_v + v * scale_v)


def set_point_attribute(obj, name, values):
    mesh = obj.data
    attribute = mesh.attributes.new(name, 'FLOAT', 'POINT')
    attribute.data.foreach_set('value', values)


def set_sway_by_height(obj, base_y, height):
    values = [max(0.0, min(1.0, (v.co.z - base_y) / max(height, 1e-4))) ** 1.5
              for v in obj.data.vertices]
    set_point_attribute(obj, '_SWAY', values)


def set_neutral_color(obj):
    mesh = obj.data
    color = mesh.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
    for item in color.data:
        item.color = (1.0, 1.0, 1.0, 1.0)
    mesh.color_attributes.active_color = color


# --------------------------------------------------------------------------
# Hardscape
# --------------------------------------------------------------------------

def build_rocks():
    sources = import_asset('rock_moss_set_02')
    for obj in sources.values():
        recenter_on_base(obj)
    parts = []
    for name, x, z, scale, yaw, sink in ROCKS:
        rock = duplicate(sources[name], f'rock-{name[-6:]}')
        decimate(rock, ROCK_TRIANGLES)
        height = max(v.co.z for v in rock.data.vertices) * scale
        place(rock, x, surface_y(x, z) - sink * height, z, yaw, scale)
        parts.append(rock)
    pebble_source = sources['rock_moss_set_02_rock08']
    for index, (x, z, scale) in enumerate(PEBBLES):
        pebble = duplicate(pebble_source, f'pebble-{index}')
        decimate(pebble, PEBBLE_TRIANGLES)
        tilt = Matrix.Rotation(math.radians(RNG.uniform(-25, 25)), 4, 'X')
        height = max(v.co.z for v in pebble.data.vertices) * scale
        place(pebble, x, surface_y(x, z) - 0.35 * height, z, RNG.uniform(0, 360), scale, tilt)
        parts.append(pebble)
    for obj in sources.values():
        bpy.data.objects.remove(obj)
    rocks = join(parts, 'slice-a-rocks')
    set_neutral_color(rocks)
    log(f'rocks: {triangle_count(rocks)} triangles')
    return rocks


def branch_upright(obj):
    """Rotate a lying branch so its long axis is +Z with the thick end at the origin."""
    verts = [v.co.copy() for v in obj.data.vertices]
    extents = [max(p[i] for p in verts) - min(p[i] for p in verts) for i in range(3)]
    axis = 0 if extents[0] >= extents[1] else 1
    lo = min(p[axis] for p in verts)
    hi = max(p[axis] for p in verts)
    span = hi - lo

    def end_width(selector):
        pts = [p for p in verts if selector(p[axis])]
        other = 1 - axis
        return (max(p[other] for p in pts) - min(p[other] for p in pts)
                + max(p.z for p in pts) - min(p.z for p in pts))

    low_thick = end_width(lambda c: c < lo + 0.1 * span) >= end_width(lambda c: c > hi - 0.1 * span)
    base = lo if low_thick else hi
    base_pts = [p for p in verts if abs(p[axis] - base) < 0.06 * span]
    centre = sum(base_pts, Vector()) / len(base_pts)
    obj.data.transform(Matrix.Translation(-centre))
    direction = Vector((0, 0, 0))
    direction[axis] = 1.0 if low_thick else -1.0
    rotation = direction.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
    obj.data.transform(rotation)
    return span


def build_wood():
    sources = import_asset('dry_branches_medium_01')
    parts = []
    for name, x, z, lean, twist, yaw, scale, girth in WOOD:
        branch = duplicate(sources[name], f'wood-{name[-1]}')
        branch_upright(branch)
        branch.data.transform(Matrix.Diagonal((girth, girth, 1.0, 1.0)))
        pose = (Matrix.Rotation(math.radians(lean), 4, 'Y')
                @ Matrix.Rotation(math.radians(twist), 4, 'Z'))
        place(branch, x, surface_y(x, z) - 0.12, z, yaw, scale, pose)
        parts.append(branch)
    for obj in sources.values():
        bpy.data.objects.remove(obj)
    wood = join(parts, 'slice-a-wood')
    decimate(wood, WOOD_TRIANGLES)
    set_neutral_color(wood)
    log(f'wood: {triangle_count(wood)} triangles')
    return wood


# --------------------------------------------------------------------------
# Moss: real CC0 moss sprigs scattered on up-facing wood/rock surfaces.
# --------------------------------------------------------------------------

def surface_samples(objects, count, min_up=0.35):
    triangles = []
    for obj in objects:
        mesh = obj.data
        mesh.calc_loop_triangles()
        for tri in mesh.loop_triangles:
            normal = tri.normal
            if normal.z < min_up:
                continue
            a, b, c = (mesh.vertices[i].co for i in tri.vertices)
            weight = tri.area * (normal.z ** 2)
            triangles.append((weight, a, b, c, normal.copy()))
    cumulative = list(itertools.accumulate(t[0] for t in triangles))
    samples = []
    for _ in range(count):
        index = bisect.bisect_left(cumulative, RNG.uniform(0, cumulative[-1]))
        _, a, b, c, normal = triangles[min(index, len(triangles) - 1)]
        r1, r2 = RNG.random(), RNG.random()
        if r1 + r2 > 1:
            r1, r2 = 1 - r1, 1 - r2
        samples.append((a + (b - a) * r1 + (c - a) * r2, normal))
    return samples


def build_moss(hosts):
    sources = list(import_asset('moss_01').values())
    for obj in sources:
        recenter_on_base(obj)
    parts = []
    for index, (point, normal) in enumerate(surface_samples(hosts, MOSS_SPRIGS)):
        sprig = duplicate(RNG.choice(sources), f'moss-{index}')
        align = Vector((0, 0, 1)).rotation_difference(normal.lerp(Vector((0, 0, 1)), 0.4))
        matrix = (Matrix.Translation(point - normal * 0.01)
                  @ align.to_matrix().to_4x4()
                  @ Matrix.Rotation(RNG.uniform(0, math.tau), 4, 'Z')
                  @ Matrix.Scale(RNG.uniform(*MOSS_SCALE), 4))
        sprig.data.transform(matrix)
        parts.append(sprig)
    for obj in sources:
        bpy.data.objects.remove(obj)
    moss = join(parts, 'slice-a-moss')
    set_point_attribute(moss, '_SWAY', [0.15] * len(moss.data.vertices))
    log(f'moss: {triangle_count(moss)} triangles from {MOSS_SPRIGS} sprigs')
    return moss


# --------------------------------------------------------------------------
# Mesh vegetation: broad-leaf + fern, UVs packed into a 2x1 atlas
# (broad-leaf left half, fern right half).
# --------------------------------------------------------------------------

def build_plants():
    broad = import_asset('anthurium_botany_01')
    ferns = import_asset('fern_02')
    parts = []
    for table, sources, atlas_u, target in ((BROADLEAF, broad, 0.0, BROADLEAF_TRIANGLES),
                                            (FERNS, ferns, 0.5, None)):
        for obj in sources.values():
            recenter_on_base(obj)
        for name, x, z, scale, yaw in table:
            plant = duplicate(sources[name], f'plant-{name}')
            if target:
                decimate(plant, target)
            remap_uvs(plant, atlas_u, 0.0, 0.5, 1.0)
            height = max(v.co.z for v in plant.data.vertices)
            set_sway_by_height(plant, 0.0, height)
            place(plant, x, surface_y(x, z) - 0.03, z, yaw, scale)
            parts.append(plant)
        for obj in sources.values():
            bpy.data.objects.remove(obj)
    plants = join(parts, 'slice-a-plants')
    log(f'plants: {triangle_count(plants)} triangles')
    return plants


# --------------------------------------------------------------------------
# Card vegetation: camera-facing quads (the habitat camera is fixed), UVs in
# the card atlas. Tiles are rendered by render_cards.py from the same view.
# --------------------------------------------------------------------------

CAMERA = (0.0, 0.06, 6.2)
CARD_ATLAS = (2048, 1024)
CARD_TILES = {
    'carpet_0': (0, 0, 512, 256), 'carpet_1': (512, 0, 512, 256),
    'carpet_2': (0, 256, 512, 256), 'carpet_3': (512, 256, 512, 256),
    'stem_0': (1024, 0, 512, 1024), 'stem_1': (1536, 0, 512, 1024),
}
# zone: (x range, z range, count, width range, kind)
CARPET_ZONES = [
    ((-3.7, -1.0), (0.35, 1.5), 46, (0.55, 0.85)),
    ((-1.0, -0.4), (0.75, 1.35), 8, (0.45, 0.65)),
    ((1.3, 3.4), (0.0, 1.2), 16, (0.5, 0.7)),
]
STEM_ZONES = [
    # x range, z range, count, height range (left heights keep the icon region calm)
    ((-3.9, -1.9), (-1.0, -0.65), 12, (0.85, 1.15)),
    ((2.0, 3.9), (-1.0, -0.6), 14, (1.0, 1.55)),
    ((1.3, 2.0), (-0.9, -0.6), 3, (0.7, 0.95)),
]
CARPET_SINK = 0.3      # fraction of card height below the surface (hides stalks)
STEM_SINK = 0.04


def tile_uv(name, mirror=False):
    x, y, w, h = CARD_TILES[name]
    u0, u1 = x / CARD_ATLAS[0], (x + w) / CARD_ATLAS[0]
    v_top, v_bottom = 1 - y / CARD_ATLAS[1], 1 - (y + h) / CARD_ATLAS[1]
    if mirror:
        u0, u1 = u1, u0
    return u0, u1, v_bottom, v_top


def build_cards():
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new('UVMap')
    sway_values = []
    normals = []

    def add_card(x, z, width, height, sink, tile, mirror, sway_top):
        base = surface_y(x, z) - sink * height
        dx, dz = CAMERA[0] - x, CAMERA[2] - z
        length = math.hypot(dx, dz)
        dx, dz = dx / length, dz / length
        right = (dz, -dx)                 # habitat XZ, perpendicular to view
        u0, u1, v0, v1 = tile_uv(tile, mirror)
        corners = [
            (x - right[0] * width / 2, base, z - right[1] * width / 2, u0, v0, 0.0),
            (x + right[0] * width / 2, base, z + right[1] * width / 2, u1, v0, 0.0),
            (x + right[0] * width / 2, base + height, z + right[1] * width / 2, u1, v1, sway_top),
            (x - right[0] * width / 2, base + height, z - right[1] * width / 2, u0, v1, sway_top),
        ]
        verts = [bm.verts.new(to_blender(cx, cy, cz)) for cx, cy, cz, *_ in corners]
        face = bm.faces.new(verts)
        for loop, (*_, u, v, _sway) in zip(face.loops, corners):
            loop[uv_layer].uv = (u, v)
        # Soft up-and-toward-camera normal so cards take the aquarium top light.
        n = Vector((dx * 0.45, 0.8, dz * 0.45)).normalized()
        for *_, sway in corners:
            sway_values.append(sway)
            normals.append(to_blender(n.x, n.y, n.z).normalized())

    carpet_tiles = [name for name in CARD_TILES if name.startswith('carpet')]
    for (x_range, z_range, count, widths) in CARPET_ZONES:
        for _ in range(count):
            width = RNG.uniform(*widths)
            add_card(RNG.uniform(*x_range), RNG.uniform(*z_range), width, width * 0.5,
                     CARPET_SINK, RNG.choice(carpet_tiles), RNG.random() < 0.5, 0.25)
    for (x_range, z_range, count, heights) in STEM_ZONES:
        for _ in range(count):
            height = RNG.uniform(*heights)
            tile = 'stem_1' if RNG.random() < 0.3 else 'stem_0'
            add_card(RNG.uniform(*x_range), RNG.uniform(*z_range), height * 0.5, height,
                     STEM_SINK, tile, RNG.random() < 0.5, 1.0)

    mesh = bpy.data.meshes.new('slice-a-cards')
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new('slice-a-cards', mesh)
    bpy.context.scene.collection.objects.link(obj)
    set_point_attribute(obj, '_SWAY', sway_values)
    mesh.normals_split_custom_set_from_vertices(normals)
    log(f'cards: {len(sway_values) // 4} cards, {triangle_count(obj)} triangles')
    return obj


# --------------------------------------------------------------------------
# Substrate: gently mounded terrain with planar UVs (unique baked texture).
# --------------------------------------------------------------------------

SUBSTRATE_X = (-5.0, 5.0)
SUBSTRATE_Z = (-1.8, 2.8)


def surface_y(x, z):
    return FLOOR + substrate_height(x, z)


def substrate_height(x, z):
    # Nature-aquarium slope: rises toward the rear and toward the planted left.
    back = min(max(0.0, 0.4 - z), 1.6) ** 1.3 * 0.16
    left_rise = 0.18 / (1.0 + math.exp((x + 1.2) * 1.8))
    mound_a = 0.26 * math.exp(-((x + 2.3) ** 2 / 1.4 + (z + 0.2) ** 2 / 0.7))
    mound_r = 0.1 * math.exp(-((x - 2.35) ** 2 / 0.6 + (z + 0.4) ** 2 / 0.4))
    path = -0.04 * math.exp(-((x - 0.3) ** 2 / 1.4 + (z - 1.0) ** 2 / 0.7))
    ripple = 0.006 * math.sin(x * 2.3 + z * 1.1) + 0.004 * math.sin(x * 5.1 - z * 3.7)
    return back + left_rise + mound_a + mound_r + path + ripple


def build_substrate(columns=96, rows=32):
    mesh = bpy.data.meshes.new('slice-a-substrate')
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    grid = []
    for row in range(rows + 1):
        z = SUBSTRATE_Z[0] + (SUBSTRATE_Z[1] - SUBSTRATE_Z[0]) * row / rows
        line = []
        for column in range(columns + 1):
            x = SUBSTRATE_X[0] + (SUBSTRATE_X[1] - SUBSTRATE_X[0]) * column / columns
            line.append(bm.verts.new(to_blender(x, FLOOR + substrate_height(x, z), z)))
        grid.append(line)
    for row in range(rows):
        for column in range(columns):
            face = bm.faces.new((grid[row][column], grid[row + 1][column],
                                 grid[row + 1][column + 1], grid[row][column + 1]))
            for loop in face.loops:
                co = loop.vert.co
                loop[uv].uv = ((co.x - SUBSTRATE_X[0]) / (SUBSTRATE_X[1] - SUBSTRATE_X[0]),
                               1.0 - ((-co.y) - SUBSTRATE_Z[0]) / (SUBSTRATE_Z[1] - SUBSTRATE_Z[0]))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new('slice-a-substrate', mesh)
    bpy.context.scene.collection.objects.link(obj)
    set_neutral_color(obj)
    log(f'substrate: {triangle_count(obj)} triangles')
    return obj


# --------------------------------------------------------------------------
# Contact occlusion (Cycles): floor AO map + per-vertex hardscape AO.
# Only hardscape and substrate occlude; alpha vegetation is hidden so its
# card quads cannot darken the floor as solid slabs.
# --------------------------------------------------------------------------

def bake_material(obj, image=None):
    material = bpy.data.materials.new(f'{obj.name}-bake')
    material.use_nodes = True
    if image is not None:
        node = material.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        material.node_tree.nodes.active = node
    obj.data.materials.clear()
    obj.data.materials.append(material)


def run_bake(obj, target):
    scene = bpy.context.scene
    scene.render.bake.target = target
    scene.render.bake.margin = 8
    with bpy.context.temp_override(active_object=obj, object=obj,
                                   selected_objects=[obj], selected_editable_objects=[obj]):
        bpy.ops.object.bake(type='AO')


def bake_occlusion(substrate, hardscape, hidden):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 96
    world = bpy.data.worlds.new('bake-world')
    world.light_settings.distance = 0.9
    scene.world = world
    for obj in hidden:
        obj.hide_render = True

    image = bpy.data.images.new('substrate_ao', 1024, 512, alpha=False)
    bake_material(substrate, image)
    run_bake(substrate, 'IMAGE_TEXTURES')
    image.filepath_raw = str(WORK / 'substrate_ao.png')
    image.file_format = 'PNG'
    image.save()
    log('baked substrate_ao.png')

    for obj in hardscape:
        bake_material(obj)
        run_bake(obj, 'VERTEX_COLORS')
        log(f'baked vertex AO for {obj.name}')
    for obj in hidden:
        obj.hide_render = False


def export(objects):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objects)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT),
        export_format='GLB',
        use_selection=True,
        export_materials='NONE',
        export_vertex_color='ACTIVE',
        export_attributes=True,
        export_normals=True,
        export_texcoords=True,
        export_tangents=False,
        export_yup=True,
        export_apply=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
    )
    log(f'exported {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.2f} MB)')


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    WORK.mkdir(parents=True, exist_ok=True)
    rocks = build_rocks()
    wood = build_wood()
    moss = build_moss([rocks, wood])
    plants = build_plants()
    substrate = build_substrate()
    cards = build_cards()
    objects = [rocks, wood, moss, plants, cards, substrate]
    bake_occlusion(substrate, [rocks, wood], [moss, plants, cards])
    for obj in objects:
        obj.data.name = obj.name
    total = sum(triangle_count(obj) for obj in objects)
    log(f'total triangles: {total}')
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'slice-a.blend'))
    export(objects)


main()
