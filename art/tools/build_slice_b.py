"""Build the Slice B runtime environment: the approved Aquascape Hero Frame
Pass 2 (composition B) translated for the real-time habitat.

Run headless (Blender 5.2 LTS), after fetch_sources.py:
  blender -b --factory-startup -P art/tools/build_slice_b.py

Outputs: habitat/assets/slice-b/environment.glb   geometry only, no materials
         art/work/slice-b/cards/*.png              card tiles for prepare_textures_slice_b.py

The offline frame is the visual target, not a polygon source. Translation:
- hardscape (rocks, three-gesture driftwood root, moss) is real geometry, decimated;
- hardscape planting, rock/wood epiphytes, hairgrass and ribbon plants are solid
  vertex-coloured leaf geometry (no alpha, so no overdraw cost);
- the background stem masses and the carpet's relief are camera-facing cards
  rendered here from the fixed habitat camera angle; the carpet itself is baked
  into the substrate texture by prepare_textures_slice_b.py.
Materials are assigned at runtime by mesh name.
"""

import bisect
import math
import pathlib
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import slice_b_layout as L  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'art' / 'source' / 'polyhaven'
WORK = ROOT / 'art' / 'work' / 'slice-b'
CARDS = WORK / 'cards'
OUT = ROOT / 'habitat' / 'assets' / 'slice-b' / 'environment.glb'
RNG = random.Random(20260924)

# Card atlas layout (pixels, y from the top). Must match prepare_textures_slice_b.py.
CARD_ATLAS = (2048, 768)
STEM_TILE = (256, 512)       # 8 tiles in the top row: kinds 0..3, two variants each
CARPET_TILE = (512, 256)     # 4 tiles in the bottom row
STEM_REGION = (0.5, 1.0)     # habitat units covered by a stem tile (width, height)
CARPET_REGION = (1.0, 0.5)

# Linear albedo per plant character (the offline Pass 2 values).
COLOURS = {
    'broadleaf': (0.05, 0.13, 0.045), 'fern': (0.07, 0.15, 0.05), 'grass': (0.12, 0.28, 0.08),
    'ribbon': (0.1, 0.22, 0.07), 'crypt': (0.08, 0.13, 0.05), 'stem': (0.12, 0.26, 0.07),
    'carpet': (0.075, 0.17, 0.05),
}
STEM_KINDS = [
    dict(leaf_len=0.095, per_whorl=4, width_ratio=0.2, top=(1.25, 1.15, 0.7), base=(0.7, 0.85, 0.65)),
    dict(leaf_len=0.14, per_whorl=2, width_ratio=0.3, top=(1.05, 1.2, 0.8), base=(0.65, 0.8, 0.6)),
    dict(leaf_len=0.085, per_whorl=3, width_ratio=0.25, top=(1.45, 0.85, 0.65), base=(0.75, 0.8, 0.6)),
    dict(leaf_len=0.12, per_whorl=3, width_ratio=0.16, top=(0.9, 1.1, 0.75), base=(0.5, 0.65, 0.5)),
]


def log(message):
    print(f'[slice-b] {message}', flush=True)


def B(x, y, z):
    return Vector((x, -z, y))


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)


def mesh_object(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return link(bpy.data.objects.new(name, mesh))


def triangle_count(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def import_asset(asset_id):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(next((SRC / asset_id).glob('*.gltf'))))
    created = sorted(set(bpy.data.objects) - before, key=lambda obj: obj.name)
    meshes = {}
    for obj in created:
        if obj.type == 'MESH':
            matrix = obj.matrix_world.copy()
            obj.parent = None
            obj.data.transform(matrix)
            obj.matrix_world = Matrix.Identity(4)
            meshes[obj.name] = obj
    for obj in created:
        if obj.type != 'MESH':
            bpy.data.objects.remove(obj)
    return meshes


def recenter_on_base(obj):
    verts = obj.data.vertices
    zs = [v.co.z for v in verts]
    min_z, max_z = min(zs), max(zs)
    base = [v.co for v in verts if v.co.z < min_z + 0.08 * (max_z - min_z)]
    cx = sum(p.x for p in base) / len(base)
    cy = sum(p.y for p in base) / len(base)
    obj.data.transform(Matrix.Translation(Vector((-cx, -cy, -min_z))))
    return max_z - min_z


def decimate(obj, target):
    count = triangle_count(obj)
    if count <= target:
        return
    modifier = obj.modifiers.new('decimate', 'DECIMATE')
    modifier.ratio = target / count
    modifier.use_collapse_triangulate = True
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True,
                                           depsgraph=depsgraph)
    obj.modifiers.remove(modifier)
    old = obj.data
    obj.data = mesh
    bpy.data.meshes.remove(old)


def duplicate(obj, name):
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = name
    return link(copy)


def join(objects, name):
    target = objects[0]
    with bpy.context.temp_override(active_object=target, object=target,
                                   selected_editable_objects=objects, selected_objects=objects):
        bpy.ops.object.join()
    target.name = name
    target.data.name = name
    return target


def set_point_attribute(obj, name, values):
    attribute = obj.data.attributes.new(name, 'FLOAT', 'POINT')
    attribute.data.foreach_set('value', values)


def set_sway_by_height(obj, scale=1.2, exponent=1.5):
    values = []
    for v in obj.data.vertices:
        x, y, z = v.co.x, v.co.z, -v.co.y
        values.append(max(0.0, min(1.0, (y - L.surface_y(x, z)) / scale)) ** exponent)
    set_point_attribute(obj, '_SWAY', values)


def set_contact_color(obj, reach=0.45):
    """Hardscape contact occlusion without a bake: darker toward the substrate."""
    mesh = obj.data
    color = mesh.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
    for vertex, item in zip(mesh.vertices, color.data):
        x, y, z = vertex.co.x, vertex.co.z, -vertex.co.y
        lift = max(0.0, y - L.surface_y(x, z))
        shade = 0.42 + 0.58 * L.smoothstep(0.0, reach, lift)
        item.color = (shade, shade, shade, 1.0)
    mesh.color_attributes.active_color = color


# ==========================================================================
# Procedural leaf geometry (shared by cards and runtime plants)
# ==========================================================================

def add_leaf(bm, col, base, direction, normal_hint, length, width, shape, tint, arch=0.25, fold=0.2,
             rows=4, columns=(-1.0, 0.0, 1.0), wave=0.0, twist=0.0):
    direction = direction.normalized()
    side = direction.cross(normal_hint)
    if side.length < 1e-5:
        side = direction.orthogonal()
    side.normalize()
    up = side.cross(direction).normalized()
    grid = []
    for row in range(rows + 1):
        t = row / rows
        half = width * 0.5 * shape(t)
        rot = twist * t
        side_t = side * math.cos(rot) + up * math.sin(rot)
        up_t = up * math.cos(rot) - side * math.sin(rot)
        centre = base + direction * (length * t) + up * (-arch * length * t * t)
        grid.append([bm.verts.new(centre + side_t * (c * half) + up_t * (abs(c) * half * fold)
                                  + up_t * (wave * half * math.sin(t * 18 + c * 2)))
                     for c in columns])
    shade = 0.85 + 0.15 * RNG.random()
    for row in range(rows):
        for c in range(len(columns) - 1):
            face = bm.faces.new((grid[row][c], grid[row][c + 1], grid[row + 1][c + 1], grid[row + 1][c]))
            for loop in face.loops:
                loop[col] = (tint[0] * shade, tint[1] * shade, tint[2] * shade, 1.0)


def ellipse(t):
    return math.sin(math.pi * min(1.0, t ** 0.85)) ** 0.8 if t < 1 else 0.0


def lance(t):
    return math.sin(math.pi * t ** 0.6) ** 1.2 * (1 - t) ** 0.3


def blade(t):
    return (1 - t) ** 0.9


def ribbon_shape(t):
    return 1.0 - 0.7 * t ** 3


def times(colour, tint):
    return tuple(c * k for c, k in zip(colour, tint))


def jitter(base, amount=0.12):
    return tuple(max(0.0, c * (1 + RNG.uniform(-amount, amount))) for c in base)


def strip(bm, col, points, width, tint, facing):
    verts = []
    for p in points:
        side = Vector((0, 0, 1)).cross((facing - p).normalized()).normalized() * width * 0.5
        verts.append((bm.verts.new(p - side), bm.verts.new(p + side)))
    for (a, b), (c, d) in zip(verts, verts[1:]):
        face = bm.faces.new((a, b, d, c))
        for loop in face.loops:
            loop[col] = (*tint, 1.0)


def stem_plant(bm, col, base, height, lean, kind, shade, facing):
    whorls = max(8, int(height / 0.045))
    points = []
    for i in range(whorls + 1):
        t = i / whorls
        points.append(base + Vector((0, 0, height * t)) + Vector((lean[0], -lean[1], 0)) * (t * t) * height
                      + noise.noise_vector(base * 2 + Vector((0, 0, t * 3))) * 0.02 * t)
    stem_colour = times(COLOURS['stem'], tuple(c * shade for c in kind['base']))
    strip(bm, col, points, 0.01, stem_colour, facing)
    for i, p in enumerate(points[1:], start=1):
        t = i / whorls
        tint = tuple((b + (c - b) * t ** 1.5) * shade for b, c in zip(kind['base'], kind['top']))
        spin = RNG.uniform(0, math.tau)
        size = kind['leaf_len'] * (0.6 + 0.5 * math.sin(math.pi * min(1.0, t * 1.1))) * (0.75 if t > 0.92 else 1.0)
        for k in range(kind['per_whorl']):
            angle = spin + k * math.tau / kind['per_whorl']
            out = Vector((math.cos(angle), math.sin(angle), 0))
            direction = (out + Vector((0, 0, 0.55 + 0.6 * t))).normalized()
            add_leaf(bm, col, p, direction, Vector((0, 0, 1)), size, size * kind['width_ratio'], lance,
                     times(COLOURS['stem'], jitter(tint, 0.06)), arch=0.2, fold=0.0, rows=2)


def carpet_leaves(bm, col, x0, x1, z0, z1, count, surface, cushion=0.05):
    for _ in range(count):
        x, z = RNG.uniform(x0, x1), RNG.uniform(z0, z1)
        height = cushion * RNG.uniform(0.2, 1.0)
        centre = Vector((x, -z, surface(x, z) + height))
        normal = (Vector((0, 0, 1)) + Vector((RNG.gauss(0, 0.45), RNG.gauss(0, 0.45), 0))).normalized()
        size = RNG.uniform(0.015, 0.024)
        tangent = normal.orthogonal().normalized()
        bitangent = normal.cross(tangent)
        ring = [bm.verts.new(centre + (tangent * math.cos(k * math.tau / 6) + bitangent * math.sin(k * math.tau / 6)) * size)
                for k in range(6)]
        middle = bm.verts.new(centre + normal * size * 0.15)
        shade = RNG.uniform(0.75, 1.15)
        tint = times(COLOURS['carpet'], (0.85 * shade, 1.05 * shade, 0.75 * shade))
        for k in range(6):
            face = bm.faces.new((middle, ring[k], ring[(k + 1) % 6]))
            for loop in face.loops:
                loop[col] = (*tint, 1.0)


# ==========================================================================
# Card tiles (rendered from the habitat camera angle)
# ==========================================================================

def vertex_colour_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    bsdf = tree.nodes['Principled BSDF']
    attribute = tree.nodes.new('ShaderNodeVertexColor')
    attribute.layer_name = 'Col'
    tree.links.new(attribute.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.6
    return material


def setup_tile_render(width, height):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    try:
        scene.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    world = bpy.data.worlds.new('tile-world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.85
    scene.world = world
    sun = bpy.data.lights.new('tile-sun', 'SUN')
    sun.energy = 1.2
    sun_obj = link(bpy.data.objects.new('tile-sun', sun))
    sun_obj.rotation_euler = (math.radians(25), math.radians(-20), 0)


def tile_camera(width, height, target_z, elevation_deg):
    data = bpy.data.cameras.new('tile-camera')
    data.type = 'ORTHO'
    data.sensor_fit = 'VERTICAL'
    data.ortho_scale = height
    cam = link(bpy.data.objects.new('tile-camera', data))
    elevation = math.radians(elevation_deg)
    cam.location = Vector((0, -5 * math.cos(elevation), target_z + 5 * math.sin(elevation)))
    cam.rotation_euler = (math.pi / 2 - elevation, 0, 0)
    bpy.context.scene.camera = cam
    return cam


def render_tile(path, width_px, height_px, region, target_z, elevation, builder):
    clear_scene()
    setup_tile_render(width_px, height_px)
    tile_camera(*region, target_z, elevation)
    bm = bmesh.new()
    col = bm.loops.layers.float_color.new('Col')
    builder(bm, col)
    obj = mesh_object('tile', bm)
    obj.data.materials.append(vertex_colour_material('tile'))
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def render_cards():
    CARDS.mkdir(parents=True, exist_ok=True)
    facing = Vector((0, -50, 0))
    # Stem clumps: the tile covers 0.5 x 1.0 units; clumps reach ~0.92.
    for index in range(8):
        kind = STEM_KINDS[index % 4]

        def stems(bm, col, kind=kind):
            shade = RNG.uniform(0.85, 1.05)
            for _ in range(RNG.randint(14, 20)):
                base = Vector((RNG.gauss(0, 0.075), RNG.gauss(0, 0.05), 0))
                h = 0.92 * RNG.uniform(0.8, 1.02)
                lean = (RNG.gauss(0.03, 0.05), RNG.gauss(0, 0.03))
                stem_plant(bm, col, base, h, lean, kind, shade * RNG.uniform(0.8, 1.1), facing)
        render_tile(CARDS / f'stem_{index}.png', *STEM_TILE, STEM_REGION, 0.5, 4, stems)
        log(f'card stem_{index}')
    # Carpet relief: a strip of cushion seen from the camera's floor angle.
    for index in range(4):
        def carpet(bm, col):
            def surface(x, z):
                return 0.02 * math.sin(x * 9 + index) + 0.012 * math.sin(z * 17)
            carpet_leaves(bm, col, -0.5, 0.5, -0.25, 0.25, 1700, surface, cushion=0.06)
        render_tile(CARDS / f'carpet_{index}.png', *CARPET_TILE, CARPET_REGION, 0.12, 16, carpet)
        log(f'card carpet_{index}')
    # Top-down carpet texture for the substrate bake.

    def carpet_top(bm, col):
        carpet_leaves(bm, col, -0.55, 0.55, -0.55, 0.55, 5200, lambda x, z: 0.0, cushion=0.04)
    render_tile(CARDS / 'carpet_top.png', 512, 512, (1.0, 1.0), 0.0, 90, carpet_top)
    log('card carpet_top')


# ==========================================================================
# Runtime geometry
# ==========================================================================

def build_substrate(columns=96, rows=40):
    (x0, x1), (z0, z1) = L.SUBSTRATE_X, L.SUBSTRATE_Z
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    grid = []
    for row in range(rows + 1):
        # Rows concentrate toward the front, where the floor is seen large.
        t = row / rows
        z = z0 + (z1 - z0) * (t ** 0.75)
        grid.append([bm.verts.new(B(x0 + (x1 - x0) * c / columns, L.surface_y(x0 + (x1 - x0) * c / columns, z), z))
                     for c in range(columns + 1)])
    for row in range(rows):
        for c in range(columns):
            face = bm.faces.new((grid[row][c], grid[row + 1][c], grid[row + 1][c + 1], grid[row][c + 1]))
            for loop in face.loops:
                co = loop.vert.co
                # glTF v runs from the image top: flip so image row 0 (v = 0) is the front edge.
                loop[uv].uv = ((co.x - x0) / (x1 - x0), 1.0 - L.substrate_v(-co.y))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=bm.faces)
    obj = mesh_object('slice-b-substrate', bm)
    set_contact_color(obj, reach=1.0)
    for item in obj.data.color_attributes['Col'].data:
        item.color = (1.0, 1.0, 1.0, 1.0)
    log(f'substrate: {triangle_count(obj)} triangles')
    return obj


def build_rocks():
    sources = import_asset('rock_moss_set_02')
    heights = {name: recenter_on_base(obj) for name, obj in sources.items()}
    parts = []
    for index, (key, x, z, scale, yaw, sink, tilt, target) in enumerate(L.ROCKS):
        name = f'rock_moss_set_02_{key}'
        rock = duplicate(sources[name], f'rock-{index}')
        decimate(rock, target)
        scale *= L.ROCK_SCALE
        height = heights[name] * scale
        rock.data.transform(Matrix.Translation(B(x, L.surface_y(x, z) - sink * height, z))
                            @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
                            @ Matrix.Rotation(math.radians(tilt), 4, 'X')
                            @ Matrix.Scale(scale, 4))
        parts.append(rock)
    for index, (x, z, scale) in enumerate(L.PEBBLES):
        pebble = duplicate(sources['rock_moss_set_02_rock08'], f'pebble-{index}')
        decimate(pebble, 150)
        height = heights['rock_moss_set_02_rock08'] * scale
        pebble.data.transform(Matrix.Translation(B(x, L.surface_y(x, z) - 0.4 * height, z))
                              @ Matrix.Rotation(RNG.uniform(0, math.tau), 4, 'Z')
                              @ Matrix.Rotation(math.radians(RNG.uniform(-20, 20)), 4, 'X')
                              @ Matrix.Scale(scale, 4))
        parts.append(pebble)
    for obj in sources.values():
        bpy.data.objects.remove(obj)
    rocks = join(parts, 'slice-b-rocks')
    set_contact_color(rocks)
    log(f'rocks: {triangle_count(rocks)} triangles')
    return rocks


JOINTS = []


def catmull(points, samples):
    pts = [Vector(p) for p in points]
    pts = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    segments = len(pts) - 3
    for i in range(samples + 1):
        t = i / samples * segments
        k = min(int(t), segments - 1)
        u = t - k
        p0, p1, p2, p3 = pts[k:k + 4]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u))
    return out


def tube(bm, uv_layer, spine, radii, sides, seed):
    rings = []
    length = 0.0
    tangent_prev = (spine[1] - spine[0]).normalized()
    normal = tangent_prev.orthogonal().normalized()
    for index, point in enumerate(spine):
        if index > 0:
            length += (point - spine[index - 1]).length
        tangent = (spine[index + 1] - point).normalized() if index < len(spine) - 1 else tangent_prev
        axis = tangent_prev.cross(tangent)
        if axis.length > 1e-6:
            normal = Matrix.Rotation(tangent_prev.angle(tangent), 3, axis.normalized()) @ normal
        tangent_prev = tangent
        binormal = tangent.cross(normal).normalized()
        ring = []
        for side in range(sides + 1):
            theta = math.tau * side / sides
            direction = normal * math.cos(theta) + binormal * math.sin(theta)
            gnarl = 1.0 + 0.3 * noise.noise(point * 5.0 + direction * 0.6 + Vector((seed, 0, 0)))
            ridge = 1.0 + 0.1 * math.sin(theta * 5 + length * 6 + seed)
            ring.append((point + direction * radii[index] * gnarl * ridge, side / sides, length))
        rings.append(ring)
    verts = [[bm.verts.new(co) for co, _, _ in ring] for ring in rings]
    for r in range(len(rings) - 1):
        for s in range(sides):
            face = bm.faces.new((verts[r][s], verts[r][s + 1], verts[r + 1][s + 1], verts[r + 1][s]))
            for loop, (rr, ss) in zip(face.loops, ((r, s), (r, s + 1), (r + 1, s + 1), (r + 1, s))):
                _, u, v = rings[rr][ss]
                loop[uv_layer].uv = (u, v / 0.7)


def resolve(points, sink):
    return [(x, L.surface_y(x, z + L.WOOD_Z_SHIFT) - sink if y is None else y, z + L.WOOD_Z_SHIFT)
            for x, y, z in points]


def spine_from(points, samples, wiggle, seed):
    raw = catmull([B(*p) for p in points], samples)
    out = []
    for index, p in enumerate(raw):
        t = index / samples
        envelope = math.sin(math.pi * min(1.0, t * 1.2))
        offset = (noise.noise_vector(p * 1.7 + Vector((seed, seed * 0.5, 0))) * wiggle
                  + noise.noise_vector(p * 4.5 + Vector((0, seed, seed))) * wiggle * 0.35) * envelope
        out.append(p + offset)
    return out


def taper(samples, base, tip, seed):
    return [(tip + (base - tip) * (1 - i / samples) ** 1.35)
            * (1.0 + 0.18 * max(0.0, noise.noise(Vector((i / samples * 5.0, seed, 0.0)))))
            for i in range(samples + 1)]


def build_wood():
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    rng = random.Random(7)
    branches = []
    for index, (points, base, tip) in enumerate(L.WOOD):
        spine = spine_from(resolve(points, 0.22), 36, 0.15, index * 3.7)
        radii = taper(36, base * L.WOOD_GIRTH, tip * 1.5, index * 1.3)
        tube(bm, uv, spine, radii, 10, index * 2.1)
        branches.append((spine, radii))
        JOINTS.append(spine[0])
    for index, points in enumerate(L.ROOTS):
        spine = spine_from(resolve(points, 0.035), 14, 0.04, 20 + index)
        tube(bm, uv, spine, taper(14, 0.09, 0.02, 40 + index), 8, 30 + index)
    for spine, radii in branches:
        for _ in range(3):
            k = rng.randint(int(len(spine) * 0.3), int(len(spine) * 0.85))
            origin = spine[k]
            tangent = (spine[min(k + 1, len(spine) - 1)] - spine[k - 1]).normalized()
            side = tangent.cross(Vector((0, 1, 0))).normalized() * rng.choice((-1, 1))
            direction = (tangent * 0.7 + side * rng.uniform(0.2, 0.7) + Vector((0, 0, rng.uniform(0.1, 0.6)))).normalized()
            length = rng.uniform(0.35, 0.7) if rng.random() < 0.5 else rng.uniform(0.1, 0.18)
            base_r = radii[k] * 0.55
            raw = catmull([origin, origin + direction * length * 0.5 + Vector((0, 0, 0.05)),
                           origin + direction * length + noise.noise_vector(origin * 3) * 0.08], 12)
            tube(bm, uv, raw, taper(12, base_r, max(0.012, base_r * (0.2 if length > 0.3 else 0.45)), k), 7, k * 0.7)
            JOINTS.append(origin)
    for spine, radii in branches[:2]:
        for fork in range(2):
            k = int(len(spine) * rng.uniform(0.78, 0.9))
            origin = spine[k]
            tangent = (spine[k + 1] - spine[k - 1]).normalized()
            side = tangent.cross(Vector((0, 1, 0))).normalized() * (1 if fork else -1)
            direction = (tangent + side * rng.uniform(0.35, 0.8) + Vector((0, 0, rng.uniform(0.0, 0.4)))).normalized()
            length = rng.uniform(0.14, 0.26)
            raw = catmull([origin, origin + direction * length * 0.5,
                           origin + direction * length + noise.noise_vector(origin * 5) * 0.05], 8)
            tube(bm, uv, raw, taper(8, radii[k] * 0.6, 0.009, k + fork), 6, k + fork)
    bm.normal_update()
    wood = mesh_object('slice-b-wood', bm)
    set_contact_color(wood)
    log(f'wood: {triangle_count(wood)} triangles')
    return wood


def sample_surfaces(objects, count, weight_fn, min_up=0.25):
    triangles = []
    for obj in objects:
        mesh = obj.data
        mesh.calc_loop_triangles()
        for tri in mesh.loop_triangles:
            normal = tri.normal
            if normal.z < min_up:
                continue
            a, b, c = (mesh.vertices[i].co.copy() for i in tri.vertices)
            weight = tri.area * normal.z ** 2 * weight_fn((a + b + c) / 3)
            if weight > 0:
                triangles.append((weight, a, b, c, normal.copy()))
    cumulative, acc = [], 0.0
    for t in triangles:
        acc += t[0]
        cumulative.append(acc)
    out = []
    for _ in range(count):
        _, a, b, c, normal = triangles[min(bisect.bisect_left(cumulative, RNG.uniform(0, acc)), len(triangles) - 1)]
        r1, r2 = RNG.random(), RNG.random()
        if r1 + r2 > 1:
            r1, r2 = 1 - r1, 1 - r2
        out.append((a + (b - a) * r1 + (c - a) * r2, normal))
    return out


def near_joint(p, width=0.12):
    return max((math.exp(-((p - j).length ** 2) / width) for j in JOINTS), default=0.0)


def build_moss(hosts, count=560):
    sources = list(import_asset('moss_01').values())
    for obj in sources:
        recenter_on_base(obj)

    def weight(p):
        low = 1.0 - L.smoothstep(L.FLOOR + 0.2, L.FLOOR + 2.2, p.z)
        return 0.45 + 1.2 * near_joint(p) + 0.8 * low
    parts = []
    for index, (point, normal) in enumerate(sample_surfaces(hosts, count, weight)):
        sprig = duplicate(RNG.choice(sources), f'moss-{index}')
        align = Vector((0, 0, 1)).rotation_difference(normal.lerp(Vector((0, 0, 1)), 0.5))
        sprig.data.transform(Matrix.Translation(point - normal * 0.01) @ align.to_matrix().to_4x4()
                             @ Matrix.Rotation(RNG.uniform(0, math.tau), 4, 'Z')
                             @ Matrix.Scale(RNG.uniform(6.0, 11.0), 4))
        parts.append(sprig)
    for obj in sources:
        bpy.data.objects.remove(obj)
    moss = join(parts, 'slice-b-moss')
    set_point_attribute(moss, '_SWAY', [0.15] * len(moss.data.vertices))
    log(f'moss: {triangle_count(moss)} triangles from {count} sprigs')
    return moss


def build_plants(rocks, wood):
    """Solid, vertex-coloured leaf geometry: hardscape planting, epiphytes,
    small rosettes, hairgrass and ribbon plants. No alpha, no overdraw."""
    bm = bmesh.new()
    col = bm.loops.layers.float_color.new('Col')
    up = Vector((0, 0, 1))
    facing = B(*L.CAMERA)

    def rosette(x, z, scale):
        base = B(x, L.surface_y(x, z), z)
        for _ in range(RNG.randint(5, 8)):
            angle = RNG.uniform(0, math.tau)
            out = Vector((math.cos(angle), math.sin(angle), 0))
            elevation = RNG.uniform(0.35, 0.95)
            petiole = (out * (1 - elevation) + Vector((0, 0, elevation))).normalized()
            start = base + petiole * RNG.uniform(0.06, 0.16) * scale
            strip(bm, col, [base, start], 0.012 * scale, times(COLOURS['broadleaf'], (1.3, 1.3, 1.0)), facing)
            length = RNG.uniform(0.22, 0.4) * scale
            add_leaf(bm, col, start, (petiole + out * 0.6).normalized(), up, length, length * RNG.uniform(0.42, 0.55),
                     ellipse, times(COLOURS['broadleaf'], jitter((1, 1, 1), 0.15)), arch=0.18, fold=0.18, rows=4)

    for x, z, s in L.BROADLEAF_SPOTS:
        for _ in range(2):
            rosette(x + RNG.gauss(0, 0.08), z + RNG.gauss(0, 0.06), s * RNG.uniform(0.85, 1.15))

    rock_parts = sample_surfaces([rocks], 40, lambda p: 1.0 if p.z > L.FLOOR + 0.35 else 0.2, min_up=0.35)
    for point, normal in rock_parts:
        for _ in range(RNG.randint(3, 6)):
            angle = RNG.uniform(0, math.tau)
            direction = (normal * 0.8 + Vector((math.cos(angle), math.sin(angle), 0)) * 0.6 + up * 0.4).normalized()
            length = RNG.uniform(0.1, 0.17)
            add_leaf(bm, col, point, direction, up, length, length * 0.38, lance,
                     times(COLOURS['broadleaf'], jitter((0.85, 0.95, 1.0), 0.15)), arch=0.12, rows=3, wave=0.08)

    wood_parts = sample_surfaces([wood], 22, lambda p: 0.2 + near_joint(p, 0.1), min_up=0.3)
    for point, normal in wood_parts:
        scale = RNG.uniform(0.6, 1.0)
        for _ in range(RNG.randint(5, 9)):
            angle = RNG.uniform(0, math.tau)
            direction = (normal * 0.4 + Vector((math.cos(angle), math.sin(angle), 0)) * 0.5
                         + Vector((0, 0, RNG.uniform(0.5, 1.1)))).normalized()
            length = RNG.uniform(0.35, 0.75) * scale
            add_leaf(bm, col, point, direction, up, length, length * 0.16, lance,
                     times(COLOURS['fern'], jitter((1, 1, 1), 0.12)), arch=0.3, fold=0.1, rows=6,
                     wave=0.12, twist=RNG.uniform(-0.6, 0.6))

    for cx, cz, n in L.CRYPT_GROUPS:
        for _ in range(n):
            x, z = cx + RNG.gauss(0, 0.1), cz + RNG.gauss(0, 0.08)
            base = B(x, L.surface_y(x, z), z)
            for _ in range(RNG.randint(6, 9)):
                angle = RNG.uniform(0, math.tau)
                direction = (Vector((math.cos(angle), math.sin(angle), 0)) * RNG.uniform(0.3, 0.7) + up).normalized()
                length = RNG.uniform(0.14, 0.26) * RNG.uniform(0.8, 1.3)
                add_leaf(bm, col, base, direction, up, length, length * 0.3, lance,
                         times(COLOURS['crypt'], jitter((1.05, 0.9, 0.7), 0.12)), arch=0.35, fold=0.12, rows=4,
                         wave=0.15)

    for cx, cz, n in L.HAIRGRASS_CLUSTERS:
        peak = RNG.uniform(0.2, 0.4)
        for _ in range(n):
            x, z = cx + RNG.gauss(0, 0.16), cz + RNG.gauss(0, 0.12)
            if L.path_mask(x, z) > 0.45:
                continue
            falloff = math.exp(-((x - cx) ** 2 + (z - cz) ** 2) / 0.05)
            height = peak * (0.5 + 0.5 * falloff)
            base_y = L.surface_y(x, z)
            for _ in range(RNG.randint(9, 14)):
                bx, bz = x + RNG.gauss(0, 0.03), z + RNG.gauss(0, 0.03)
                angle = RNG.uniform(0, math.tau)
                direction = (up + Vector((math.cos(angle), math.sin(angle), 0)) * RNG.uniform(0.05, 0.4)).normalized()
                add_leaf(bm, col, B(bx, base_y - 0.01, bz), direction, Vector((1, 0, 0)),
                         height * RNG.uniform(0.6, 1.1), 0.014, blade,
                         times(COLOURS['grass'], jitter((0.9, 1.05, 0.8), 0.1)), arch=0.25, fold=0.0, rows=3,
                         columns=(-1.0, 1.0))

    for cx, cz, count, heights in L.RIBBON_CLUMPS:
        for _ in range(count):
            x, z = cx + RNG.gauss(0, 0.13), cz + RNG.gauss(0, 0.1)
            height = RNG.uniform(*heights)
            width = RNG.uniform(0.04, 0.065)
            lean = RNG.gauss(0.34, 0.12)
            tint = times(COLOURS['ribbon'], jitter((0.85, 1.0, 0.85), 0.12))
            base = B(x, L.surface_y(x, z) - 0.02, z)
            phase = RNG.uniform(0, math.tau)
            previous = None
            segments = 12
            for i in range(segments + 1):
                t = i / segments
                p = (base + Vector((0, 0, height * t)) + Vector((lean, 0, 0)) * height * t ** 2.6
                     + Vector((math.sin(t * 4 + phase), 0, 0)) * 0.04 * t)
                view = (facing - p).normalized()
                twist = math.sin(t * 5 + phase) * 0.9
                side = Vector((0, 0, 1)).cross(view).normalized()
                side = side * math.cos(twist) + view * math.sin(twist)
                half = width * 0.5 * ribbon_shape(t)
                a, b = bm.verts.new(p - side * half), bm.verts.new(p + side * half)
                if previous:
                    face = bm.faces.new((previous[0], previous[1], b, a))
                    shade = 0.75 + 0.35 * t
                    for loop in face.loops:
                        loop[col] = (tint[0] * shade, tint[1] * shade, tint[2] * shade, 1.0)
                previous = (a, b)

    bm.normal_update()
    plants = mesh_object('slice-b-plants', bm)
    plants.data.color_attributes.active_color = plants.data.color_attributes['Col']
    set_sway_by_height(plants)
    log(f'plants: {triangle_count(plants)} triangles')
    return plants


def tile_uv(index, stem):
    width, height = CARD_ATLAS
    if stem:
        x, y, w, h = index * STEM_TILE[0], 0, *STEM_TILE
    else:
        x, y, w, h = index * CARPET_TILE[0], STEM_TILE[1], *CARPET_TILE
    return x / width, (x + w) / width, 1 - (y + h) / height, 1 - y / height


def build_cards():
    """Camera-facing cards: background stem clumps and carpet relief."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    sway, normals = [], []
    camera = L.CAMERA

    def add_card(x, z, width, height, sink, tile, mirror, sway_top, shade):
        base = L.surface_y(x, z) - sink * height
        dx, dz = camera[0] - x, camera[2] - z
        length = math.hypot(dx, dz)
        dx, dz = dx / length, dz / length
        right = (dz, -dx)
        u0, u1, v0, v1 = tile
        if mirror:
            u0, u1 = u1, u0
        corners = [(x - right[0] * width / 2, base, z - right[1] * width / 2, u0, v0, 0.0),
                   (x + right[0] * width / 2, base, z + right[1] * width / 2, u1, v0, 0.0),
                   (x + right[0] * width / 2, base + height, z + right[1] * width / 2, u1, v1, sway_top),
                   (x - right[0] * width / 2, base + height, z - right[1] * width / 2, u0, v1, sway_top)]
        face = bm.faces.new([bm.verts.new(B(cx, cy, cz)) for cx, cy, cz, *_ in corners])
        for loop, (*_, u, v, _s) in zip(face.loops, corners):
            loop[uv].uv = (u, v)
        n = Vector((dx * 0.45, 0.8, dz * 0.45)).normalized()
        for *_, s in corners:
            sway.append(s)
            normals.append(B(n.x, n.y, n.z).normalized())
        shades.extend([shade] * 4)

    shades = []
    stem_cards = 0
    for mx, mz, half, peak, clumps, kinds in L.STEM_MASSES:
        for c in range(clumps):
            cx = mx + RNG.uniform(-half, half)
            cz = mz + RNG.gauss(0, 0.18)
            dome = max(0.3, 1 - (abs(cx - mx) / half) ** 1.6 * 0.6)
            h = peak * dome * RNG.uniform(0.7, 1.08) / 0.92
            kind = kinds[c % len(kinds)]
            tile = tile_uv(kind + 4 * RNG.randint(0, 1), True)
            add_card(cx, cz, h * STEM_REGION[0] / STEM_REGION[1], h, 0.03, tile, RNG.random() < 0.5, 1.0,
                     RNG.uniform(0.75, 1.05))
            stem_cards += 1
    carpet_cards = 0
    attempts = 0
    while carpet_cards < 36 and attempts < 5000:
        attempts += 1
        x, z = RNG.uniform(-4.2, 3.6), RNG.uniform(-1.2, 1.9)
        coverage = L.carpet_coverage(x, z)
        if coverage < 0.55 or RNG.random() > coverage:
            continue
        width = RNG.uniform(0.45, 0.75)
        # Low relief only: mostly sunk, darker than the lit floor under it.
        add_card(x, z, width, width * 0.5, 0.55, tile_uv(RNG.randint(0, 3), False), RNG.random() < 0.5, 0.2,
                 0.55 + 0.15 * coverage)
        carpet_cards += 1

    mesh = bpy.data.meshes.new('slice-b-cards')
    bm.to_mesh(mesh)
    bm.free()
    obj = link(bpy.data.objects.new('slice-b-cards', mesh))
    set_point_attribute(obj, '_SWAY', sway)
    color = mesh.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
    for item, shade in zip(color.data, shades):
        item.color = (shade, shade, shade, 1.0)
    mesh.color_attributes.active_color = color
    mesh.normals_split_custom_set_from_vertices(normals)
    log(f'cards: {stem_cards} stem + {carpet_cards} carpet, {triangle_count(obj)} triangles')
    return obj


def export(objects):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objects)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT), export_format='GLB', use_selection=True, export_materials='NONE',
        export_vertex_color='ACTIVE', export_attributes=True, export_normals=True, export_texcoords=True,
        export_tangents=False, export_yup=True, export_apply=True, export_animations=False,
        export_cameras=False, export_lights=False)
    log(f'exported {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.2f} MB)')


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if '--skip-cards' not in sys.argv:
        state = RNG.getstate()
        render_cards()
        RNG.setstate(state)   # geometry is identical with or without a card re-render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rocks = build_rocks()
    wood = build_wood()
    moss = build_moss([rocks, wood])
    plants = build_plants(rocks, wood)
    substrate = build_substrate()
    cards = build_cards()
    objects = [rocks, wood, moss, plants, cards, substrate]
    total = sum(triangle_count(obj) for obj in objects)
    log(f'total triangles: {total}')
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'slice-b.blend'))
    export(objects)


main()
