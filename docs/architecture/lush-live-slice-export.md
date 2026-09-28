# Approved live environment slice: export record

This is implementation commit 1 of [the live underwater architecture spike](live-underwater-runtime-spike.md). It prepares a GLB only. The default Aquarium.exe scene, Hero Fish, host, lighting, and water renderer are unchanged. The neutral [geometry inspection frame](../evidence/lush-slice/geometry-inspection-1920.png) shows the exported asset without runtime fish, water, fog, effects, or final lighting. Its visible left/right floor cut edges are expected in this deliberately narrow proof, not a proposed full-tank composition.

## Repeatable source and commands

- Source of truth: local `art/work/lush-reference/lush-water-reference.blend`, SHA-256 `a43f49fb006b3a5ac7128f5d2faf0af978e983d85ea4e981b29d0cc67af54b93`. This file is Git-ignored; the exporter refuses a missing or changed source. The art-direction commit is `6dfd62d`.
- Exporter: `art/tools/export_lush_live_slice.py`, run with Blender 5.2.2 from the repository root: `blender -b art/work/lush-reference/lush-water-reference.blend -P art/tools/export_lush_live_slice.py`.
- Validation: `node art/tools/validate_lush_live_slice.mjs`. It parses the GLB with the repository's vendored Three.js `GLTFLoader`, inspects embedded WebP headers, checks metadata and spatial layer ordering, and verifies broad-leaf depth-write/alpha-test behavior.
- Optional neutral frame: `blender -b --factory-startup -P art/tools/render_lush_slice_inspection.py`.
- GLB output: `habitat/assets/lush-slice/environment.glb`, SHA-256 `333d8a93a698a75ae1eb64aa032290f6639bc2ccdb01535cee5e4ce8153e7791`. Two consecutive exports of the final script produced identical hashes. The `.blend` remains unmodified.

## Selection and spatial metadata

Plant geometry is selected as complete connected leaf/stem pieces whose original world-space X centers are between **−3.3 and +3.3 Blender units**. This avoids cutting individual leaves. Existing ground and loose gravel faces are selected by their center in that interval, with fine gravel openings limited to Blender Y ≤ 1.5. The wood/stone proof uses three existing central wood sections and the existing partly buried rock-09. The source rear boundary and approved perspective camera are included. No geometry is generated, decimated, flattened, or repositioned. The wide original rear boundary remains intact (12 triangles) so its sides and back enclose the slice; the selected plant/ground region is central only.

Blender's scene is X-right, Y-away, Z-up. The glTF Y-up export maps `(X, Y, Z)_Three = (X, Z, −Y)_Blender` in the same scene units. The camera exported in the GLB is at `(0, 6.6, 15.3)` in Three coordinates, with 48 mm lens / 36 mm sensor, aspect 16:9, vertical FOV **23.8224°**, near 0.1, far 1000. Blender camera position is `(0, −15.3, 6.6)`. The source glass/front plane is Blender Y **−5.0**, or Three Z **+5.0**. The rear boundary is around Blender Y **+4.8**, or Three Z **−4.8**. These values and the source hash are also stored on the GLB's `lush-slice-metadata` node as glTF extras; the camera is an actual glTF camera node. Future runtime code will need to consume that metadata deliberately because the current `loadArtGroup()` API returns mesh and texture maps only.

The vendored loader reports these separated Three-Z ranges: foreground low plants **+0.086 to +2.677**, middle small-leaf bushes **−2.268 to +0.623**, rear fine feather plants **−4.210 to −2.347**, rear boundary **−4.825 to −4.775**. This proves multiple real depth layers are present; it does not yet prove moving fish occlusion, which belongs to the next runtime slice.

## Materials and embedded textures

The source Cycles node graphs cannot map directly to glTF PBR. Each used source material retains its name/identity and is mapped to a minimal Principled glTF material using its original base-color, roughness, and metallic values where available. Source procedural leaf noise, bumps, camera-distance mixes, transmission and Cycles lighting are deliberately absent. The rear material uses the midpoint of its source blue color ramp as a neutral PBR stand-in; it is actual rear geometry, not a baked aquarium image. Existing UVs and object transforms survive the export.

| Source material family | Export treatment |
| --- | --- |
| Procedural leaves, stems, gravel | Original source base color in PBR; no new texture. Thin foliage is double sided and opaque, so it writes depth. |
| Photographed broad leaves | Existing `leaves_albedo.webp` (1024 × 1024) is embedded. Double sided glTF `MASK` at alpha cutoff 0.45; vendored loader gives `depthWrite=true` and `alphaTest≈0.45`. |
| Central wood | Existing `wood_albedo.webp` (1024 × 1024) is embedded. |
| Rock-09 | Existing `rock09_albedo.webp` (512 × 512) is embedded. |
| Rear boundary | Existing source blue ramp midpoint as plain PBR color. The full ramp and water treatment are deferred. |

No plate image is embedded. There are three WebP textures total, about **12 MiB decoded RGBA8 with mipmaps**. Their compressed payloads are 73,864, 197,780, and 47,466 bytes respectively. No new external asset or dependency was added.

## GLB inspection result

| Measure | Export |
| --- | ---: |
| File size | 4,661,760 bytes (4.45 MiB) |
| glTF source meshes | 16 |
| Runtime render meshes / primitives | 57 / 57 |
| Used glTF materials | 28 |
| Triangles | 95,552 |
| Exported position vertices across primitives | 117,401 |
| Embedded textures | 3 WebP, listed above |
| Whole GLB bounds, Three XYZ | min `(−8.5, −0.6, −4.825)`, max `(+8.5, +7.4, +5.0)` |

The wide X bound comes from the unchanged rear boundary, not the selected central plants. The 57 primitives preserve source material variation rather than prematurely merging distinct vegetation. This is an export proof, not a performance claim for a full live aquarium.

The GLB contains **no posed Blender fish, no offline water particles, and no static environment plate**. The 1920 × 1080 inspection frame was rendered by importing this GLB back into Blender and adding one neutral sun plus ambient light; it checks geometry/camera/material transfer only. It is intentionally not an art acceptance image.

## Validation boundary

The same vendored `GLTFLoader` parsed the GLB in Node with a bitmap stub, and Blender reimported and rendered its embedded images. The bitmap stub does not exercise WebView2 image decoding; the Blender reimport checks the image payloads independently. Asset manifest integrity and texture/geometry budget tests cover the shipped file. Runtime FPS, moving fish occlusion, underwater appearance, and true pause idle must be measured in later implementation commits; no runtime path loads this group by default.
