"""Aquascape Hero Composition: offline Blender composition and render.

Composition study only. Nothing here is loaded by the runtime.

Run headless (Blender 5.2 LTS):
  blender -b --factory-startup -P art/tools/compose_hero_frame.py -- \
      --variant B --mode final --scale 100 --out art/work/hero-frame/final.png

  --variant  A (left triangle) | B (left root mass, sweeping diagonals) | C (low left island)
  --mode     final | clay (silhouette/clay study: one neutral material, same light)
  --scale    render resolution percentage of 1920x1080
  --density  vegetation density multiplier (quick studies use < 1)
  --fish     add a few small neutral fish silhouettes for scale

Coordinates are habitat units (x right, y up, z toward the camera; 1 unit is
about 10 cm) and the camera is the runtime habitat camera (position
(0, 0.06, 6.2), looking at the origin, 38 degree vertical field of view), so
an approved composition can later be rebuilt for the runtime without moving
the viewpoint.

Sources: approved CC0 Poly Haven assets already fetched for Slice A
(rock_moss_set_02, moss_01, dry_branches_medium_01 bark texture,
gravelly_sand, coast_sand_03). All vegetation except the moss is procedural
geometry created here.
"""

import argparse
import math
import pathlib
import random
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'art' / 'source' / 'polyhaven'
FLOOR = -1.45
CAMERA = (0.0, 0.06, 6.2)


def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', default='B', choices='ABC')
    parser.add_argument('--mode', default='final', choices=['final', 'clay'])
    parser.add_argument('--scale', type=int, default=100)
    parser.add_argument('--density', type=float, default=1.0)
    parser.add_argument('--samples', type=int, default=48)
    parser.add_argument('--fish', action='store_true')
    parser.add_argument('--hero-fish', default='', help='directory with the exported Hero Fish (scale reference only)')
    parser.add_argument('--out', default=str(ROOT / 'art' / 'work' / 'hero-frame' / 'frame.png'))
    parser.add_argument('--blend', default='')
    # Natural Environment Stage 1 (offline hardscape material-presence test)
    parser.add_argument('--rocks', default='default', choices=['default', 'scanned'])
    parser.add_argument('--root', default='', help='scanned root model (glTF/GLB/FBX/OBJ) replacing the procedural wood')
    parser.add_argument('--root-yaw', type=float, default=0.0)
    parser.add_argument('--root-tilt', type=float, default=0.0)
    parser.add_argument('--root-roll', type=float, default=0.0)
    parser.add_argument('--root-height', type=float, default=2.1, help='target height of the root above its base')
    parser.add_argument('--root-at', default='-2.2,-0.75', help='habitat x,z of the root base')
    parser.add_argument('--root-sink', type=float, default=0.12, help='fraction of the root height below the surface')
    parser.add_argument('--camera', default='habitat', choices=['habitat', 'close'])
    parser.add_argument('--no-plants', action='store_true', help='hardscape only (no vegetation)')
    parser.add_argument('--wood', default='procedural', choices=['procedural', 'scan-strips'],
                        help='Stage 1 A: scan-strips = root ridges cut from Poly Haven root scans')
    parser.add_argument('--bark', default='default', choices=['default', 'willow'],
                        help='Stage 1 B: willow = Poly Haven bark_willow_02 + restrained weathering')
    return parser.parse_args(argv)


ARGS = parse_args()
RNG = random.Random(20260923)
CLAY = ARGS.mode == 'clay'


def log(message):
    print(f'[hero-frame] {message}', flush=True)


def B(x, y, z):
    """Habitat -> Blender coordinates."""
    return Vector((x, -z, y))


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def gauss2(x, z, cx, cz, sx, sz):
    return math.exp(-(((x - cx) / sx) ** 2 + ((z - cz) / sz) ** 2))


# ==========================================================================
# Composition data per variant
# ==========================================================================

# The far-left column (x < -3.2) stays low and dark: that is where Windows
# puts desktop icons. The hardscape mass is centred around x -2.3.

VARIANTS = {
    'A': {  # strong left triangular hardscape
        'mound': (0.42, -2.3, -0.55, 1.35, 0.95),
        'rocks': [
            # source, x, z, scale, yaw, sink, tilt
            ('rock13', -2.3, -0.75, 1.05, 20, 0.18, 4),
            ('rock11', -1.45, -0.35, 0.72, -30, 0.25, -6),
            ('rock09', -3.05, -0.45, 0.6, 140, 0.3, 8),
            ('rock10', -0.75, 0.05, 0.42, 60, 0.35, 0),
            ('rock12', -0.15, 0.35, 0.24, -10, 0.35, 5),
        ],
        'wood': [
            # spine control points (habitat), base radius, tip radius
            ([(-2.6, -1.0, -1.05), (-2.2, -0.2, -1.1), (-1.6, 0.45, -1.2), (-0.95, 0.95, -1.3)], 0.075, 0.008),
            ([(-2.4, -0.9, -0.95), (-2.0, -0.35, -0.95), (-1.35, 0.1, -1.0), (-0.6, 0.35, -1.05)], 0.055, 0.006),
        ],
        'roots': [],
        'knot': (-2.5, -1.05),
    },
    'B': {  # left root mass with sweeping diagonal branches
        'mound': (0.36, -2.3, -0.5, 1.5, 1.0),
        'rocks': [
            ('rock13', -2.95, -1.1, 0.7, 150, 0.36, -5),    # primary, rear left
            ('rock11', -1.7, -1.0, 0.6, 35, 0.38, 6),       # primary, rear centre-left
            ('rock10', -2.05, 0.1, 0.36, -40, 0.42, 3),     # secondary, front
            ('rock09', -3.05, 0.05, 0.34, 70, 0.42, -8),    # secondary, front left
            ('rock12', -1.05, 0.35, 0.2, 10, 0.42, 6),      # transition
            ('rock08', -2.6, 0.62, 0.16, 120, 0.42, 0),     # transition
            # secondary stones gathered around the primaries' bases
            ('rock12', -3.5, -0.7, 0.26, 40, 0.45, 8), ('rock08', -2.45, -0.72, 0.2, 200, 0.45, -6),
            ('rock09', -1.15, -0.7, 0.24, -70, 0.45, 5), ('rock08', -2.15, -0.55, 0.16, 15, 0.45, 10),
            ('rock12', -2.5, 0.38, 0.17, 95, 0.45, -4), ('rock08', -1.55, 0.38, 0.18, 250, 0.45, 6),
            ('rock09', -3.55, 0.2, 0.18, 10, 0.45, -5),
        ],
        'wood': [
            # hero sweep toward the centre
            ([(-2.45, None, -0.45), (-2.1, -0.55, -0.5), (-1.5, -0.05, -0.6), (-0.8, 0.4, -0.75),
              (-0.1, 0.72, -0.85), (0.5, 0.88, -0.95)], 0.12, 0.012),
            # steep rise
            ([(-2.5, None, -0.55), (-2.3, -0.5, -0.7), (-1.95, 0.15, -0.85), (-1.5, 0.7, -1.0),
              (-1.0, 1.1, -1.1), (-0.72, 1.24, -1.15)], 0.085, 0.012),
            # back left arm, kept below the icon column
            ([(-2.6, None, -0.7), (-2.85, -0.5, -1.0), (-3.05, 0.05, -1.3), (-3.1, 0.35, -1.5)], 0.06, 0.014),
        ],
        'roots': [
            [(-2.45, -1.2, -0.45), (-2.9, None, -0.1), (-3.45, None, 0.2)],
            [(-2.4, -1.2, -0.4), (-2.0, None, 0.0), (-1.6, None, 0.3)],
            [(-2.5, -1.2, -0.5), (-2.85, None, -0.9), (-3.35, None, -1.2)],
            [(-2.35, -1.2, -0.45), (-1.95, None, -0.8), (-1.45, None, -1.15)],
        ],
        'knot': (-2.45, -0.45),
    },
    'C': {  # lower left island, open upper water
        'mound': (0.5, -2.2, -0.35, 1.9, 1.2),
        'rocks': [
            ('rock10', -2.2, -0.35, 0.85, 20, 0.45, 3),
            ('rock09', -3.1, -0.6, 0.62, 110, 0.45, -4),
            ('rock12', -1.3, 0.2, 0.45, -30, 0.45, 5),
            ('rock08', -0.65, 0.5, 0.25, 60, 0.45, 0),
        ],
        'wood': [
            ([(-3.3, -0.85, -0.6), (-2.6, -0.6, -0.7), (-1.8, -0.5, -0.8), (-1.0, -0.62, -0.9), (-0.2, -0.9, -0.95)], 0.08, 0.01),
            ([(-2.4, -0.7, -0.8), (-2.0, -0.2, -0.95), (-1.5, 0.15, -1.05), (-1.0, 0.3, -1.1)], 0.055, 0.006),
        ],
        'roots': [],
        'knot': (-2.4, -0.75),
    },
}
V = VARIANTS[ARGS.variant]

# A shallow sand clearing: from the front centre, curving back to the right.
PATH = [(0.2, 2.2), (0.55, 1.2), (1.05, 0.3), (1.55, -0.6), (2.0, -1.6), (2.3, -2.6)]


def path_distance(x, z):
    best = 9.0
    for (ax, az), (bx, bz) in zip(PATH, PATH[1:]):
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)))
        best = min(best, math.hypot(x - ax - t * dx, z - az - t * dz))
    return best


def path_mask(x, z):
    # Wider toward the viewer, narrowing with depth.
    width = 0.3 + 0.18 * smoothstep(-2.0, 2.0, z)
    wobble = 0.22 * noise.noise(Vector((x * 0.9, z * 0.9, 3.1))) + 0.07 * noise.noise(Vector((x * 4, z * 4, 1.1)))
    core = 1.0 - smoothstep(width * 0.45, width, path_distance(x, z) + wobble)
    # Carpet tongues and stones interrupt it; it fades before the back.
    broken = smoothstep(-0.45, 0.05, noise.noise(Vector((x * 1.4, z * 1.4, 8.0))))
    return core * (0.35 + 0.65 * broken) * smoothstep(-1.9, -0.6, z)


def substrate_height(x, z):
    amp, cx, cz, sx, sz = V['mound']
    back = 0.75 * smoothstep(0.6, -3.3, z) ** 1.4
    mound = amp * gauss2(x, z, cx, cz, sx, sz)
    shoulder = 0.12 * gauss2(x, z, cx + 1.4, cz + 0.3, 1.2, 1.0)
    right_low = -0.06 * smoothstep(-0.5, 3.0, x) * smoothstep(-2.5, 1.0, z)
    clearing = -0.035 * path_mask(x, z)
    undulation = 0.03 * noise.noise(Vector((x * 0.7, z * 0.7, 0.3))) + 0.01 * noise.noise(Vector((x * 3, z * 3, 1.7)))
    return back + mound + shoulder + right_low + clearing + undulation


def surface_y(x, z):
    return FLOOR + substrate_height(x, z)


# ==========================================================================
# Helpers
# ==========================================================================

def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_object(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return link(bpy.data.objects.new(name, mesh))


def try_set(obj, name, value):
    try:
        setattr(obj, name, value)
    except (AttributeError, TypeError, ValueError):
        log(f'  (skipped {type(obj).__name__}.{name})')


def import_asset(asset_id):
    before = set(bpy.data.objects)
    gltf = next((SRC / asset_id).glob('*.gltf'))
    bpy.ops.import_scene.gltf(filepath=str(gltf))
    created = [obj for obj in set(bpy.data.objects) - before]
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


def color_attribute(bm):
    return bm.loops.layers.float_color.new('tint')


# ==========================================================================
# Materials
# ==========================================================================

def principled(name, color=(0.5, 0.5, 0.5), roughness=0.6):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    return material, bsdf


def caustics_group():
    """Soft aquarium caustics: two drifting Voronoi edge layers seen from above."""
    if 'caustics' in bpy.data.node_groups:
        return bpy.data.node_groups['caustics']
    group = bpy.data.node_groups.new('caustics', 'ShaderNodeTree')
    group.interface.new_socket('Factor', in_out='OUTPUT', socket_type='NodeSocketFloat')
    nodes, links = group.nodes, group.links
    out = nodes.new('NodeGroupOutput')
    geometry = nodes.new('ShaderNodeNewGeometry')
    layers = []
    for scale, offset in ((2.3, (0.0, 0.0, 0.0)), (3.1, (0.37, 0.71, 0.5))):
        mapping = nodes.new('ShaderNodeMapping')
        mapping.inputs['Location'].default_value = offset
        mapping.inputs['Scale'].default_value = (1.0, 1.0, 0.0)
        links.new(geometry.outputs['Position'], mapping.inputs['Vector'])
        voronoi = nodes.new('ShaderNodeTexVoronoi')
        voronoi.feature = 'DISTANCE_TO_EDGE'
        voronoi.inputs['Scale'].default_value = scale
        voronoi.inputs['Randomness'].default_value = 0.85
        links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
        ramp.color_ramp.elements[1].position = 0.09
        ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
        links.new(voronoi.outputs['Distance'], ramp.inputs['Fac'])
        layers.append(ramp)
    both = nodes.new('ShaderNodeMath')
    both.operation = 'MULTIPLY'
    links.new(layers[0].outputs['Color'], both.inputs[0])
    links.new(layers[1].outputs['Color'], both.inputs[1])
    soft = nodes.new('ShaderNodeMath')
    soft.operation = 'ADD'
    links.new(both.outputs[0], soft.inputs[0])
    scaled = nodes.new('ShaderNodeMath')
    scaled.operation = 'MULTIPLY'
    scaled.inputs[1].default_value = 0.35
    links.new(layers[0].outputs['Color'], scaled.inputs[0])
    links.new(scaled.outputs[0], soft.inputs[1])
    # Only up-facing surfaces receive caustics.
    separate = nodes.new('ShaderNodeSeparateXYZ')
    links.new(geometry.outputs['Normal'], separate.inputs['Vector'])
    up = nodes.new('ShaderNodeMapRange')
    up.inputs['From Min'].default_value = 0.2
    up.inputs['From Max'].default_value = 0.9
    links.new(separate.outputs['Z'], up.inputs['Value'])
    masked = nodes.new('ShaderNodeMath')
    masked.operation = 'MULTIPLY'
    links.new(soft.outputs[0], masked.inputs[0])
    links.new(up.outputs['Result'], masked.inputs[1])
    links.new(masked.outputs[0], out.inputs['Factor'])
    return group


def add_caustics(material, strength, source_socket=None):
    """Adds caustic light as emission tinted by the surface albedo."""
    if CLAY:
        return
    tree = material.node_tree
    bsdf = tree.nodes['Principled BSDF']
    group = tree.nodes.new('ShaderNodeGroup')
    group.node_tree = caustics_group()
    factor = tree.nodes.new('ShaderNodeMath')
    factor.operation = 'MULTIPLY'
    factor.inputs[1].default_value = strength
    tree.links.new(group.outputs['Factor'], factor.inputs[0])
    tint = tree.nodes.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.blend_type = 'MULTIPLY'
    tint.inputs['Factor'].default_value = 1.0
    tint.inputs[7].default_value = (1.0, 0.93, 0.8, 1.0)
    base_link = next((l for l in tree.links if l.to_socket == bsdf.inputs['Base Color']), None)
    if base_link is not None:
        tree.links.new(base_link.from_socket, tint.inputs[6])
    else:
        tint.inputs[6].default_value = bsdf.inputs['Base Color'].default_value
    tree.links.new(tint.outputs[2], bsdf.inputs['Emission Color'])
    tree.links.new(factor.outputs[0], bsdf.inputs['Emission Strength'])


def image(path, colorspace='sRGB'):
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def textured_ground_material():
    material, bsdf = principled('substrate', (0.3, 0.24, 0.17), 0.85)
    if CLAY:
        return material
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    coords = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (0.55, 0.55, 0.55)
    links.new(coords.outputs['Object'], mapping.inputs['Vector'])
    fine_mapping = nodes.new('ShaderNodeMapping')
    fine_mapping.inputs['Scale'].default_value = (0.8, 0.8, 0.8)
    links.new(coords.outputs['Object'], fine_mapping.inputs['Vector'])

    def tex(asset, kind, mapping_node, colorspace='sRGB'):
        node = nodes.new('ShaderNodeTexImage')
        node.image = image(next((SRC / asset / 'textures').glob(f'*_{kind}_2k.*')), colorspace)
        links.new(mapping_node.outputs['Vector'], node.inputs['Vector'])
        return node

    gravel = tex('gravelly_sand', 'diff', mapping)
    gravel_n = tex('gravelly_sand', 'nor_gl', mapping, 'Non-Color')
    sand = tex('coast_sand_03', 'diff', fine_mapping)
    sand_n = tex('coast_sand_03', 'nor_gl', fine_mapping, 'Non-Color')
    attribute = nodes.new('ShaderNodeAttribute')
    attribute.attribute_name = 'path'
    # Darken and cool the gravel toward the planted hardscape.
    gravel_grade = nodes.new('ShaderNodeHueSaturation')
    gravel_grade.inputs['Saturation'].default_value = 0.6
    gravel_grade.inputs['Value'].default_value = 0.4
    links.new(gravel.outputs['Color'], gravel_grade.inputs['Color'])
    sand_grade = nodes.new('ShaderNodeHueSaturation')
    sand_grade.inputs['Saturation'].default_value = 0.55
    sand_grade.inputs['Value'].default_value = 0.52
    links.new(sand.outputs['Color'], sand_grade.inputs['Color'])
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    links.new(attribute.outputs['Fac'], mix.inputs['Factor'])
    links.new(gravel_grade.outputs['Color'], mix.inputs[6])
    links.new(sand_grade.outputs['Color'], mix.inputs[7])
    # Contact darkening where plants and hardscape meet the ground.
    shade = nodes.new('ShaderNodeAttribute')
    shade.attribute_name = 'shade'
    darken = nodes.new('ShaderNodeMix')
    darken.data_type = 'RGBA'
    darken.blend_type = 'MULTIPLY'
    links.new(shade.outputs['Fac'], darken.inputs['Factor'])
    links.new(mix.outputs[2], darken.inputs[6])
    darken.inputs[7].default_value = (0.12, 0.14, 0.14, 1)
    links.new(darken.outputs[2], bsdf.inputs['Base Color'])
    normal_mix = nodes.new('ShaderNodeMix')
    normal_mix.data_type = 'RGBA'
    links.new(attribute.outputs['Fac'], normal_mix.inputs['Factor'])
    links.new(gravel_n.outputs['Color'], normal_mix.inputs[6])
    links.new(sand_n.outputs['Color'], normal_mix.inputs[7])
    normal_map = nodes.new('ShaderNodeNormalMap')
    normal_map.inputs['Strength'].default_value = 0.8
    links.new(normal_mix.outputs[2], normal_map.inputs['Color'])
    links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
    add_caustics(material, 0.35)
    return material


def bark_material():
    material, bsdf = principled('driftwood', (0.09, 0.06, 0.04), 0.7)
    if CLAY:
        return material
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    uv = nodes.new('ShaderNodeUVMap')
    mapping = nodes.new('ShaderNodeMapping')
    links.new(uv.outputs['UV'], mapping.inputs['Vector'])
    bark = nodes.new('ShaderNodeTexImage')
    bark.image = image(SRC / 'dry_branches_medium_01' / 'textures' / 'dry_branches_medium_01_diff_2k.jpg')
    links.new(mapping.outputs['Vector'], bark.inputs['Vector'])
    bark_n = nodes.new('ShaderNodeTexImage')
    bark_n.image = image(SRC / 'dry_branches_medium_01' / 'textures' / 'dry_branches_medium_01_nor_gl_2k.jpg', 'Non-Color')
    links.new(mapping.outputs['Vector'], bark_n.inputs['Vector'])
    # Waterlogged: darker, less saturated, fibres along the branch.
    fibre_map = nodes.new('ShaderNodeMapping')
    fibre_map.inputs['Scale'].default_value = (18.0, 1.2, 1.0)
    links.new(uv.outputs['UV'], fibre_map.inputs['Vector'])
    fibres = nodes.new('ShaderNodeTexNoise')
    fibres.inputs['Scale'].default_value = 3.0
    fibres.inputs['Detail'].default_value = 6.0
    links.new(fibre_map.outputs['Vector'], fibres.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.035, 0.025, 0.018, 1)
    ramp.color_ramp.elements[1].color = (0.16, 0.11, 0.072, 1)
    links.new(fibres.outputs['Fac'], ramp.inputs['Fac'])
    grade = nodes.new('ShaderNodeHueSaturation')
    grade.inputs['Saturation'].default_value = 0.7
    grade.inputs['Value'].default_value = 0.55
    links.new(bark.outputs['Color'], grade.inputs['Color'])
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 0.85
    links.new(ramp.outputs['Color'], mix.inputs[6])
    links.new(grade.outputs['Color'], mix.inputs[7])
    bright = nodes.new('ShaderNodeMath')
    bright.operation = 'MULTIPLY'
    boost = nodes.new('ShaderNodeMix')
    boost.data_type = 'RGBA'
    boost.blend_type = 'MULTIPLY'
    boost.inputs['Factor'].default_value = 1.0
    boost.inputs[7].default_value = (2.6, 2.4, 2.2, 1)
    links.new(mix.outputs[2], boost.inputs[6])
    links.new(boost.outputs[2], bsdf.inputs['Base Color'])
    normal_map = nodes.new('ShaderNodeNormalMap')
    normal_map.inputs['Strength'].default_value = 1.2
    links.new(bark_n.outputs['Color'], normal_map.inputs['Color'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    links.new(fibres.outputs['Fac'], bump.inputs['Height'])
    links.new(normal_map.outputs['Normal'], bump.inputs['Normal'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    add_caustics(material, 0.4)
    return material


def plant_material(name, color, roughness=0.45, translucency=0.35, sheen=0.0):
    """Aquatic leaf: vertex-tinted, wet, with thin-tissue translucency."""
    material, bsdf = principled(name, color, roughness)
    if CLAY:
        return material
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    tint = nodes.new('ShaderNodeVertexColor')
    tint.layer_name = 'tint'
    base = nodes.new('ShaderNodeMix')
    base.data_type = 'RGBA'
    base.blend_type = 'MULTIPLY'
    base.inputs['Factor'].default_value = 1.0
    base.inputs[6].default_value = (*color, 1)
    links.new(tint.outputs['Color'], base.inputs[7])
    links.new(base.outputs[2], bsdf.inputs['Base Color'])
    bsdf.inputs['Specular IOR Level'].default_value = 0.55
    if sheen:
        bsdf.inputs['Coat Weight'].default_value = sheen
        bsdf.inputs['Coat Roughness'].default_value = 0.25
    translucent = nodes.new('ShaderNodeBsdfTranslucent')
    links.new(base.outputs[2], translucent.inputs['Color'])
    shader_mix = nodes.new('ShaderNodeMixShader')
    shader_mix.inputs['Fac'].default_value = translucency
    output = nodes['Material Output']
    links.new(bsdf.outputs['BSDF'], shader_mix.inputs[1])
    links.new(translucent.outputs['BSDF'], shader_mix.inputs[2])
    links.new(shader_mix.outputs['Shader'], output.inputs['Surface'])
    add_caustics(material, 0.05)
    return material


def clay_material():
    material, bsdf = principled('clay', (0.42, 0.42, 0.4), 0.8)
    return material


# ==========================================================================
# Substrate
# ==========================================================================

HARDSCAPE_POINTS = []   # (x, z, radius) contact shadows for the substrate


def build_substrate(columns=320, rows=150):
    x0, x1, z0, z1 = -13.0, 13.0, -9.5, 2.7
    bm = bmesh.new()
    path_layer = bm.verts.layers.float.new('path')
    shade_layer = bm.verts.layers.float.new('shade')
    grid = []
    for row in range(rows + 1):
        z = z0 + (z1 - z0) * row / rows
        line = []
        for column in range(columns + 1):
            x = x0 + (x1 - x0) * column / columns
            vert = bm.verts.new(B(x, surface_y(x, z), z))
            vert[path_layer] = 0.7 * path_mask(x, z)
            shade = 0.0
            for hx, hz, radius in HARDSCAPE_POINTS:
                shade = max(shade, math.exp(-((x - hx) ** 2 + (z - hz) ** 2) / (radius * radius)))
            vert[shade_layer] = min(1.0, max(shade * 0.85, smoothstep(0.2, -2.7, z)))
            line.append(vert)
        grid.append(line)
    for row in range(rows):
        for column in range(columns):
            bm.faces.new((grid[row][column], grid[row][column + 1],
                          grid[row + 1][column + 1], grid[row + 1][column]))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    obj = mesh_object('substrate', bm)
    # bmesh float layers become mesh attributes named after the layer.
    return obj


# ==========================================================================
# Hardscape: rocks
# ==========================================================================

# Stage 1 scanned rock family (Poly Haven CC0): primaries and front
# secondaries swap to dark weathered scans; transition and secondary stones
# stay rock_moss_set_02. Values: source, target height (habitat units).
SCANNED_ROCKS = {
    0: ('rock_07', 1.35),      # primary, rear left
    1: ('boulder_01', 1.2),    # primary, rear centre-left
    2: ('rock_09', 0.5),       # secondary, front
    3: ('rock_09', 0.42),      # secondary, front left
}


def grade_scan_material(material, saturation, value, caustics):
    if material is None or CLAY or not material.use_nodes:
        return
    tree = material.node_tree
    bsdf = tree.nodes.get('Principled BSDF')
    if bsdf is None:
        return
    base_link = next((l for l in tree.links if l.to_socket == bsdf.inputs['Base Color']), None)
    if base_link is not None:
        grade = tree.nodes.new('ShaderNodeHueSaturation')
        grade.inputs['Saturation'].default_value = saturation
        grade.inputs['Value'].default_value = value
        tree.links.new(base_link.from_socket, grade.inputs['Color'])
        tree.links.new(grade.outputs['Color'], bsdf.inputs['Base Color'])
    add_caustics(material, caustics)


def join_meshes(parts):
    target = parts[0]
    if len(parts) > 1:
        with bpy.context.temp_override(active_object=target, object=target, selected_editable_objects=parts,
                                       selected_objects=parts):
            bpy.ops.object.join()
    return target


def build_scanned_rock(asset_id, x, z, target_height, yaw, sink, tilt, name):
    rock = join_meshes(list(import_asset(asset_id).values()))
    height = recenter_on_base(rock)
    scale = target_height / height
    rock.data.transform(Matrix.Translation(B(x, surface_y(x, z) - sink * target_height, z))
                        @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
                        @ Matrix.Rotation(math.radians(tilt), 4, 'X')
                        @ Matrix.Scale(scale, 4))
    rock.name = name
    for material in rock.data.materials:
        grade_scan_material(material, 0.75, 0.95, 0.45)
    log(f'scanned rock {asset_id}: {len(rock.data.polygons)} faces')
    return rock


def build_rocks():
    sources = import_asset('rock_moss_set_02')
    heights = {name: recenter_on_base(obj) for name, obj in sources.items()}
    material = None
    parts = []
    for index, (key, x, z, scale, yaw, sink, tilt) in enumerate(V['rocks']):
        if ARGS.rocks == 'scanned' and index in SCANNED_ROCKS:
            asset_id, target = SCANNED_ROCKS[index]
            parts.append(build_scanned_rock(asset_id, x, z, target, yaw, sink, tilt, f'scan-{asset_id}-{index}'))
            HARDSCAPE_POINTS.append((x, z, 0.9 * target * 1.3))
            continue
        name = f'rock_moss_set_02_{key}'
        rock = sources[name].copy()
        rock.data = sources[name].data.copy()
        link(rock)
        scale *= ROCK_SCALE
        height = heights[name] * scale
        matrix = (Matrix.Translation(B(x, surface_y(x, z) - sink * height, z))
                  @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
                  @ Matrix.Rotation(math.radians(tilt), 4, 'X')
                  @ Matrix.Scale(scale, 4))
        rock.data.transform(matrix)
        parts.append(rock)
        HARDSCAPE_POINTS.append((x, z, 0.75 * scale * 1.3))
    # Small transition stones: a trail from the hardscape into the clearing.
    small = sources['rock_moss_set_02_rock08']
    stones = [(-0.2, 0.95, 0.09), (0.15, 0.75, 0.06), (-0.95, 1.1, 0.075), (0.45, 1.35, 0.05),
              (-1.35, 0.35, 0.1), (-0.05, 0.2, 0.07), (1.25, -0.6, 0.06), (1.7, 0.4, 0.045),
              (-3.5, 0.3, 0.1), (-2.35, 0.9, 0.08), (0.8, -1.4, 0.05), (2.6, -1.1, 0.07)]
    for index, (x, z, scale) in enumerate(stones):
        stone = small.copy()
        stone.data = small.data.copy()
        link(stone)
        height = heights['rock_moss_set_02_rock08'] * scale
        matrix = (Matrix.Translation(B(x, surface_y(x, z) - 0.4 * height, z))
                  @ Matrix.Rotation(RNG.uniform(0, math.tau), 4, 'Z')
                  @ Matrix.Rotation(math.radians(RNG.uniform(-20, 20)), 4, 'X')
                  @ Matrix.Scale(scale, 4))
        stone.data.transform(matrix)
        parts.append(stone)
    for obj in sources.values():
        material = material or (obj.data.materials[0] if obj.data.materials else None)
        bpy.data.objects.remove(obj)
    if material is not None and not CLAY:
        tree = material.node_tree
        bsdf = tree.nodes.get('Principled BSDF')
        base_link = next((l for l in tree.links if l.to_socket == bsdf.inputs['Base Color']), None)
        if base_link is not None:
            grade = tree.nodes.new('ShaderNodeHueSaturation')
            grade.inputs['Saturation'].default_value = 0.65
            grade.inputs['Value'].default_value = 0.72
            tree.links.new(base_link.from_socket, grade.inputs['Color'])
            tree.links.new(grade.outputs['Color'], bsdf.inputs['Base Color'])
        add_caustics(material, 0.45)
    log(f'rocks: {len(parts)} pieces')
    return parts


# ==========================================================================
# Hardscape: driftwood root (procedural tubes with bark UVs)
# ==========================================================================

JOINTS = []   # branch junction points for moss
ROCK_SCALE = 1.45
WOOD_GIRTH = 2.3


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


def tube(bm, uv_layer, spine, radii, sides=9, seed=0.0):
    """Tube along a spine with parallel-transported frames and gnarled radius."""
    rings = []
    length = 0.0
    tangent_prev = (spine[1] - spine[0]).normalized()
    normal = tangent_prev.orthogonal().normalized()
    for index, point in enumerate(spine):
        if index > 0:
            length += (point - spine[index - 1]).length
        if index < len(spine) - 1:
            tangent = (spine[index + 1] - point).normalized()
        else:
            tangent = tangent_prev
        axis = tangent_prev.cross(tangent)
        if axis.length > 1e-6:
            angle = tangent_prev.angle(tangent)
            normal = Matrix.Rotation(angle, 3, axis.normalized()) @ normal
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
    out = []
    for x, y, z in points:
        out.append((x, surface_y(x, z) - sink if y is None else y, z))
    return out


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


def taper(samples, base, tip, bulge_seed):
    radii = []
    for index in range(samples + 1):
        t = index / samples
        r = tip + (base - tip) * (1 - t) ** 1.35
        r *= 1.0 + 0.18 * max(0.0, noise.noise(Vector((t * 5.0, bulge_seed, 0.0))))
        radii.append(r)
    return radii


def build_scanned_root(path):
    """Stage 1: a scanned root replaces the procedural wood, placed at the
    same base in the same envelope. Its own material is kept and graded
    toward waterlogged driftwood; both candidates get the same treatment."""
    path = pathlib.Path(path)
    before = set(bpy.data.objects)
    suffix = path.suffix.lower()
    if suffix in ('.gltf', '.glb'):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif suffix == '.obj':
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise SystemExit(f'unsupported root format: {path}')
    created = [obj for obj in set(bpy.data.objects) - before]
    meshes = [obj for obj in created if obj.type == 'MESH']
    for obj in meshes:
        matrix = obj.matrix_world.copy()
        obj.parent = None
        obj.data.transform(matrix)
        obj.matrix_world = Matrix.Identity(4)
    for obj in created:
        if obj.type != 'MESH':
            bpy.data.objects.remove(obj)
    root = join_meshes(meshes)
    source_faces = len(root.data.polygons)
    root.data.transform(Matrix.Rotation(math.radians(ARGS.root_yaw), 4, 'Z')
                        @ Matrix.Rotation(math.radians(ARGS.root_tilt), 4, 'X')
                        @ Matrix.Rotation(math.radians(ARGS.root_roll), 4, 'Y'))
    height = recenter_on_base(root)
    x, z = (float(v) for v in ARGS.root_at.split(','))
    scale = ARGS.root_height / height
    root.data.transform(Matrix.Translation(B(x, surface_y(x, z) - ARGS.root_sink * ARGS.root_height, z))
                        @ Matrix.Scale(scale, 4))
    root.name = 'scanned-root'
    for material in root.data.materials:
        grade_scan_material(material, 0.75, 0.55, 0.35)
    # Moss and epiphytes keep the same joint-weighted sampling: upper
    # surface points of the scan stand in for branch junctions.
    verts = root.data.vertices
    step = max(1, len(verts) // 400)
    tops = sorted((v.co.copy() for v in verts[::step]), key=lambda co: -co.z)
    JOINTS.extend(tops[len(tops) // 6: len(tops) // 2: max(1, len(tops) // 40)])
    HARDSCAPE_POINTS.append((x, z, 0.9))
    dims = root.dimensions
    log(f'root: {source_faces} source faces, {len(verts)} verts, {len(root.data.materials)} materials, '
        f'dims {dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f}')
    return root


def bark_willow_material():
    """Stage 1 B: scanned bark (Poly Haven bark_willow_02, CC0) on the
    procedural root, with restrained weathering: fibre-aligned cracks and
    darker waterlogged tone. Same UVs as before (u around, v along grain)."""
    material, bsdf = principled('driftwood-willow', (0.1, 0.07, 0.05), 0.75)
    if CLAY:
        return material
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    folder = SRC / 'bark_willow_02' / 'textures'
    uv = nodes.new('ShaderNodeUVMap')
    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (1.0, 0.8, 1.0)
    links.new(uv.outputs['UV'], mapping.inputs['Vector'])

    def tex(name, colorspace='sRGB'):
        node = nodes.new('ShaderNodeTexImage')
        node.image = image(folder / f'bark_willow_02_{name}_2k.jpg', colorspace)
        links.new(mapping.outputs['Vector'], node.inputs['Vector'])
        return node
    diffuse, normal_tex, arm = tex('diff'), tex('nor_gl', 'Non-Color'), tex('arm', 'Non-Color')
    # Cracks: stretched Voronoi edges following the grain.
    crack_map = nodes.new('ShaderNodeMapping')
    crack_map.inputs['Scale'].default_value = (6.0, 0.9, 1.0)
    links.new(uv.outputs['UV'], crack_map.inputs['Vector'])
    voronoi = nodes.new('ShaderNodeTexVoronoi')
    voronoi.feature = 'DISTANCE_TO_EDGE'
    voronoi.inputs['Scale'].default_value = 4.0
    links.new(crack_map.outputs['Vector'], voronoi.inputs['Vector'])
    crack = nodes.new('ShaderNodeMapRange')
    crack.inputs['From Min'].default_value = 0.0
    crack.inputs['From Max'].default_value = 0.035
    crack.inputs['To Min'].default_value = 0.45
    crack.inputs['To Max'].default_value = 1.0
    links.new(voronoi.outputs['Distance'], crack.inputs['Value'])
    grade = nodes.new('ShaderNodeHueSaturation')
    grade.inputs['Saturation'].default_value = 0.8
    grade.inputs['Value'].default_value = 0.42
    links.new(diffuse.outputs['Color'], grade.inputs['Color'])
    # Pale willow bark -> waterlogged driftwood brown (same target tone as
    # the approved Pass 2 wood).
    warm = nodes.new('ShaderNodeMix')
    warm.data_type = 'RGBA'
    warm.blend_type = 'MULTIPLY'
    warm.inputs[0].default_value = 1.0
    warm.inputs[7].default_value = (0.95, 0.72, 0.52, 1.0)
    links.new(grade.outputs['Color'], warm.inputs[6])
    grade = warm
    darken = nodes.new('ShaderNodeMix')
    darken.data_type = 'RGBA'
    darken.blend_type = 'MULTIPLY'
    darken.inputs[0].default_value = 1.0
    links.new(grade.outputs[2] if grade.bl_idname == 'ShaderNodeMix' else grade.outputs['Color'], darken.inputs[6])
    links.new(crack.outputs['Result'], darken.inputs[7])
    links.new(darken.outputs[2], bsdf.inputs['Base Color'])
    separate = nodes.new('ShaderNodeSeparateColor')
    links.new(arm.outputs['Color'], separate.inputs['Color'])
    links.new(separate.outputs['Green'], bsdf.inputs['Roughness'])
    normal_map = nodes.new('ShaderNodeNormalMap')
    normal_map.inputs['Strength'].default_value = 1.3
    links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.4
    links.new(crack.outputs['Result'], bump.inputs['Height'])
    links.new(normal_map.outputs['Normal'], bump.inputs['Normal'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    add_caustics(material, 0.4)
    return material


def extract_root_strips(obj, lift=0.012, cell=0.05, min_length=0.18):
    """Cut the raised root ridges out of a Poly Haven ground-patch scan:
    faces whose vertices sit more than `lift` above the local soil level."""
    import bmesh as _bm
    mesh = obj.data
    coords = [v.co.copy() for v in mesh.vertices]
    cells = {}
    for co in coords:
        cells.setdefault((int(co.x // cell), int(co.y // cell)), []).append(co.z)
    ground = {}
    for (cx, cy) in cells:
        zs = []
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                zs.extend(cells.get((cx + dx, cy + dy), []))
        zs.sort()
        ground[(cx, cy)] = zs[len(zs) // 5]
    raised = [co.z - ground[(int(co.x // cell), int(co.y // cell))] > lift for co in coords]
    bm = _bm.new()
    bm.from_mesh(mesh)
    doomed = [f for f in bm.faces if not all(raised[v.index] for v in f.verts)]
    _bm.ops.delete(bm, geom=doomed, context='FACES')
    # Connected components (pure bmesh; no edit-mode operators).
    bm.faces.ensure_lookup_table()
    seen = set()
    strips = []
    for face in bm.faces:
        if face.index in seen:
            continue
        stack, component = [face], []
        seen.add(face.index)
        while stack:
            current = stack.pop()
            component.append(current)
            for edge in current.edges:
                for other in edge.link_faces:
                    if other.index not in seen:
                        seen.add(other.index)
                        stack.append(other)
        if len(component) < 200:
            continue
        part = _bm.new()
        uv_src = bm.loops.layers.uv.active
        uv_dst = part.loops.layers.uv.new('UVMap') if uv_src else None
        remap = {}
        for f in component:
            verts = []
            for v in f.verts:
                if v.index not in remap:
                    remap[v.index] = part.verts.new(v.co)
                verts.append(remap[v.index])
            try:
                nf = part.faces.new(verts)
            except ValueError:
                continue
            nf.smooth = True
            if uv_src:
                for dst, src in zip(nf.loops, f.loops):
                    dst[uv_dst].uv = src[uv_src].uv
        new_mesh = bpy.data.meshes.new(f'{obj.name}-strip')
        part.to_mesh(new_mesh)
        part.free()
        for material in mesh.materials:
            new_mesh.materials.append(material)
        strip = link(bpy.data.objects.new(f'{obj.name}-strip', new_mesh))
        if max(strip.dimensions.x, strip.dimensions.y) >= min_length:
            strips.append(strip)
        else:
            bpy.data.objects.remove(strip)
    bm.free()
    bpy.data.objects.remove(obj)
    return strips


def align_strip_to_x(strip):
    """Principal (long) axis of the strip onto +X, base end at the origin."""
    verts = strip.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    if max(ys) - min(ys) > max(xs) - min(xs):
        strip.data.transform(Matrix.Rotation(math.radians(90), 4, 'Z'))
    xs = [v.co.x for v in verts]
    cy = sum(v.co.y for v in verts) / len(verts)
    zmin = min(v.co.z for v in verts)
    strip.data.transform(Matrix.Translation(Vector((-min(xs), -cy, -zmin))))
    return max(xs) - min(xs)


def bend_strip_along(strip, spine, girth_scale):
    """Minimal intervention: scale to the gesture length and bend along its
    spine with a Curve modifier (no sculpting, no invented undersides)."""
    length = align_strip_to_x(strip)
    curve_length = sum((b - a).length for a, b in zip(spine, spine[1:]))
    strip.data.transform(Matrix.Diagonal((curve_length / length, girth_scale, girth_scale, 1.0)))
    curve_data = bpy.data.curves.new(f'{strip.name}-path', 'CURVE')
    curve_data.dimensions = '3D'
    spline = curve_data.splines.new('POLY')
    spline.points.add(len(spine) - 1)
    for point, co in zip(spline.points, spine):
        point.co = (co.x, co.y, co.z, 1.0)
    curve = link(bpy.data.objects.new(f'{strip.name}-path', curve_data))
    modifier = strip.modifiers.new('bend', 'CURVE')
    modifier.object = curve
    modifier.deform_axis = 'POS_X'
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(strip.evaluated_get(depsgraph), depsgraph=depsgraph)
    strip.modifiers.clear()
    old = strip.data
    strip.data = mesh
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(curve)
    return strip


def build_scan_strip_root():
    """Stage 1 A: scanned root geometry recombined into the approved
    three-gesture envelope with minimal intervention."""
    sources = []
    for asset in ('root_cluster_02', 'single_root'):
        sources.extend(import_asset(asset).values())
    source_faces = sum(len(o.data.polygons) for o in sources)
    strips = []
    for obj in sources:
        strips.extend(extract_root_strips(obj))
    strips.sort(key=lambda o: -max(o.dimensions.x, o.dimensions.y))
    log(f'scan strips: {len(strips)} ridges from {source_faces} source faces; '
        f'longest {max(strips[0].dimensions.x, strips[0].dimensions.y):.2f} m')
    targets = []
    for index, (points, base, tip) in enumerate(V['wood']):
        spine = catmull([B(*p) for p in resolve(points, 0.22)], 24)
        targets.append((spine, base * WOOD_GIRTH))
        JOINTS.append(spine[0])
    for points in V['roots']:
        spine = catmull([B(*p) for p in resolve(points, 0.035)], 12)
        targets.append((spine, 0.09))
    parts = []
    for (spine, radius), strip in zip(targets, strips):
        width = min(strip.dimensions.x, strip.dimensions.y)
        parts.append(bend_strip_along(strip, spine, (2 * radius) / max(width, 1e-3)))
    for leftover in strips[len(targets):]:
        bpy.data.objects.remove(leftover)
    wood = join_meshes(parts)
    wood.name = 'scan-strip-root'
    for material in wood.data.materials:
        grade_scan_material(material, 0.75, 0.6, 0.35)
    knot_x, knot_z = V['knot']
    HARDSCAPE_POINTS.append((knot_x, knot_z, 0.7))
    log(f'scan-strip root: {len(wood.data.polygons)} faces in {len(parts)} bent ridges')
    return wood


def build_wood():
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new('UVMap')
    branches = []
    for index, (points, base, tip) in enumerate(V['wood']):
        spine = spine_from(resolve(points, 0.22), 44, 0.15, index * 3.7)
        radii = taper(44, base * WOOD_GIRTH, tip * 1.5, index * 1.3)
        tube(bm, uv_layer, spine, radii, sides=10, seed=index * 2.1)
        branches.append((spine, radii))
        JOINTS.append(spine[0])
    for index, points in enumerate(V['roots']):
        spine = spine_from(resolve(points, 0.035), 18, 0.04, 20 + index)
        radii = taper(18, 0.09, 0.02, 40 + index)
        tube(bm, uv_layer, spine, radii, sides=8, seed=30 + index)
    # Twigs: forks off the main branches, thinning to fine tips.
    twig_rng = random.Random(7)
    for spine, radii in branches:
        count = 3
        for _ in range(count):
            k = twig_rng.randint(int(len(spine) * 0.3), int(len(spine) * 0.85))
            origin = spine[k]
            tangent = (spine[min(k + 1, len(spine) - 1)] - spine[k - 1]).normalized()
            side = tangent.cross(Vector((0, 1, 0))).normalized() * twig_rng.choice((-1, 1))
            up = Vector((0, 0, 1))
            direction = (tangent * 0.7 + side * twig_rng.uniform(0.2, 0.7) + up * twig_rng.uniform(0.1, 0.6)).normalized()
            length = twig_rng.uniform(0.35, 0.7) if twig_rng.random() < 0.5 else twig_rng.uniform(0.1, 0.18)
            base_r = radii[k] * 0.55
            points = [origin, origin + direction * length * 0.5 + up * 0.05,
                      origin + direction * length + noise.noise_vector(origin * 3) * 0.08]
            raw = catmull(points, 16)
            tube(bm, uv_layer, raw, taper(16, base_r, max(0.012, base_r * (0.2 if length > 0.3 else 0.45)), k), sides=7, seed=k * 0.7)
            JOINTS.append(origin)
    # Tips fork into finer twigs instead of ending in a single point.
    for spine, radii in branches[:2]:
        for fork in range(2):
            k = int(len(spine) * twig_rng.uniform(0.78, 0.9))
            origin = spine[k]
            tangent = (spine[k + 1] - spine[k - 1]).normalized()
            side = tangent.cross(Vector((0, 1, 0))).normalized() * (1 if fork else -1)
            direction = (tangent + side * twig_rng.uniform(0.35, 0.8) + Vector((0, 0, twig_rng.uniform(0.0, 0.4)))).normalized()
            length = twig_rng.uniform(0.14, 0.26)
            raw = catmull([origin, origin + direction * length * 0.5, origin + direction * length
                           + noise.noise_vector(origin * 5) * 0.05], 12)
            tube(bm, uv_layer, raw, taper(12, radii[k] * 0.6, 0.009, k + fork), sides=6, seed=k + fork)
    bm.normal_update()
    obj = mesh_object('driftwood', bm)
    knot_x, knot_z = V['knot']
    HARDSCAPE_POINTS.append((knot_x, knot_z, 0.7))
    log(f'wood: {len(obj.data.polygons)} faces')
    return obj


# ==========================================================================
# Moss (CC0 moss_01 sprigs) on upper wood/rock surfaces, near joints and
# rock/wood transitions.
# ==========================================================================

def sample_surfaces(objects, count, weight_fn, min_up=0.25):
    triangles = []
    for obj in objects:
        mesh = obj.data
        mesh.calc_loop_triangles()
        matrix = obj.matrix_world
        for tri in mesh.loop_triangles:
            normal = (matrix.to_3x3() @ tri.normal).normalized()
            if normal.z < min_up:
                continue
            a, b, c = (matrix @ mesh.vertices[i].co for i in tri.vertices)
            centre = (a + b + c) / 3
            w = tri.area * normal.z ** 2 * weight_fn(centre)
            if w > 0:
                triangles.append((w, a, b, c, normal))
    total = sum(t[0] for t in triangles)
    cumulative = []
    acc = 0.0
    for t in triangles:
        acc += t[0]
        cumulative.append(acc)
    import bisect
    out = []
    for _ in range(count):
        i = min(bisect.bisect_left(cumulative, RNG.uniform(0, total)), len(triangles) - 1)
        _, a, b, c, normal = triangles[i]
        r1, r2 = RNG.random(), RNG.random()
        if r1 + r2 > 1:
            r1, r2 = 1 - r1, 1 - r2
        out.append((a + (b - a) * r1 + (c - a) * r2, normal))
    return out


def build_moss(wood, rocks, count):
    sources = list(import_asset('moss_01').values())
    for obj in sources:
        recenter_on_base(obj)
    wood_top = max(v.co.z for v in wood.data.vertices)

    def weight(p):
        near_joint = max((math.exp(-((p - j).length ** 2) / 0.12) for j in JOINTS), default=0.0)
        low = 1.0 - smoothstep(FLOOR + 0.2, FLOOR + 2.2, p.z)      # more moss low down
        return 0.45 + 1.2 * near_joint + 0.8 * low
    samples = sample_surfaces([wood] + rocks, count, weight)
    bm = bmesh.new()
    parts = []
    for index, (point, normal) in enumerate(samples):
        source = RNG.choice(sources)
        sprig = source.copy()
        sprig.data = source.data
        align = Vector((0, 0, 1)).rotation_difference(normal.lerp(Vector((0, 0, 1)), 0.5))
        sprig.matrix_world = (Matrix.Translation(point - normal * 0.01) @ align.to_matrix().to_4x4()
                              @ Matrix.Rotation(RNG.uniform(0, math.tau), 4, 'Z')
                              @ Matrix.Scale(RNG.uniform(6.0, 11.0), 4))
        link(sprig)
        parts.append(sprig)
    for obj in sources:
        obj.hide_render = True
        obj.hide_viewport = True
    if not CLAY:
        # Own material from the source maps: the importer's combined
        # diffuse+alpha image does not cut out in EEVEE here.
        material = bpy.data.materials.new('moss')
        material.use_nodes = True
        try_set(material, 'surface_render_method', 'DITHERED')
        tree = material.node_tree
        bsdf = tree.nodes['Principled BSDF']
        textures = SRC / 'moss_01' / 'textures'
        diffuse = tree.nodes.new('ShaderNodeTexImage')
        diffuse.image = image(textures / 'moss_01_diff_2k.jpg')
        alpha = tree.nodes.new('ShaderNodeTexImage')
        alpha.image = image(textures / 'moss_01_alpha_2k.png', 'Non-Color')
        grade = tree.nodes.new('ShaderNodeHueSaturation')
        grade.inputs['Hue'].default_value = 0.53
        grade.inputs['Saturation'].default_value = 0.9
        grade.inputs['Value'].default_value = 0.9
        tree.links.new(diffuse.outputs['Color'], grade.inputs['Color'])
        tree.links.new(grade.outputs['Color'], bsdf.inputs['Base Color'])
        tree.links.new(alpha.outputs['Color'], bsdf.inputs['Alpha'])
        bsdf.inputs['Roughness'].default_value = 0.6
        for obj in sources:
            obj.data.materials.clear()
            obj.data.materials.append(material)
    log(f'moss: {len(parts)} sprigs')
    return parts


# ==========================================================================
# Procedural aquatic vegetation
# ==========================================================================

def add_leaf(bm, tint_layer, base, direction, normal_hint, length, width, shape, arch=0.25,
             fold=0.25, rows=6, tint=(1, 1, 1), wave=0.0, twist=0.0):
    """One leaf blade: folded along the midrib and arched along its length."""
    direction = direction.normalized()
    side = direction.cross(normal_hint)
    if side.length < 1e-5:
        side = direction.orthogonal()
    side.normalize()
    up = side.cross(direction).normalized()
    columns = [-1.0, -0.5, 0.0, 0.5, 1.0]
    grid = []
    for row in range(rows + 1):
        t = row / rows
        half = width * 0.5 * shape(t)
        along = direction * (length * t)
        droop = up * (-arch * length * t * t)
        line = []
        rot = twist * t
        side_t = side * math.cos(rot) + up * math.sin(rot)
        up_t = up * math.cos(rot) - side * math.sin(rot)
        for c in columns:
            lateral = side_t * (c * half)
            lift = up_t * (abs(c) * half * fold) + up_t * (wave * half * math.sin(t * 18 + c * 2))
            line.append(bm.verts.new(base + along + droop + lateral + lift))
        grid.append(line)
    shade = 0.85 + 0.15 * RNG.random()
    for row in range(rows):
        for c in range(len(columns) - 1):
            face = bm.faces.new((grid[row][c], grid[row][c + 1], grid[row + 1][c + 1], grid[row + 1][c]))
            for loop in face.loops:
                edge = abs(columns[c]) * 0.1
                loop[tint_layer] = (tint[0] * shade * (1 - edge), tint[1] * shade, tint[2] * shade * (1 - edge), 1)


def ellipse(t):
    return math.sin(math.pi * min(1.0, t ** 0.85)) ** 0.8 if t < 1 else 0.0


def lance(t):
    return math.sin(math.pi * t ** 0.6) ** 1.2 * (1 - t) ** 0.3


def ribbon_shape(t):
    return 1.0 - 0.7 * t ** 3


def blade(t):
    return (1 - t) ** 0.9


def roundish(t):
    return math.sin(math.pi * t) ** 0.6


def stem_strip(bm, tint_layer, points, width, tint):
    """Thin two-sided stem as a narrow strip facing the camera."""
    cam = B(*CAMERA)
    verts = []
    for p in points:
        view = (cam - p).normalized()
        tangent = Vector((0, 0, 1))
        side = tangent.cross(view).normalized() * width * 0.5
        verts.append((bm.verts.new(p - side), bm.verts.new(p + side)))
    for (a, b), (c, d) in zip(verts, verts[1:]):
        face = bm.faces.new((a, b, d, c))
        for loop in face.loops:
            loop[tint_layer] = (*tint, 1)


def plant_object(name, builder, material):
    bm = bmesh.new()
    tint_layer = color_attribute(bm)
    builder(bm, tint_layer)
    bm.normal_update()
    obj = mesh_object(name, bm)
    obj.data.materials.append(material)
    log(f'{name}: {len(obj.data.polygons)} faces')
    return obj


def jitter_tint(base, amount=0.12):
    return tuple(max(0.0, c * (1 + RNG.uniform(-amount, amount))) for c in base)


def anubias_rosette(bm, tint_layer, x, z, scale=1.0, y=None, leaves=None, lean=None):
    y = surface_y(x, z) if y is None else y
    base = B(x, y, z)
    leaves = leaves or RNG.randint(5, 9)
    lean = lean or Vector((0, 0, 1))
    for i in range(leaves):
        angle = RNG.uniform(0, math.tau)
        out = Vector((math.cos(angle), math.sin(angle), 0))
        elevation = RNG.uniform(0.35, 0.95)
        petiole_len = RNG.uniform(0.06, 0.16) * scale
        petiole_dir = (out * (1 - elevation) + Vector((0, 0, elevation)) + lean * 0.3).normalized()
        start = base + petiole_dir * petiole_len
        stem_strip(bm, tint_layer, [base, start], 0.012 * scale, (0.5, 0.6, 0.4))
        leaf_dir = (petiole_dir + out * 0.6).normalized()
        length = RNG.uniform(0.22, 0.4) * scale
        add_leaf(bm, tint_layer, start, leaf_dir, Vector((0, 0, 1)), length, length * RNG.uniform(0.42, 0.55),
                 ellipse, arch=0.18, fold=0.18, rows=6, tint=jitter_tint((1.0, 1.0, 1.0), 0.15))


def buce_cluster(bm, tint_layer, point, normal, scale=1.0):
    for _ in range(RNG.randint(4, 7)):
        angle = RNG.uniform(0, math.tau)
        out = Vector((math.cos(angle), math.sin(angle), 0))
        direction = (normal * 0.8 + out * 0.6 + Vector((0, 0, 0.4))).normalized()
        length = RNG.uniform(0.1, 0.17) * scale
        add_leaf(bm, tint_layer, point, direction, Vector((0, 0, 1)), length, length * 0.38,
                 lance, arch=0.12, fold=0.2, rows=4, tint=jitter_tint((0.85, 0.95, 1.0), 0.15), wave=0.08)


def java_fern(bm, tint_layer, point, normal, scale=1.0):
    for _ in range(RNG.randint(6, 11)):
        angle = RNG.uniform(0, math.tau)
        out = Vector((math.cos(angle), math.sin(angle), 0))
        direction = (normal * 0.4 + out * 0.5 + Vector((0, 0, RNG.uniform(0.5, 1.1)))).normalized()
        length = RNG.uniform(0.35, 0.75) * scale
        add_leaf(bm, tint_layer, point, direction, Vector((0, 0, 1)), length, length * 0.16,
                 lance, arch=0.3, fold=0.1, rows=8, tint=jitter_tint((1.0, 1.0, 1.0), 0.12),
                 wave=0.12, twist=RNG.uniform(-0.6, 0.6))


def crypt_rosette(bm, tint_layer, x, z, scale=1.0):
    base = B(x, surface_y(x, z), z)
    for _ in range(RNG.randint(6, 10)):
        angle = RNG.uniform(0, math.tau)
        out = Vector((math.cos(angle), math.sin(angle), 0))
        direction = (out * RNG.uniform(0.3, 0.7) + Vector((0, 0, 1))).normalized()
        length = RNG.uniform(0.14, 0.26) * scale
        add_leaf(bm, tint_layer, base, direction, Vector((0, 0, 1)), length, length * 0.3,
                 lance, arch=0.35, fold=0.12, rows=5, tint=jitter_tint((1.05, 0.9, 0.7), 0.12), wave=0.15)


def stem_plant(bm, tint_layer, x, z, height, lean, top_tint, base_tint, leaf_len=0.085, per_whorl=3, width_ratio=0.22):
    base = B(x, surface_y(x, z) - 0.02, z)
    bend = Vector((lean[0], -lean[1], 0))
    whorls = max(8, int(height / 0.045))
    points = []
    for i in range(whorls + 1):
        t = i / whorls
        points.append(base + Vector((0, 0, height * t)) + bend * (t * t) * height
                      + noise.noise_vector(base * 2 + Vector((0, 0, t * 3))) * 0.02 * t)
    stem_strip(bm, tint_layer, points, 0.01, base_tint)
    for i, p in enumerate(points[1:], start=1):
        t = i / whorls
        tint = tuple(b + (c - b) * t ** 1.5 for b, c in zip(base_tint, top_tint))
        spin = RNG.uniform(0, math.tau)
        size = leaf_len * (0.6 + 0.5 * math.sin(math.pi * min(1.0, t * 1.1))) * (0.75 if t > 0.92 else 1.0)
        for k in range(per_whorl):
            angle = spin + k * math.tau / per_whorl
            out = Vector((math.cos(angle), math.sin(angle), 0))
            direction = (out + Vector((0, 0, 0.55 + 0.6 * t))).normalized()
            add_leaf(bm, tint_layer, p, direction, Vector((0, 0, 1)), size, size * width_ratio, lance,
                     arch=0.2, fold=0.0, rows=2, tint=jitter_tint(tint, 0.06))


def vallis_ribbon(bm, tint_layer, x, z, height, width, lean, tint):
    base = B(x, surface_y(x, z) - 0.02, z)
    segments = 18
    cam = B(*CAMERA)
    phase = RNG.uniform(0, math.tau)
    prev = None
    for i in range(segments + 1):
        t = i / segments
        p = (base + Vector((0, 0, height * t)) + Vector((lean[0], -lean[1], 0)) * height * t ** 2.6
             + Vector((math.sin(t * 4 + phase), 0, 0)) * 0.04 * t)
        view = (cam - p).normalized()
        twist = math.sin(t * 5 + phase) * 0.9
        side = Vector((0, 0, 1)).cross(view).normalized()
        side = side * math.cos(twist) + view * math.sin(twist)
        half = width * 0.5 * ribbon_shape(t)
        a, b = bm.verts.new(p - side * half), bm.verts.new(p + side * half)
        if prev:
            face = bm.faces.new((prev[0], prev[1], b, a))
            shade = 0.75 + 0.35 * t
            for loop in face.loops:
                loop[tint_layer] = (tint[0] * shade, tint[1] * shade, tint[2] * shade, 1)
        prev = (a, b)


def hairgrass_clump(bm, tint_layer, x, z, height):
    base_y = surface_y(x, z)
    for _ in range(RNG.randint(10, 18)):
        bx, bz = x + RNG.gauss(0, 0.03), z + RNG.gauss(0, 0.03)
        base = B(bx, base_y - 0.01, bz)
        angle = RNG.uniform(0, math.tau)
        out = Vector((math.cos(angle), math.sin(angle), 0))
        direction = (Vector((0, 0, 1)) + out * RNG.uniform(0.05, 0.4)).normalized()
        add_leaf(bm, tint_layer, base, direction, Vector((1, 0, 0)), height * RNG.uniform(0.6, 1.1), 0.012,
                 blade, arch=0.25, fold=0.0, rows=3, tint=jitter_tint((0.9, 1.05, 0.8), 0.1))


def carpet_patch(bm, tint_layer, cx, cz, rx, rz, density, cushion=0.06):
    """Monte-Carlo-like carpet: many small round leaves forming a low cushion."""
    area = math.pi * rx * rz
    count = int(area * density * 1.7 * ARGS.density)
    for _ in range(count):
        a = RNG.uniform(0, math.tau)
        r = math.sqrt(RNG.random())
        x, z = cx + math.cos(a) * r * rx, cz + math.sin(a) * r * rz
        if path_mask(x, z) > 0.35 or RNG.random() < smoothstep(0.55, 1.0, r):
            continue
        edge = 1 - r
        height = cushion * (0.25 + 0.75 * edge ** 0.6) * RNG.uniform(0.5, 1.0)
        centre = B(x, surface_y(x, z) + height, z)
        normal = (Vector((0, 0, 1)) + Vector((RNG.gauss(0, 0.45), RNG.gauss(0, 0.45), 0))).normalized()
        size = RNG.uniform(0.015, 0.024)
        tangent = normal.orthogonal().normalized()
        bitangent = normal.cross(tangent)
        ring = [bm.verts.new(centre + (tangent * math.cos(k * math.tau / 6) + bitangent * math.sin(k * math.tau / 6)) * size)
                for k in range(6)]
        middle = bm.verts.new(centre + normal * size * 0.15)
        shade = RNG.uniform(0.75, 1.1) * (0.8 + 0.3 * edge)
        tint = (0.85 * shade, 1.05 * shade, 0.75 * shade, 1)
        for k in range(6):
            face = bm.faces.new((middle, ring[k], ring[(k + 1) % 6]))
            for loop in face.loops:
                loop[tint_layer] = tint


def carpet_coverage(x, z):
    """Where the foreground carpet grows: dense around the hardscape base and
    the front left, thinning toward the right, never on the sand clearing."""
    left = 1.0 - smoothstep(-1.0, 3.2, x)
    front = 0.35 + 0.65 * smoothstep(-2.3, 0.2, z)
    base = 0.25 + 0.75 * left
    n = (noise.noise(Vector((x * 0.9, z * 1.3, 5.0))) + 0.5 * noise.noise(Vector((x * 2.6, z * 3.1, 9.0)))
         + 0.25 * noise.noise(Vector((x * 7.0, z * 7.0, 2.0))))
    organic = smoothstep(-0.3, 0.25, n + 0.3 * left)
    clearing = 1.0 - smoothstep(0.1, 0.5, path_mask(x, z))
    return base * front * organic * clearing


def carpet_field(bm, tint_layer, density):
    x0, x1, z0, z1 = -4.2, 4.2, -2.3, 2.3
    count = int((x1 - x0) * (z1 - z0) * density * ARGS.density)
    for _ in range(count):
        x, z = RNG.uniform(x0, x1), RNG.uniform(z0, z1)
        coverage = carpet_coverage(x, z)
        if RNG.random() > coverage:
            continue
        mound = 0.5 + 0.5 * noise.noise(Vector((x * 1.6, z * 1.6, 4.0)))
        height = 0.06 * coverage ** 0.7 * (0.5 + mound) * RNG.uniform(0.4, 1.0)
        centre = B(x, surface_y(x, z) + height, z)
        normal = (Vector((0, 0, 1)) + Vector((RNG.gauss(0, 0.45), RNG.gauss(0, 0.45), 0))).normalized()
        size = RNG.uniform(0.015, 0.024)
        tangent = normal.orthogonal().normalized()
        bitangent = normal.cross(tangent)
        ring = [bm.verts.new(centre + (tangent * math.cos(k * math.tau / 6) + bitangent * math.sin(k * math.tau / 6)) * size)
                for k in range(6)]
        middle = bm.verts.new(centre + normal * size * 0.15)
        shade = RNG.uniform(0.75, 1.1) * (0.75 + 0.35 * coverage)
        tint = (0.85 * shade, 1.05 * shade, 0.75 * shade, 1)
        for k in range(6):
            face = bm.faces.new((middle, ring[k], ring[(k + 1) % 6]))
            for loop in face.loops:
                loop[tint_layer] = tint


VEGETATION = {
    # Carpet patches: centre x, z, radius x, radius z, leaves per unit^2
    'carpet': {
        'A': [(-1.6, 1.1, 1.3, 0.55, 2400), (-0.2, 1.55, 0.7, 0.35, 2000), (1.9, 0.9, 1.0, 0.45, 1500)],
        'B': [(-2.3, 1.0, 1.1, 0.45, 2600), (-1.2, 1.25, 0.9, 0.4, 2600), (-3.2, 0.8, 0.7, 0.4, 2400),
              (-0.3, 1.6, 0.7, 0.35, 2200), (-1.7, 0.7, 0.6, 0.3, 2400), (1.6, 1.1, 0.8, 0.35, 1500),
              (2.7, 0.6, 0.9, 0.35, 1400), (1.0, 1.75, 0.5, 0.25, 1500), (3.4, 1.3, 0.7, 0.35, 1300),
              (-0.6, 0.3, 0.6, 0.3, 1800), (2.2, -0.6, 0.9, 0.4, 1200), (0.2, -0.9, 0.7, 0.35, 1400),
              (-0.8, -1.2, 0.8, 0.4, 1600), (3.3, -0.9, 0.7, 0.4, 1100)],
        'C': [(-1.2, 1.2, 1.6, 0.6, 2400), (1.6, 0.9, 1.1, 0.5, 1500)],
    },
}


def build_vegetation(rocks, wood):
    greens = plant_material('carpet-leaf', (0.075, 0.17, 0.05), roughness=0.5, translucency=0.3)
    anubias_mat = plant_material('broad-leaf', (0.05, 0.13, 0.045), roughness=0.3, translucency=0.15, sheen=0.35)
    fern_mat = plant_material('fern-leaf', (0.07, 0.15, 0.05), roughness=0.4, translucency=0.3)
    stem_mat = plant_material('stem-leaf', (0.12, 0.26, 0.07), roughness=0.45, translucency=0.4)
    vallis_mat = plant_material('ribbon-leaf', (0.1, 0.22, 0.07), roughness=0.4, translucency=0.45)
    grass_mat = plant_material('grass-blade', (0.12, 0.28, 0.08), roughness=0.5, translucency=0.35)
    crypt_mat = plant_material('crypt-leaf', (0.08, 0.13, 0.05), roughness=0.4, translucency=0.25)
    density = ARGS.density
    objects = []

    def carpet(bm, layer):
        if ARGS.variant == 'B':
            carpet_field(bm, layer, 4200)
            return
        for cx, cz, rx, rz, d in VEGETATION['carpet'][ARGS.variant]:
            carpet_patch(bm, layer, cx, cz, rx, rz, d)
    objects.append(plant_object('carpet', carpet, greens))

    def hairgrass(bm, layer):
        # Composed tufts: clusters of clumps along the clearing edges and a
        # midground layer, never an even scatter.
        clusters = [(0.9, 0.9, 7), (1.9, 0.35, 9), (2.8, 0.9, 6), (3.4, 0.2, 5), (0.35, -0.35, 6),
                    (1.2, -0.9, 8), (2.2, -1.3, 7), (-0.5, -1.1, 6), (3.1, -1.0, 6), (-0.2, 1.35, 4),
                    (1.55, 1.75, 4), (-1.0, -1.6, 5)]
        for cx, cz, n in clusters:
            peak = RNG.uniform(0.2, 0.4)
            for _ in range(int(n * density + 0.5)):
                x, z = cx + RNG.gauss(0, 0.16), cz + RNG.gauss(0, 0.12)
                if path_mask(x, z) > 0.45:
                    continue
                falloff = math.exp(-((x - cx) ** 2 + (z - cz) ** 2) / 0.05)
                hairgrass_clump(bm, layer, x, z, peak * (0.5 + 0.5 * falloff))
    objects.append(plant_object('hairgrass', hairgrass, grass_mat))

    def anubias(bm, layer):
        # Masses at the rock bases and where wood meets stone: they hide the
        # contact lines so wood, stone and plants read as one formation.
        spots = [(-2.35, 0.55, 1.0), (-1.6, 0.5, 0.9), (-2.8, 0.5, 0.85), (-1.3, 0.65, 0.75),
                 (-3.35, 0.4, 0.85), (-2.05, 0.7, 0.7), (-2.15, -0.2, 1.0),
                 (-2.75, -0.35, 0.9), (-1.35, -0.4, 0.8), (-3.45, -0.5, 0.8),
                 (-2.25, -0.62, 0.9), (-2.7, -0.62, 0.8), (-1.95, -0.4, 0.8), (-1.3, -0.7, 0.75),
                 (-3.3, -0.85, 0.8), (-1.15, -1.0, 0.7)]
        for x, z, s in spots:
            for _ in range(3):
                anubias_rosette(bm, layer, x + RNG.gauss(0, 0.08), z + RNG.gauss(0, 0.06), s * RNG.uniform(0.8, 1.1))
    objects.append(plant_object('broadleaf', anubias, anubias_mat))

    def crypts(bm, layer):
        # Small rosette groups: they break the clearing edges and carry the
        # left mass into the centre.
        groups = [(0.35, 0.8, 1), (1.25, 0.25, 2), (0.75, -0.6, 2), (1.7, -0.1, 1)]
        for cx, cz, n in groups:
            for _ in range(n):
                crypt_rosette(bm, layer, cx + RNG.gauss(0, 0.1), cz + RNG.gauss(0, 0.08), RNG.uniform(0.8, 1.3))
    objects.append(plant_object('crypts', crypts, crypt_mat))

    def epiphytes(bm, layer):
        # Java-fern-like tufts on the wood, small dark clusters on the rocks.
        wood_samples = sample_surfaces([wood], int(24 * density), lambda p: 0.2 + max(
            (math.exp(-((p - j).length ** 2) / 0.1) for j in JOINTS), default=0.0), min_up=0.3)
        for point, normal in wood_samples:
            java_fern(bm, layer, point, normal, RNG.uniform(0.6, 1.0))
    objects.append(plant_object('fern-tufts', epiphytes, fern_mat))

    def buce(bm, layer):
        rock_samples = sample_surfaces(rocks[:len(V['rocks'])], int(44 * density), lambda p: 1.0, min_up=0.35)
        for point, normal in rock_samples:
            buce_cluster(bm, layer, point, normal, RNG.uniform(0.8, 1.2))
    objects.append(plant_object('rock-leaves', buce, anubias_mat))

    def stems(bm, layer):
        # Background masses, composed like an aquascaper would: each mass is
        # a set of sub-clumps (one plant character per clump, similar heights
        # inside a clump), with a strong height hierarchy that follows the
        # composition (tallest behind the hardscape, falling to the right)
        # and deliberate gaps.
        kinds = [
            dict(leaf_len=0.095, per_whorl=4, width_ratio=0.2, top=(1.25, 1.15, 0.7), base=(0.7, 0.85, 0.65)),
            dict(leaf_len=0.14, per_whorl=2, width_ratio=0.3, top=(1.05, 1.2, 0.8), base=(0.65, 0.8, 0.6)),
            dict(leaf_len=0.085, per_whorl=3, width_ratio=0.25, top=(1.45, 0.85, 0.65), base=(0.75, 0.8, 0.6)),
            dict(leaf_len=0.12, per_whorl=3, width_ratio=0.16, top=(0.9, 1.1, 0.75), base=(0.5, 0.65, 0.5)),
        ]
        masses = [
            # centre x, z, half width, peak height, sub-clumps, preferred kinds
            (-2.55, -2.35, 1.1, 2.9, 11, (0, 3, 0)),
            (-1.25, -2.65, 0.8, 2.1, 7, (2, 0)),
            (-0.15, -2.95, 0.6, 1.35, 5, (1, 3)),
            (1.75, -2.9, 0.55, 0.95, 4, (3, 1)),
            (3.3, -2.55, 0.8, 1.6, 6, (0, 2)),
            (-3.7, -1.75, 0.35, 1.3, 3, (3,)),
            (-1.9, -1.7, 0.5, 1.15, 4, (1, 2)),
            # low, broken back layer: darkness and haze do the rest
            (0.75, -3.3, 1.4, 0.55, 6, (3, 1)), (2.6, -3.35, 1.2, 0.5, 5, (1,)), (-4.4, -3.2, 0.9, 1.4, 4, (0,)),
            (4.6, -3.1, 0.9, 1.1, 4, (3,)),
        ]
        for mx, mz, half, peak, clumps, kind_ids in masses:
            for c in range(int(clumps * 2.2 * density + 0.5)):
                cx = mx + RNG.uniform(-half, half)
                cz = mz + RNG.gauss(0, 0.18)
                dome = max(0.3, 1 - (abs(cx - mx) / half) ** 1.6 * 0.6)
                clump_h = peak * dome * RNG.uniform(0.7, 1.08)
                kind = kinds[kind_ids[c % len(kind_ids)]]
                shade = RNG.uniform(0.7, 1.1)
                for _ in range(RNG.randint(10, 18)):
                    x, z = cx + RNG.gauss(0, 0.1), cz + RNG.gauss(0, 0.08)
                    lean = (RNG.gauss(0.04, 0.06), RNG.gauss(0, 0.04))
                    stem_plant(bm, layer, x, z, max(0.25, clump_h * RNG.uniform(0.82, 1.04)), lean,
                               tuple(c * shade for c in kind['top']), tuple(c * shade for c in kind['base']),
                               leaf_len=kind['leaf_len'] * RNG.uniform(0.9, 1.1), per_whorl=kind['per_whorl'],
                               width_ratio=kind['width_ratio'])
    objects.append(plant_object('stems', stems, stem_mat))

    def vallis(bm, layer):
        # Ribbons in several clumps at different depths and heights, woven
        # into the stem masses instead of one isolated clump.
        clumps = [(3.05, -2.35, 14, (1.8, 2.8)), (3.85, -2.05, 8, (1.1, 1.9)), (2.35, -2.95, 9, (2.1, 3.0)),
                  (4.4, -2.9, 8, (2.2, 3.2)), (-3.35, -2.95, 9, (1.9, 2.7)), (-1.7, -3.1, 5, (2.0, 2.6))]
        for cx, cz, count, heights in clumps:
            for _ in range(int(count * 1.6 * density + 0.5)):
                x, z = cx + RNG.gauss(0, 0.13), cz + RNG.gauss(0, 0.1)
                vallis_ribbon(bm, layer, x, z, RNG.uniform(*heights), RNG.uniform(0.04, 0.065),
                              (RNG.gauss(0.34, 0.12), 0.0), jitter_tint((0.85, 1.0, 0.85), 0.12))
    objects.append(plant_object('ribbons', vallis, vallis_mat))
    return objects


# ==========================================================================
# Water, light, atmosphere
# ==========================================================================

def build_camera():
    data = bpy.data.cameras.new('habitat-camera')
    data.sensor_fit = 'VERTICAL'
    data.angle_y = math.radians(38)
    data.clip_start = 0.1
    data.clip_end = 30
    camera = link(bpy.data.objects.new('habitat-camera', data))
    camera.location = B(*CAMERA)
    direction = (B(0, 0, 0) - camera.location).normalized()
    if ARGS.camera == 'close':
        # Material close view of the hardscape (Stage 1 comparison).
        data.angle_y = math.radians(30)
        camera.location = B(-1.0, 0.05, 3.3)
        direction = (B(-2.05, -0.45, -0.85) - camera.location).normalized()
    camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = camera


def build_world():
    world = bpy.data.worlds.new('water')
    world.use_nodes = True
    tree = world.node_tree
    background = tree.nodes['Background']
    # Camera rays see a deep teal gradient; lighting sees a dim teal ambient.
    gradient_coord = tree.nodes.new('ShaderNodeTexCoord')
    separate = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(gradient_coord.outputs['Window'], separate.inputs['Vector'])
    ramp = tree.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.004, 0.017, 0.02, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.018, 0.065, 0.07, 1)
    tree.links.new(separate.outputs['Y'], ramp.inputs['Fac'])
    light_path = tree.nodes.new('ShaderNodeLightPath')
    mix = tree.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs[6].default_value = (0.02, 0.055, 0.06, 1)
    tree.links.new(light_path.outputs['Is Camera Ray'], mix.inputs['Factor'])
    tree.links.new(ramp.outputs['Color'], mix.inputs[7])
    tree.links.new(mix.outputs[2], background.inputs['Color'])
    background.inputs['Strength'].default_value = 1.0
    bpy.context.scene.world = world


def build_water_volume():
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    obj = mesh_object('water-volume', bm)
    obj.scale = (16, 16, 6)
    obj.location = B(0, 0.8, 0)
    material = bpy.data.materials.new('water')
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.remove(tree.nodes['Principled BSDF'])
    volume = tree.nodes.new('ShaderNodeVolumePrincipled')
    volume.inputs['Color'].default_value = (0.12, 0.33, 0.34, 1)
    volume.inputs['Density'].default_value = 0.075
    volume.inputs['Anisotropy'].default_value = 0.55
    volume.inputs['Absorption Color'].default_value = (0.55, 0.82, 0.8, 1)
    tree.links.new(volume.outputs['Volume'], tree.nodes['Material Output'].inputs['Volume'])
    obj.data.materials.append(material)
    return obj


def build_lights():
    sun = bpy.data.lights.new('aquarium-lamp', 'SUN')
    sun.color = (0.86, 0.94, 1.0)
    sun.energy = 2.4
    sun.angle = math.radians(4)
    obj = link(bpy.data.objects.new('aquarium-lamp', sun))
    # From above, a little from the upper left and the front.
    obj.rotation_euler = (math.radians(18), math.radians(-22), 0)
    try_set(sun, 'volume_factor', 1.0)
    # Surface ripples: a light-blocking sheet above the frame whose
    # transparent holes cast soft moving-water shafts through the volume.
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=9)
    sheet = mesh_object('surface-sheet', bm)
    sheet.location = B(0, 3.4, -0.5)
    material = bpy.data.materials.new('surface-shadow')
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.remove(tree.nodes['Principled BSDF'])
    transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
    diffuse = tree.nodes.new('ShaderNodeBsdfDiffuse')
    mix = tree.nodes.new('ShaderNodeMixShader')
    coord = tree.nodes.new('ShaderNodeTexCoord')
    mapping = tree.nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (1.1, 3.4, 1)
    tree.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    pattern = tree.nodes.new('ShaderNodeTexNoise')
    pattern.inputs['Scale'].default_value = 1.2
    pattern.inputs['Detail'].default_value = 2.0
    tree.links.new(mapping.outputs['Vector'], pattern.inputs['Vector'])
    ramp = tree.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[0].color = (0.45, 0.45, 0.45, 1)
    ramp.color_ramp.elements[1].position = 0.62
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    tree.links.new(pattern.outputs['Fac'], ramp.inputs['Fac'])
    tree.links.new(ramp.outputs['Color'], mix.inputs['Fac'])
    tree.links.new(diffuse.outputs['BSDF'], mix.inputs[1])
    tree.links.new(transparent.outputs['BSDF'], mix.inputs[2])
    tree.links.new(mix.outputs['Shader'], tree.nodes['Material Output'].inputs['Surface'])
    try_set(material, 'use_transparent_shadow', True)
    sheet.data.materials.append(material)
    sheet.visible_camera = False
    try_set(sheet, 'visible_diffuse', False)
    try_set(sheet, 'visible_glossy', False)
    # Hero key: a warm, soft light from the upper left that falls on the
    # hardscape and fades through the centre into the deep open water.
    key = bpy.data.lights.new('hero-key', 'SPOT')
    key.color = (1.0, 0.8, 0.58)
    key.energy = 11000
    key.spot_size = math.radians(42)
    key.spot_blend = 1.0
    try_set(key, 'shadow_soft_size', 0.45)
    try_set(key, 'volume_factor', 0.55)
    key_obj = link(bpy.data.objects.new('hero-key', key))
    key_obj.location = B(-3.9, 3.9, 2.2)
    aim = (B(-1.9, -0.55, -0.7) - key_obj.location).normalized()
    key_obj.rotation_euler = aim.to_track_quat('-Z', 'Y').to_euler()
    # Soft cool fill from the front so the hardscape never goes pitch black.
    fill = bpy.data.lights.new('fill', 'AREA')
    fill.energy = 28
    fill.color = (0.55, 0.8, 0.85)
    fill.size = 8
    fill_obj = link(bpy.data.objects.new('fill', fill))
    fill_obj.location = B(-1.0, 1.2, 5.5)
    fill_obj.rotation_euler = (math.radians(80), 0, 0)
    try_set(fill, 'volume_factor', 0.0)


def build_back_fog():
    """Denser water toward the back: distant forms dissolve into teal."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    obj = mesh_object('back-fog', bm)
    obj.scale = (30, 7.4, 8)
    obj.location = B(0, 1.0, -6.2)
    material = bpy.data.materials.new('back-fog')
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.remove(tree.nodes['Principled BSDF'])
    volume = tree.nodes.new('ShaderNodeVolumePrincipled')
    volume.inputs['Color'].default_value = (0.055, 0.17, 0.18, 1)
    volume.inputs['Density'].default_value = 0.2
    volume.inputs['Anisotropy'].default_value = 0.4
    volume.inputs['Absorption Color'].default_value = (0.5, 0.8, 0.78, 1)
    tree.links.new(volume.outputs['Volume'], tree.nodes['Material Output'].inputs['Volume'])
    obj.data.materials.append(material)
    return obj


def build_back_wall():
    """Dark background film behind the tank, as in most nature aquariums."""
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1)
    wall = mesh_object('back-wall', bm)
    wall.scale = (30, 12, 1)
    wall.location = B(0, 1.2, -10.2)
    wall.rotation_euler = (math.radians(90), 0, 0)
    material, bsdf = principled('back-film', (0.006, 0.02, 0.022), 0.95)
    wall.data.materials.append(material)
    return wall


def build_shafts():
    """Faint light shafts from the upper left, drawn as soft additive sheets
    behind the midground (the lamp's volume scattering alone is too weak to
    read at this density)."""
    material = bpy.data.materials.new('shaft')
    material.use_nodes = True
    try_set(material, 'surface_render_method', 'BLENDED')
    tree = material.node_tree
    tree.nodes.remove(tree.nodes['Principled BSDF'])
    coord = tree.nodes.new('ShaderNodeTexCoord')
    separate = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(coord.outputs['UV'], separate.inputs['Vector'])
    # Fade along the shaft (strong at the top) and across it (soft edges).
    along = tree.nodes.new('ShaderNodeMapRange')
    along.inputs['From Min'].default_value = 0.0
    along.inputs['From Max'].default_value = 1.0
    along.inputs['To Min'].default_value = 0.0
    along.inputs['To Max'].default_value = 1.0
    tree.links.new(separate.outputs['Y'], along.inputs['Value'])
    across = tree.nodes.new('ShaderNodeMath')
    across.operation = 'PINGPONG'
    across.inputs[1].default_value = 0.5
    tree.links.new(separate.outputs['X'], across.inputs[0])
    soft = tree.nodes.new('ShaderNodeMath')
    soft.operation = 'POWER'
    soft.inputs[1].default_value = 1.6
    tree.links.new(across.outputs[0], soft.inputs[0])
    fade = tree.nodes.new('ShaderNodeMath')
    fade.operation = 'MULTIPLY'
    tree.links.new(along.outputs['Result'], fade.inputs[0])
    tree.links.new(soft.outputs[0], fade.inputs[1])
    strength = tree.nodes.new('ShaderNodeMath')
    strength.operation = 'MULTIPLY'
    strength.inputs[1].default_value = 0.1
    tree.links.new(fade.outputs[0], strength.inputs[0])
    emission = tree.nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (0.75, 0.9, 0.8, 1)
    tree.links.new(strength.outputs[0], emission.inputs['Strength'])
    transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
    add = tree.nodes.new('ShaderNodeAddShader')
    tree.links.new(emission.outputs['Emission'], add.inputs[0])
    tree.links.new(transparent.outputs['BSDF'], add.inputs[1])
    tree.links.new(add.outputs['Shader'], tree.nodes['Material Output'].inputs['Surface'])
    shafts = [(-2.6, -1.5, 0.9, 1.0), (-1.4, -1.8, 0.6, 0.8), (-0.3, -2.1, 0.8, 0.6)]
    for index, (x, z, width, strength_scale) in enumerate(shafts):
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new('UVMap')
        top, bottom = 3.8, -1.0
        lean = 0.75   # shafts slant down to the right, away from the lamp
        corners = [(x - width / 2, top, 0, 1), (x + width / 2, top, 1, 1),
                   (x + width / 2 + lean * 1.6, bottom, 1, 0), (x - width / 2 + lean * 1.6, bottom, 0, 0)]
        verts = [bm.verts.new(B(cx, cy, z)) for cx, cy, _, _ in corners]
        face = bm.faces.new(verts)
        for loop, (_, _, u, v) in zip(face.loops, corners):
            loop[uv].uv = (u, v)
        obj = mesh_object(f'shaft-{index}', bm)
        instance = material.copy()
        instance.node_tree.nodes['Math.003'].inputs[1].default_value *= strength_scale if 'Math.003' in instance.node_tree.nodes else 1
        obj.data.materials.append(instance)
        try_set(obj, 'visible_shadow', False)


def build_particles(count=70):
    bm = bmesh.new()
    for _ in range(count):
        x = RNG.uniform(-3.8, 3.8)
        z = RNG.uniform(-2.5, 3.0)
        y = RNG.uniform(-1.2, 2.2)
        radius = RNG.uniform(0.003, 0.007)
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius, matrix=Matrix.Translation(B(x, y, z)))
    obj = mesh_object('particles', bm)
    material, bsdf = principled('particle', (0.6, 0.65, 0.55), 0.8)
    bsdf.inputs['Emission Color'].default_value = (0.7, 0.85, 0.8, 1)
    bsdf.inputs['Emission Strength'].default_value = 0.04
    bsdf.inputs['Alpha'].default_value = 0.35
    obj.data.materials.append(material)
    return obj


def build_hero_fish(directory):
    """The approved Hero Fish (Pass 1B), exported as a static pose from the
    runtime module, placed at realistic desktop scale. Scale reference only."""
    folder = pathlib.Path(directory)
    before = set(bpy.data.objects)
    for name in ('fish_body.obj', 'fish_fins.obj'):
        bpy.ops.wm.obj_import(filepath=str(folder / name))
    parts = {obj.name.split('.')[0]: obj for obj in set(bpy.data.objects) - before}
    body_mat, body = principled('hero-fish-body', (0.6, 0.6, 0.6), 0.32)
    tex = body_mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = image(folder / 'fish_body.png')
    body_mat.node_tree.links.new(tex.outputs['Color'], body.inputs['Base Color'])
    body.inputs['Metallic'].default_value = 0.35
    body.inputs['Coat Weight'].default_value = 0.35
    try_set(body.inputs.get('Thin Film Thickness'), 'default_value', 380.0)
    eye_mat, eye = principled('hero-fish-eye', (0.012, 0.012, 0.014), 0.15)
    eye.inputs['Coat Weight'].default_value = 1.0
    fin_mat, fin = principled('hero-fish-fin', (0.8, 0.4, 0.3), 0.45)
    try_set(fin_mat, 'surface_render_method', 'DITHERED')
    fin_tex = fin_mat.node_tree.nodes.new('ShaderNodeTexImage')
    fin_tex.image = image(folder / 'fish_fin.png')
    fin_mat.node_tree.links.new(fin_tex.outputs['Color'], fin.inputs['Base Color'])
    fin_mat.node_tree.links.new(fin_tex.outputs['Alpha'], fin.inputs['Alpha'])
    for key, material in (('fish_body', body_mat), ('fish_eye', eye_mat), ('fish_fins', fin_mat)):
        if key in parts:
            parts[key].data.materials.clear()
            parts[key].data.materials.append(material)
    templates = [obj for obj in parts.values() if obj.type == 'MESH']
    # Three fish in the open water, heading toward the hardscape.
    placements = [(0.95, 0.3, 0.35, 195), (1.7, 0.55, -0.1, 170), (1.35, 0.05, 0.05, 185)]
    scale = 0.75
    for index, (x, y, z, yaw) in enumerate(placements):
        for template in templates:
            copy = template if index == 0 else template.copy()
            if index:
                link(copy)
            copy.location = B(x, y, z)
            # The OBJ importer's Y-up -> Z-up conversion lives in the object rotation.
            copy.rotation_euler = (math.radians(90), 0, math.radians(yaw))
            copy.scale = (scale, scale, scale)


def build_fish():
    """A few small neutral silhouettes, for scale only."""
    material, bsdf = principled('fish-scale-ref', (0.55, 0.58, 0.56), 0.35)
    bsdf.inputs['Metallic'].default_value = 0.5
    for x, y, z, heading, length in ((0.9, 0.35, 0.3, math.pi, 0.5), (1.6, 0.6, -0.2, math.pi * 1.05, 0.46),
                                     (2.2, 0.15, 0.1, math.pi * 0.95, 0.48)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.5)
        obj = mesh_object('fish', bm)
        obj.scale = (length, length * 0.09, length * 0.2)
        obj.location = B(x, y, z)
        obj.rotation_euler = (0, 0, heading)
        obj.data.materials.append(material)


# ==========================================================================
# Render
# ==========================================================================

def configure_render():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = ARGS.scale
    scene.render.film_transparent = False
    eevee = scene.eevee
    try_set(eevee, 'taa_render_samples', ARGS.samples)
    try_set(eevee, 'volumetric_start', 0.5)
    try_set(eevee, 'volumetric_end', 14.0)
    try_set(eevee, 'volumetric_tile_size', '4' if ARGS.scale >= 100 else '8')
    try_set(eevee, 'volumetric_samples', 64)
    try_set(eevee, 'use_volumetric_shadows', True)
    try_set(eevee, 'volumetric_shadow_samples', 16)
    try_set(eevee, 'use_shadows', True)
    try_set(eevee, 'shadow_ray_count', 2)
    try_set(eevee, 'use_raytracing', False)
    try_set(eevee, 'use_gtao', True)
    try_set(eevee, 'gtao_distance', 0.6)
    view = scene.view_settings
    try_set(view, 'view_transform', 'AgX')
    for look in ('AgX - Medium High Contrast', 'Medium High Contrast'):
        try:
            view.look = look
            break
        except TypeError:
            continue
    view.exposure = -0.1
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = ARGS.out


def apply_clay(objects):
    clay = clay_material()
    for obj in objects:
        if obj.type != 'MESH' or obj.name in ('water-volume', 'surface-sheet', 'back-wall', 'back-fog'):
            continue
        obj.data.materials.clear()
        obj.data.materials.append(clay)


def main():
    started = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_camera()
    build_world()
    rocks = build_rocks()
    if ARGS.root:
        wood = build_scanned_root(ARGS.root)
    elif ARGS.wood == 'scan-strips':
        wood = build_scan_strip_root()
    else:
        wood = build_wood()
        wood.data.materials.append(bark_willow_material() if ARGS.bark == 'willow' else bark_material())
    substrate = build_substrate()
    substrate.data.materials.append(textured_ground_material())
    RNG.seed(20260925)
    moss = build_moss(wood, rocks, int(1500 * ARGS.density))
    RNG.seed(20260926)
    vegetation = [] if ARGS.no_plants else build_vegetation(rocks, wood)
    build_water_volume()
    build_back_wall()
    build_back_fog()
    build_lights()
    if not CLAY:
        build_shafts()
    build_particles()
    if ARGS.fish:
        build_fish()
    if ARGS.hero_fish:
        build_hero_fish(ARGS.hero_fish)
    if CLAY:
        apply_clay([o for o in bpy.context.scene.objects])
    configure_render()
    total = sum(len(o.data.polygons) for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render)
    log(f'scene built in {time.time() - started:.0f}s, ~{total} faces (instanced moss counted per sprig)')
    if ARGS.blend:
        bpy.ops.wm.save_as_mainfile(filepath=ARGS.blend)
    started = time.time()
    bpy.ops.render.render(write_still=True)
    log(f'rendered {ARGS.out} in {time.time() - started:.0f}s')


main()
