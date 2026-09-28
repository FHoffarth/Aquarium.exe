"""Render the approved 6dfd62d environment without posed fish for runtime."""
import pathlib

import bpy

root = pathlib.Path(__file__).resolve().parents[2]
output = root/'art/work/lush-reference/runtime-environment.png'
for obj in bpy.data.objects:
    if obj.name.startswith('hero-') or obj.name.startswith('sparse water particle '):
        obj.hide_render = True
scene = bpy.context.scene
assert scene.render.resolution_x == 1920 and scene.render.resolution_y == 1080
assert abs(scene.view_settings.exposure+.2) < 1e-5
scene.render.filepath = str(output)
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print(f'Approved environment-only render: {output}', flush=True)
