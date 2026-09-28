"""Export the FULL approved aquarium environment for the live 3D runtime.

Run from the repository root with Blender 5.2.2:
  blender -b art/work/lush-reference/lush-water-reference.blend \
    -P art/tools/export_lush_live_full.py

Unlike export_lush_live_slice.py (a narrow central X window, which cropped the
floor into an island and left two isolated plant towers), this keeps every
approved environment object whole: all seven plant groups, supporting stems,
the complete gravel bed, all wood pieces and stones, and the real rear
boundary. Modifiers (wood bevels) are applied as in the offline render.
Nothing is regenerated, decimated, flattened or repositioned. Offline fish,
particles, lights and the rendered plate are excluded.

The rear boundary keeps its geometry but gets a restrained deep blue-green
material instead of the source's bright blue ramp (a runtime proof stand-in;
the runtime may override it with its own rear material).
"""

import hashlib
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_lush_live_slice as S  # noqa: E402  (material mapping, source pin)

ROOT = S.ROOT
OUT = ROOT / "habitat/assets/lush-live/environment.glb"
PLANTS = S.PLANTS
GRAVEL = S.GRAVEL
HARDSCAPE = (
    "planted central wood", "planted central wood.001", "planted central wood.002", "planted central wood.003",
    "left branch", "left branch.001", "right branch", "right branch.001",
    "partly buried rock-09", "partly buried rock-07", "partly buried rock-07.001", "partly buried boulder",
)
REAR = S.REAR
REAR_COLOR = (0.028, 0.062, 0.066)     # linear: deep, desaturated freshwater blue-green

S.TEXTURE_BY_MATERIAL.update({
    "scanned stone rock-07": "rock07_albedo.webp",
    "scanned stone boulder": "boulder_albedo.webp",
})


def evaluated_copy(obj, depsgraph):
    """Whole object with its modifiers applied (as rendered offline)."""
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True,
                                           depsgraph=depsgraph)
    result = bpy.data.objects.new(obj.name, mesh)
    bpy.context.collection.objects.link(result)
    result.matrix_world = obj.matrix_world.copy()
    result["approved_source_object"] = obj.name
    result["selection"] = "complete object"
    return result


def main():
    if not S.SOURCE.is_file() or hashlib.sha256(S.SOURCE.read_bytes()).hexdigest() != S.SOURCE_SHA256:
        raise RuntimeError("approved Blender source is missing or differs from the pinned source SHA-256")
    if Path(bpy.data.filepath).resolve() != S.SOURCE.resolve():
        raise RuntimeError(f"open the pinned source .blend first: {S.SOURCE}")
    names = (*PLANTS, *GRAVEL, *HARDSCAPE, REAR)
    missing = [name for name in names if bpy.data.objects.get(name) is None]
    if missing:
        raise RuntimeError(f"approved geometry missing: {missing}")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    copies = [evaluated_copy(bpy.data.objects[name], depsgraph) for name in names]

    mapped = {}
    for obj in copies:
        for index, source_material in enumerate(obj.data.materials):
            if source_material is None:
                continue
            if source_material.name not in mapped:
                mapped[source_material.name] = S.pbr_material(source_material)
            obj.data.materials[index] = mapped[source_material.name]
    rear = mapped["clear blue depth"]
    rear.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*REAR_COLOR, 1)
    rear.diffuse_color = (*REAR_COLOR, 1)

    camera = bpy.data.objects.get("offline reference camera")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("approved reference camera missing")
    camera_copy = bpy.data.objects.new("approved reference camera", camera.data.copy())
    bpy.context.collection.objects.link(camera_copy)
    camera_copy.matrix_world = camera.matrix_world.copy()

    metadata = bpy.data.objects.new("lush-live-metadata", None)
    bpy.context.collection.objects.link(metadata)
    metadata["source_sha256"] = S.SOURCE_SHA256
    metadata["source_commit"] = "6dfd62d"
    metadata["selection"] = "full approved environment (no X window)"
    metadata["coordinate_map"] = "Three (x,y,z) = Blender (x,z,-y); metres"
    metadata["front_glass_z_three"] = -S.FRONT_GLASS_Y
    metadata["rear_z_three"] = -S.REAR_Y

    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    selected = [*copies, camera_copy, metadata]
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT), export_format="GLB", use_selection=True,
        export_materials="EXPORT", export_normals=True, export_texcoords=True,
        export_yup=True, export_apply=False, export_animations=False,
        export_cameras=True, export_lights=False, export_extras=True,
    )
    triangles = 0
    for obj in copies:
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
    print("LUSHLIVE " + json.dumps({
        "out": str(OUT.relative_to(ROOT)), "bytes": OUT.stat().st_size, "objects": len(copies),
        "triangles": triangles, "materials_mapped": len(mapped), "source_sha256": S.SOURCE_SHA256,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
