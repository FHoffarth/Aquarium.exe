"""Bounded offline substrate and water treatment, with independent seeded RNGs."""
import math
import random

import bpy


def substrate_height(x, y, original_height):
    # Three broad centimeter-scale changes, confined to the open foreground.
    mask = math.exp(-(x/3.0)**6) * min(1, max(0, (.25-y)/.7))
    raised_front = .075*math.exp(-((x+1.4)/1.7)**2-((y+3.6)/1.4)**2)
    shallow_hollow = -.045*math.exp(-((x-.25)/1.7)**2-((y+1.9)/1.3)**2)
    side_rise = .07*math.exp(-((x-1.7)/1.2)**2-((y+.7)/1.0)**2)
    return original_height(x, y)+mask*(raised_front+shallow_hollow+side_rise)


def redistribute_gravel(mesh, faces_per_stone, original_height, noise, seed):
    """Move existing stones only; preserve geometry count and the scene RNG."""
    rng = random.Random(seed)
    stride = faces_per_stone*3
    for start in range(0, len(mesh.v), stride):
        ring = [mesh.v[start+j*3+k] for j in range(faces_per_stone) for k in (0, 1)]
        cx = sum(p[0] for p in ring)/len(ring)
        cy = sum(p[1] for p in ring)/len(ring)
        x, y, scale = cx, cy, 1.0
        if abs(cx) < 2.8 and cy < -.25:
            for _ in range(32):
                x, y = rng.uniform(-2.8, 2.8), rng.uniform(-4.7, -.25)
                clearing = math.exp(-((x-.15)/1.65)**2-((y+1.9)/2.2)**2)
                density = max(.08, .35+.5*noise(x*.8+2, y*.65-8)-.43*clearing)
                if rng.random() < density:
                    break
            fine = math.exp(-((x-.15)/1.7)**2-((y+1.7)/2.0)**2)
            scale = (1-.35*fine)*rng.uniform(.85, 1.2)
            if rng.random() < .06:
                scale *= 1.3
        old_z = original_height(cx, cy)
        new_z = substrate_height(x, y, original_height)
        for i in range(start, start+stride):
            vx, vy, vz = mesh.v[i]
            mesh.v[i] = (x+(vx-cx)*scale, y+(vy-cy)*scale, new_z+(vz-old_z)*scale)


def naturalize_ground_material(mat):
    n, links = mat.node_tree.nodes, mat.node_tree.links
    p = n.get('Principled BSDF')
    base = tuple(p.inputs['Base Color'].default_value)
    coord = n.new('ShaderNodeNewGeometry')
    patches = n.new('ShaderNodeTexNoise')
    patches.inputs['Scale'].default_value = .58
    patches.inputs['Detail'].default_value = 1
    links.new(coord.outputs['Position'], patches.inputs['Vector'])
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .18
    ramp.color_ramp.elements[1].position = .82
    ramp.color_ramp.elements[0].color = tuple(c*.86 for c in base[:3])+(1,)
    ramp.color_ramp.elements[1].color = tuple(c*1.14 for c in base[:3])+(1,)
    links.new(patches.outputs['Fac'], ramp.inputs[0])
    links.new(ramp.outputs[0], p.inputs['Base Color'])
    sand = n.new('ShaderNodeTexNoise')
    sand.inputs['Scale'].default_value = 125
    sand.inputs['Detail'].default_value = 1
    links.new(coord.outputs['Position'], sand.inputs['Vector'])
    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .12
    bump.inputs['Distance'].default_value = .004
    links.new(sand.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs[0], p.inputs['Normal'])


def add_water_to_material(mat, light_variation=False):
    n, links = mat.node_tree.nodes, mat.node_tree.links
    p = n.get('Principled BSDF')
    output = next(node for node in n if node.type == 'OUTPUT_MATERIAL')
    surface = output.inputs['Surface'].links[0].from_socket
    camera = n.new('ShaderNodeCameraData')
    depth = n.new('ShaderNodeMapRange')
    depth.clamp = True
    depth.inputs['From Min'].default_value = 15.5
    depth.inputs['From Max'].default_value = 21.0
    depth.inputs['To Max'].default_value = .13
    links.new(camera.outputs['View Distance'], depth.inputs['Value'])
    ray = n.new('ShaderNodeLightPath')
    amount = n.new('ShaderNodeMath'); amount.operation = 'MULTIPLY'
    links.new(depth.outputs['Result'], amount.inputs[0])
    links.new(ray.outputs['Is Camera Ray'], amount.inputs[1])
    water = n.new('ShaderNodeEmission')
    water.inputs['Color'].default_value = (.055, .19, .23, 1)
    water.inputs['Strength'].default_value = .8
    blend = n.new('ShaderNodeMixShader')
    links.new(amount.outputs[0], blend.inputs[0])
    links.new(surface, blend.inputs[1])
    links.new(water.outputs[0], blend.inputs[2])
    links.new(blend.outputs[0], output.inputs['Surface'])
    if not light_variation:
        return
    # Broad, low-contrast moving illumination; no bright caustic lines.
    coord = n.new('ShaderNodeNewGeometry')
    shimmer = n.new('ShaderNodeTexNoise'); shimmer.noise_dimensions = '4D'
    shimmer.inputs['Scale'].default_value = 2.2
    shimmer.inputs['Detail'].default_value = 1
    shimmer.inputs['Roughness'].default_value = .35
    shimmer.inputs['W'].driver_add('default_value').driver.expression = 'frame / 1800.0'
    links.new(coord.outputs['Position'], shimmer.inputs['Vector'])
    strength = n.new('ShaderNodeMapRange')
    strength.inputs['To Min'].default_value = .982
    strength.inputs['To Max'].default_value = 1.038
    links.new(shimmer.outputs['Fac'], strength.inputs['Value'])
    multiply = n.new('ShaderNodeMixRGB'); multiply.blend_type = 'MULTIPLY'
    multiply.inputs[0].default_value = 1
    if p.inputs['Base Color'].is_linked:
        links.new(p.inputs['Base Color'].links[0].from_socket, multiply.inputs[1])
    else:
        multiply.inputs[1].default_value = p.inputs['Base Color'].default_value
    links.new(strength.outputs['Result'], multiply.inputs[2])
    links.new(multiply.outputs[0], p.inputs['Base Color'])


def add_water_atmosphere(surface_materials, light_materials):
    for mat in dict.fromkeys(surface_materials):
        add_water_to_material(mat, mat in light_materials)
    rng = random.Random(73109)
    mat = bpy.data.materials.new('barely visible suspended freshwater matter')
    mat.use_nodes = True
    p = mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (.18, .23, .19, 1)
    p.inputs['Roughness'].default_value = .85
    for i in range(22):
        position = (rng.uniform(-6, 6), rng.uniform(-.6, 3.4), rng.uniform(1.2, 5.8))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(.0035, .008), location=position)
        obj = bpy.context.object; obj.name = f'sparse water particle {i:02d}'
        obj.data.materials.append(mat)
        obj.keyframe_insert(data_path='location', frame=1)
        obj.location.x += rng.uniform(.025, .075)
        obj.location.z += rng.uniform(-.015, .015)
        obj.keyframe_insert(data_path='location', frame=601)
    bpy.context.scene.frame_set(1)
