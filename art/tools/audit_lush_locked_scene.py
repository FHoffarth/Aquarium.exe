"""Hash the offline scene's locked geometry, transforms, camera and lamps."""
import array
import hashlib
import json
import sys

import bpy

excluded = {'undulating natural gravel bed', 'fine gravel openings',
            'scattered embedded foreground gravel'}
result = {}
for obj in bpy.data.objects:
    if obj.name in excluded or obj.name.startswith('sparse water particle '):
        continue
    item = {'type': obj.type, 'matrix': [list(row) for row in obj.matrix_world]}
    if obj.type == 'MESH':
        coordinates = array.array('f', [0]) * (len(obj.data.vertices)*3)
        obj.data.vertices.foreach_get('co', coordinates)
        item['vertices'] = len(obj.data.vertices)
        item['geometry'] = hashlib.sha256(coordinates.tobytes()).hexdigest()
    elif obj.type == 'LIGHT':
        item.update(energy=obj.data.energy, color=list(obj.data.color), size=obj.data.size)
    elif obj.type == 'CAMERA':
        item.update(lens=obj.data.lens, camera_type=obj.data.type)
    result[obj.name] = item
result['exposure'] = bpy.context.scene.view_settings.exposure
path = sys.argv[sys.argv.index('--')+1]
with open(path, 'w') as file:
    json.dump(result, file, sort_keys=True, indent=2)
print(f'Locked scene manifest: {path}')
