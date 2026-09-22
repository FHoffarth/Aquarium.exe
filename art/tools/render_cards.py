"""Render vegetation card tiles (colour + alpha) from approved CC0 plant scans.

Run headless before prepare_textures.py:
  blender -b --factory-startup -P art/tools/render_cards.py

The habitat camera is fixed and near-horizontal, so each tile is rendered
from that same viewpoint: camera-facing cards then never reveal flatness.
Lighting is a uniform white environment, so tiles hold near-albedo colour
plus soft self-occlusion; the runtime lights them like the rest of the scene.
Flower geometry on the carpet source is removed (aquarium vegetation).
"""

import math
import pathlib
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'art' / 'source' / 'polyhaven'
OUT = ROOT / 'art' / 'work' / 'slice-a' / 'cards'
RNG = random.Random(4412)
CAMERA_ELEVATION = math.radians(9)


def log(message):
    print(f'[cards] {message}', flush=True)


def import_asset(asset_id):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(next((SRC / asset_id).glob('*.gltf'))))
    created = sorted((o for o in set(bpy.data.objects) - before if o.type == 'MESH'), key=lambda o: o.name)
    for obj in created:
        matrix = obj.matrix_world.copy()
        obj.parent = None
        obj.data.transform(matrix)
        obj.matrix_world = Matrix.Identity(4)
    return {obj.name: obj for obj in created}


def recenter(obj):
    zs = [v.co.z for v in obj.data.vertices]
    base = [v.co for v in obj.data.vertices if v.co.z < min(zs) + 0.1 * (max(zs) - min(zs))]
    cx = sum(p.x for p in base) / len(base)
    cy = sum(p.y for p in base) / len(base)
    obj.data.transform(Matrix.Translation(Vector((-cx, -cy, -min(zs)))))


def hook_alpha(asset_id, objects):
    """Poly Haven glTF materials omit the opacity map; wire it into Principled Alpha."""
    alpha_path = next((SRC / asset_id / 'textures').glob('*_alpha_*.png'))
    image = bpy.data.images.load(str(alpha_path))
    image.colorspace_settings.name = 'Non-Color'
    for material in {slot.material for obj in objects for slot in obj.material_slots if slot.material}:
        tree = material.node_tree
        principled = next(node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED')
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        tree.links.new(node.outputs['Color'], principled.inputs['Alpha'])


def remove_flowers(obj, diffuse):
    """Delete faces whose texture colour is petal-pink (the source plant flowers)."""
    width, height = diffuse.size
    pixels = diffuse.pixels[:]
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.active
    doomed = []
    for face in bm.faces:
        u = sum(loop[uv_layer].uv.x for loop in face.loops) / len(face.loops)
        v = sum(loop[uv_layer].uv.y for loop in face.loops) / len(face.loops)
        px = min(width - 1, max(0, int(u % 1.0 * width)))
        py = min(height - 1, max(0, int(v % 1.0 * height)))
        index = (py * width + px) * 4
        r, g, b = pixels[index], pixels[index + 1], pixels[index + 2]
        if r > 0.45 and r > g * 1.35 and b > g * 1.05:
            doomed.append(face)
    bmesh.ops.delete(bm, geom=doomed, context='FACES')
    bm.to_mesh(mesh)
    bm.free()
    return len(doomed)


def setup_scene(resolution):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 48
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    world = bpy.data.worlds.new('card-world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    scene.world = world


def camera(ortho_scale, target_z):
    data = bpy.data.cameras.new('card-camera')
    data.type = 'ORTHO'
    data.ortho_scale = ortho_scale
    cam = bpy.data.objects.new('card-camera', data)
    bpy.context.scene.collection.objects.link(cam)
    distance = 3.0
    cam.location = Vector((0, -distance * math.cos(CAMERA_ELEVATION),
                           target_z + distance * math.sin(CAMERA_ELEVATION)))
    cam.rotation_euler = (math.pi / 2 - CAMERA_ELEVATION, 0, 0)
    bpy.context.scene.camera = cam
    return cam


def render(path, visible):
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.hide_render = obj not in visible
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    log(f'rendered {path.name}')


def carpet_tiles(count=4):
    sources = import_asset('shrub_sorrel_01')
    hook_alpha('shrub_sorrel_01', sources.values())
    diffuse = next(img for img in bpy.data.images if 'diff' in img.name)
    usable = []
    for obj in sources.values():
        removed = remove_flowers(obj, diffuse)
        recenter(obj)
        log(f'{obj.name}: removed {removed} flower faces')
        # Sprigs that carried flowers keep bare bud stalks; use leafy ones only.
        if removed == 0 and max(v.co.z for v in obj.data.vertices) < 0.06:
            usable.append(obj)
    log(f'carpet sprigs used: {[o.name for o in usable]}')
    setup_scene((512, 256))
    camera(0.19, 0.022)
    for tile in range(count):
        clump = []
        for index in range(22):
            obj = RNG.choice(usable)
            copy = obj.copy()
            copy.data = obj.data.copy()
            bpy.context.scene.collection.objects.link(copy)
            angle = RNG.uniform(0, math.tau)
            radius = 0.075 * math.sqrt(RNG.random())
            copy.data.transform(
                Matrix.Translation(Vector((math.cos(angle) * radius, math.sin(angle) * radius * 0.6, -0.004)))
                @ Matrix.Rotation(RNG.uniform(0, math.tau), 4, 'Z')
                @ Matrix.Rotation(RNG.uniform(-0.25, 0.25), 4, 'X')
                @ Matrix.Scale(RNG.uniform(0.55, 1.0), 4))
            clump.append(copy)
        render(OUT / f'carpet_{tile}.png', clump)
        for obj in clump:
            bpy.data.objects.remove(obj)


def stem_tiles():
    sources = import_asset('nettle_plant')
    hook_alpha('nettle_plant', sources.values())
    setup_scene((512, 1024))
    names = ['nettle_plant_tall_a_LOD0', 'nettle_plant_tall_b_LOD0']
    for index, name in enumerate(names):
        obj = sources[name]
        recenter(obj)
        height = max(v.co.z for v in obj.data.vertices)
        cam = camera(height * 1.02, height * 0.5)
        render(OUT / f'stem_{index}.png', [obj])
        bpy.data.objects.remove(cam)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    OUT.mkdir(parents=True, exist_ok=True)
    carpet_tiles()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    stem_tiles()


main()
