"""Export a spatial proof from the approved, saved Blender aquarium.

Run from the repository root with Blender 5.2.2:
  blender -b art/work/lush-reference/lush-water-reference.blend \
    -P art/tools/export_lush_live_slice.py

This selects existing connected plant pieces inside a central X window, a
section of the existing gravel bed, original central wood/stone, and the
original rear plane. It does not regenerate the art or include offline fish,
particles, lights, or the rendered environment plate.
"""

import bmesh
import bpy
import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "art/work/lush-reference/lush-water-reference.blend"
OUT = ROOT / "habitat/assets/lush-slice/environment.glb"
SOURCE_SHA256 = "a43f49fb006b3a5ac7128f5d2faf0af978e983d85ea4e981b29d0cc67af54b93"
X_MIN, X_MAX = -3.3, 3.3
FRONT_GLASS_Y = -5.0
REAR_Y = 4.8

PLANTS = (
    "01 flowing ribbon plants", "02 tall grass", "03 fine feather plants",
    "04 medium stems", "05 irregular small leaf bushes", "06 broad leaves",
    "07 low foreground plants", "supporting stems",
)
GRAVEL = (
    "undulating natural gravel bed", "fine gravel openings",
    "scattered embedded foreground gravel",
)
HARDSCAPE = (
    "planted central wood", "planted central wood.001",
    "planted central wood.002", "partly buried rock-09",
)
REAR = "blue water background"
TEXTURE_BY_MATERIAL = {
    "photographed broad leaf surfaces": "leaves_albedo.webp",
    "rooted warm driftwood": "wood_albedo.webp",
    "scanned stone rock-09": "rock09_albedo.webp",
}


def selected_components(obj):
    """Select complete disconnected leaf/stem islands by X center.

    Keeping whole components avoids a guillotine edge through ribbon leaves.
    Ground is a continuous surface, so it is clipped at face boundaries.
    """
    mesh = obj.data
    parent = list(range(len(mesh.vertices)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for polygon in mesh.polygons:
        first = polygon.vertices[0]
        for index in polygon.vertices[1:]:
            parent[find(index)] = find(first)

    sums = defaultdict(lambda: [0.0, 0])
    for polygon in mesh.polygons:
        center = obj.matrix_world @ polygon.center
        total = sums[find(polygon.vertices[0])]
        total[0] += center.x
        total[1] += 1
    keep_roots = {root for root, (xsum, count) in sums.items()
                  if X_MIN <= xsum / count <= X_MAX}
    return {polygon.index for polygon in mesh.polygons
            if find(polygon.vertices[0]) in keep_roots}


def selected_ground(obj):
    keep = set()
    for polygon in obj.data.polygons:
        center = obj.matrix_world @ polygon.center
        if X_MIN <= center.x <= X_MAX:
            # Keep a visible foreground opening and a rear-running bed.
            if obj.name == "fine gravel openings" and center.y > 1.5:
                continue
            keep.add(polygon.index)
    return keep


def copy_faces(obj, keep):
    if not keep:
        raise ValueError(f"slice selection is empty: {obj.name}")
    mesh = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    delete = [face for face in bm.faces if face.index not in keep]
    bmesh.ops.delete(bm, geom=delete, context="FACES")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    result = bpy.data.objects.new(obj.name, mesh)
    bpy.context.collection.objects.link(result)
    result.matrix_world = obj.matrix_world.copy()
    result["approved_source_object"] = obj.name
    result["slice_selection"] = "whole connected pieces by X center" if obj.name in PLANTS else "existing faces by X center"
    return result


def pbr_material(source):
    material = bpy.data.materials.new(source.name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes.get("Principled BSDF")
    source_bsdf = next((node for node in source.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if source_bsdf:
        for input_name in ("Base Color", "Roughness", "Metallic"):
            if input_name in source_bsdf.inputs:
                principled.inputs[input_name].default_value = source_bsdf.inputs[input_name].default_value
    elif source.name == "clear blue depth":
        # The source's procedural height ramp cannot be represented by plain
        # glTF PBR. Its actual midpoint is a neutral inspection color for the
        # rear geometry, not a baked aquarium backdrop or a lighting grade.
        ramp = next(node for node in source.node_tree.nodes if node.type == "VALTORGB")
        lower, upper = ramp.color_ramp.elements[0], ramp.color_ramp.elements[-1]
        midpoint = tuple((lower.color[i] + upper.color[i]) * 0.5 for i in range(3))
        principled.inputs["Base Color"].default_value = (*midpoint, 1)
        principled.inputs["Roughness"].default_value = 1.0
    material.diffuse_color = principled.inputs["Base Color"].default_value
    material.use_backface_culling = source.name not in (
        "photographed broad leaf surfaces", "living green stems",
        "rust accent stems", "golden olive accent stems",
    ) and not source.name.startswith("leaf-")
    texture_name = TEXTURE_BY_MATERIAL.get(source.name)
    if texture_name:
        path = ROOT / "habitat/assets/slice-c/textures" / texture_name
        image = bpy.data.images.load(str(path), check_existing=True)
        image_node = nodes.new("ShaderNodeTexImage")
        image_node.image = image
        links.new(image_node.outputs["Color"], principled.inputs["Base Color"])
        if source.name == "photographed broad leaf surfaces":
            clip = nodes.new("ShaderNodeMath")
            clip.operation = "GREATER_THAN"
            clip.inputs[1].default_value = 0.45
            links.new(image_node.outputs["Alpha"], clip.inputs[0])
            links.new(clip.outputs[0], principled.inputs["Alpha"])
            material.blend_method = "CLIP"
            material.alpha_threshold = 0.45
            material.use_backface_culling = False
    return material


def main():
    if not SOURCE.is_file() or hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("approved Blender source is missing or differs from the pinned source SHA-256")
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError(f"open the pinned source .blend first: {SOURCE}")
    source_objects = {name: bpy.data.objects.get(name) for name in (*PLANTS, *GRAVEL, *HARDSCAPE, REAR)}
    missing = [name for name, obj in source_objects.items() if obj is None]
    if missing:
        raise RuntimeError(f"approved geometry missing: {missing}")

    copies = []
    for name, obj in source_objects.items():
        if name in PLANTS:
            keep = selected_components(obj)
        elif name in GRAVEL:
            keep = selected_ground(obj)
        else:
            keep = {polygon.index for polygon in obj.data.polygons}
        copies.append(copy_faces(obj, keep))

    mapped = {}
    for obj in copies:
        for index, source_material in enumerate(obj.data.materials):
            if source_material is None:
                continue
            if source_material.name not in mapped:
                mapped[source_material.name] = pbr_material(source_material)
            obj.data.materials[index] = mapped[source_material.name]

    camera = bpy.data.objects.get("offline reference camera")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("approved reference camera missing")
    camera_copy = bpy.data.objects.new("approved reference camera", camera.data.copy())
    bpy.context.collection.objects.link(camera_copy)
    camera_copy.matrix_world = camera.matrix_world.copy()
    copies.append(camera_copy)

    metadata = bpy.data.objects.new("lush-slice-metadata", None)
    bpy.context.collection.objects.link(metadata)
    metadata["source_sha256"] = SOURCE_SHA256
    metadata["source_commit"] = "6dfd62d"
    metadata["blender_axes"] = "X right, Y away from viewer, Z up"
    metadata["three_axes"] = "X right, Y up, Z toward viewer"
    metadata["coordinate_map"] = "Three (x,y,z) = Blender (x,z,-y); metres"
    metadata["slice_x_min_blender"] = X_MIN
    metadata["slice_x_max_blender"] = X_MAX
    metadata["front_glass_y_blender"] = FRONT_GLASS_Y
    metadata["front_glass_z_three"] = -FRONT_GLASS_Y
    metadata["rear_y_blender"] = REAR_Y
    metadata["camera_lens_mm"] = camera.data.lens
    metadata["camera_sensor_width_mm"] = camera.data.sensor_width
    metadata["camera_resolution"] = "1920x1080"
    metadata["camera_position_blender"] = ",".join(f"{v:.6f}" for v in camera.matrix_world.translation)
    copies.append(metadata)

    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    for obj in copies:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT), export_format="GLB", use_selection=True,
        export_materials="EXPORT", export_normals=True, export_texcoords=True,
        export_yup=True, export_apply=False, export_animations=False,
        export_cameras=True, export_lights=False, export_extras=True,
    )
    print(json.dumps({
        "out": str(OUT), "bytes": OUT.stat().st_size,
        "mesh_objects": len(copies) - 2,
        "source_faces_selected": sum(len(obj.data.polygons) for obj in copies if obj.type == "MESH"),
        "materials_mapped": len(mapped),
        "source_sha256": SOURCE_SHA256,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
