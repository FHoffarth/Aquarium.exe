"""Report objects, triangle counts, dimensions and materials of each source glTF.

Run: blender -b --factory-startup -P art/tools/inspect_sources.py
"""

import pathlib

import bpy

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'art' / 'source' / 'polyhaven'


def triangles(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    return len(mesh.loop_triangles)


for gltf in sorted(SOURCE.glob('*/*.gltf')):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(gltf))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    total = sum(triangles(obj) for obj in meshes)
    print(f'\n=== {gltf.parent.name}: {len(meshes)} mesh objects, {total} triangles')
    for obj in meshes:
        dims = ', '.join(f'{value:.3f}' for value in obj.dimensions)
        mats = ', '.join(slot.material.name for slot in obj.material_slots if slot.material)
        print(f'  {obj.name:40s} tris={triangles(obj):7d} dims=({dims}) mats=[{mats}]')
