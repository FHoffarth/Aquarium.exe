# Natural Environment Stage 1: hardscape material-presence test (offline)

Branch `claude/natural-env-stage1` (from the approved Pass 2 composition, `9c2db27`). This is an offline Blender test only: no runtime, wallpaper, fish or native change, and nothing is merged.

**Sketchfab could not be used.** Its downloads require an Epic Games login, which was declined, so the CC BY 4.0 roots (yelizegi, Lesterm) were not acquired. Their author, source URL, license URL and attribution line remain recorded in `art/provenance/stage1/` for any future use.

The test was redone login-free with Poly Haven CC0 sources, approved in chat:
- `single_root` and `root_cluster_02` (both by Jenelle van Heerden);
- `bark_willow_02`.

## What was compared

Every frame uses the same scene:
- the Pass 2 composition B, camera, light, water, grade and plants (vegetation reseeded identically);
- the same **scanned rock family**: Poly Haven `rock_07` (rear left), `boulder_01` (rear centre-left) and `rock_09` ×2 (front), with `rock_moss_set_02` for transition stones.

Only the wood differs:

| | Wood |
|---|---|
| **A** | Scanned-root reconstruction: raised root ridges cut from the two Poly Haven ground-patch scans, bent along the three approved gestures and the four surface roots with a Curve modifier, scaled to gesture length and girth. Minimal intervention: no sculpting, no invented undersides. |
| **B** | The approved procedural three-gesture root (unchanged silhouette), re-surfaced with `bark_willow_02` (diffuse, normal, ARM), fibre-aligned crack weathering, and graded to the same waterlogged brown target as Pass 2. |
| Reference | The current Pass 2 root and bark, with the same scanned rocks. |

## Evidence (`docs/evidence/natural-env-stage1/`)

- `A-full.png`, `B-full.png`, `REF-full.png`: 1920×1080 at the habitat camera.
- `A-close.png`, `B-close.png`, `REF-close.png`: hardscape close views.
- `comparison-A-B-reference.jpg`: one sheet; rows are A, B and reference, with the full frame on the left and the close view on the right.

## Findings

- **A fights the composition.** The Poly Haven "roots" are ground-patch scans: one continuous soil surface 12–19 cm deep, with the roots as low relief fused into it. They have no separable root objects, no undersides, and soil baked into the same texture.
  - Cut out and bent into rising gestures, they become thin, flat ribbons that read as grass blades or bent sticks, not wood.
  - Making A work would need invented volume and undersides, which is sculpting a new asset, not reusing a scan. As instructed, it was not attempted.
- **B supports composition B unchanged and gains real surface truth.** Fissured bark and fibre direction read at desktop distance; the close view shows scanned bark structure instead of our tiled twig bark.
  - The silhouette is still ours: smooth tapering tubes without scan-level branching irregularity.
  - It improves on the reference, but less decisively than the rocks do.
- **Scanned rocks are the clear win.** `boulder_01`, in particular, has real fractures, pitting and weight.
  - `rock_07` shows glossy white flecks and needs a roughness/specular correction.
  - The rocks are identical in all three frames, so they don't bias the root comparison.

## Cost (source → proposed runtime treatment)

| | Source | Runtime treatment (estimate) |
|---|---|---|
| **A** | `root_cluster_02`: 339,641 faces in 8 ground-patch pieces. `single_root`: 61,027 faces. 2K diffuse, normal and ARM each (29 MB download). Used: 7 extracted ridges, 42,244 faces. | Not viable as-is. It would need re-meshing into closed tubes (at which point it converges on B) plus baking the scan colour. Roughly 8–12k triangles and a 2K atlas **after** a substantial authoring step. |
| **B** | Procedural root: 3,192 faces offline (Slice B runtime root: ~5k triangles). `bark_willow_02`: 2K diffuse, normal and ARM (12.9 MB download). | A drop-in for Slice B: same mesh, plus a bark atlas at 1K–2K. Cracks and grading baked into albedo and normal; no extra runtime shader cost. ~5k triangles, 1 material, about 5–16 MB GPU texture memory with mips. |
| Rocks | `rock_07` 27,830 / `boulder_01` 123,976 / `rock_09` 23,280 faces; 4K maps. | Decimate to ~2.5–4k triangles each, bake 2K normal and albedo into one rock atlas; about 12–18k triangles for the family. |

## Provenance

- `art/provenance/stage1/acquisitions.json`: every file with URL, MD5 (publisher-verified), SHA-256, author, license and license URL.
- Raw sources are in `art/source/polyhaven/` (gitignored, never shipped).
- All CC0: no attribution required. The CC-BY credits path is prepared but unused.

**Next decision:** yours. No Stage 2 work has started.
