"""Render one neutral camera check of the exported GLB; no water effects.

Run from the repository root:
  blender -b --factory-startup -P art/tools/render_lush_slice_inspection.py
"""

import bpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "habitat/assets/lush-slice/environment.glb"
OUT = ROOT / "docs/evidence/lush-slice/geometry-inspection-1920.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ASSET))
scene = bpy.context.scene
camera = next(obj for obj in scene.objects if obj.type == "CAMERA")
scene.camera = camera

world = bpy.data.worlds.new("neutral inspection ambient")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.75, 0.82, 0.86, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.55
scene.world = world

sun = bpy.data.lights.new("neutral top light", "SUN")
sun.energy = 1.7
sun.angle = 0.30
sun_object = bpy.data.objects.new("neutral top light", sun)
scene.collection.objects.link(sun_object)
sun_object.rotation_euler = (0.18, -0.35, -0.25)

scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = -0.2
OUT.parent.mkdir(parents=True, exist_ok=True)
scene.render.filepath = str(OUT)
bpy.ops.render.render(write_still=True)
print(f"inspection frame: {OUT} ({OUT.stat().st_size} bytes)")
