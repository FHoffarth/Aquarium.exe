# Natural Environment Stage 2: natural plant material study (offline)

Branch `claude/natural-env-stage1`. Offline Blender only: no runtime, wallpaper, fish or native change; nothing merged.

## Setup

- **Hardscape is identical to the accepted Stage 1 B:** scanned rock family (`rock_07`, `boulder_01`, `rock_09`), Composition B root with `bark_willow_02`, same camera, light, water and grade.
- **Only the vegetation differs.**
  - `--plants natural` builds camera-specific clusters from photographed ambientCG leaf atlases.
  - The reference is the current Pass 2 vegetation (the Stage 1 `B-full` / `B-close` renders, produced with the same arguments).
- **Leaf construction:** each photographed leaf is cut from its atlas along its own opacity outline (`art/tools/leaf_atlas_profiles.py`, 14 rows × 3 vertices). It becomes a tight curved strip (arch, fold, twist), not a transparent card, so alpha only exists at the leaf rim.
- **Rendering:** `art/tools/render_stage2.sh` (1920×1080, 64 samples), `grade_hero_frame.py`, `art/tools/stage2_comparison_sheet.py`.

## Evidence (`docs/evidence/natural-env-stage2/`)

- `NATURAL-full.png`: all three families.
- `NATURAL-nostems-full.png`: the same frame without the LeafSet002 stem masses, to judge the background without them.
- `REF-full.png`: Pass 2 vegetation, same hardscape.
- `NATURAL-close.png` and `REF-close.png`: hardscape/plant close-ups.
- `comparison-natural-vs-pass2.jpg`: one sheet.

## Verdicts (judged at 1920×1080 first)

| Family | Sources | Verdict |
|---|---|---|
| 1. Broad/medium leaf mass | LeafSet022 (main), LeafSet003 | **PASS** for the hardscape-base and seam masses. Midground singles on open sand: **MAYBE** |
| 2. Moss / low ground transition | Moss004, Moss002 | **FAIL** |
| 3. Tall/background mass | Foliage001/008 ribbons, LeafSet002 stems | **FAIL** (LeafSet002 rejected; Foliage blades read as reeds or grass) |

### 1. Broad leaf mass: PASS (the base mass)

- **At desktop distance:** the rock/wood base reads as real overlapping leaf masses.
  - Photographic venation, spots and colour variation within a cluster.
  - Irregular silhouettes, dark gaps between leaves, and a clear size hierarchy (small inner leaves, larger outer ones).
  - This is a clear step up from the Pass 2 rosettes, which read as agave or spiky star shapes.
- **Camera-specific clusters are required.** At this almost horizontal camera, flat-lying leaves collapse into slivers. Leaf planes are therefore biased toward the camera.
- **Caveats:**
  - LeafSet003's slightly serrated margin reads terrestrial in the close-up; LeafSet022 alone is safer.
  - A few leaves catch too much light and read glossy-pale (ficus/houseplant).
  - The isolated rosettes on open sand (right midground) read as seedlings, not aquarium plants. They belong only at contacts.

### 2. Moss / contact transition: FAIL, gap reported

- **On wood and rock:** the Moss004/002 textures on ray-projected cushion shells (surface-hugging, rim frayed by the moss height map) read as grey-green paint, lichen or stuck-on paper patches with hard outlines.
- **On the ground:** the low transition is practically invisible at desktop distance.
- **Why:** a tileable *surface* photo has no fringe, depth or silhouette, and moss reads through its fuzzy edge and volume.
- **The gap:** moss needs a volumetric source.
  - Options: a scanned moss clump or cushion, or strand/fringe cards built from an alpha moss atlas (a CC0 "moss clump" or "moss atlas" with opacity).
  - The two approved surfaces can serve only as the albedo/normal inside such a shape.
  - No attempt was made to invent moss procedurally.
- **Side effect to note:** without the Pass 2 carpet, the foreground ground plane is now largely bare sand. That is honest, but the frame loses its green floor.

### 3. Background: FAIL

- **LeafSet002: rejected.**
  - Stacked along stems, the boxwood twigs read at desktop distance as clipped boxwood/thuja columns: a hedge wall, terrestrial.
  - It gets worse at close range.
  - Density and haze would only hide this, as the brief warned.
- **Foliage001/008:**
  - The blades are narrow, stiff and pointed. Even widened and camera-faced, they read as tall reeds or grass blades, not soft submerged ribbons.
  - They lack the width, parallel venation and soft transparency of ribbon vegetation.
  - Stems off (`NATURAL-nostems-full`), the background is honest but empty.
- **The gap:** a wide ribbon-leaf atlas, or a tall aquatic stem-plant atlas (whorled soft leaves), is needed. None of the approved sources covers it.

## Source / license / provenance

All eight sources are ambientCG, **CC0-1.0** (creator: ambientCG, Lennart Demes; license https://docs.ambientcg.com/license/), 2K-JPG. No attribution is required, but it is recorded.

| Asset | Used for | Result |
|---|---|---|
| LeafSet022 | broad leaves (main) | keep |
| LeafSet003 | broad leaves (secondary) | maybe (serrated) |
| LeafSet001 | not used (beech-like, terrestrial) | reject |
| Moss004 | moss cushions | fail (surface only) |
| Moss002 | ground mats | fail (surface only) |
| Foliage001 | ribbons (main) | fail (reads as reed/grass) |
| Foliage008 | ribbons | fail |
| LeafSet002 | stem masses | reject (hedge/boxwood) |

- **Per-file records:** `art/provenance/stage2/acquisitions.json` has the download URL, archive SHA-256 and per-file SHA-256.
- **API snapshot:** `ambientcg.full_json.json`.
- **Raw files:** `art/source/ambientcg/` (gitignored; about 152 MB of source material, not a runtime budget).

## Rough runtime treatment and cost (family 1 only)

**Offline:**
- LeafSet022 + LeafSet003 leaves: 19,236 faces (about 690 leaves × 28 faces).
- Moss shells: 15,228 faces.
- Ribbons: 1,820 faces.
- LeafSet002 stems: 22,568 faces.
- **Total vegetation:** about 59k faces, against about 1.58M in the Pass 2 reference (dominated by the carpet and stems).

**Proposed runtime (broad leaves only):**

| | |
|---|---|
| Geometry | 6–10 baked cluster meshes (camera-specific, placed at the seams); leaf strips reduced to 6 rows × 2 → about 8–10k triangles; 1 draw call per material (1–2 total) |
| Texture | One 2K leaf atlas cropped from LeafSet022 (albedo pre-graded + normal): about 5–11 MB GPU with mips; JPG/PNG (no KTX2) |
| Overdraw | Low: tight outline strips mean alpha only at the leaf rim (alpha-test, no blending) |
| Shader | Existing standard material with alpha test and a translucency term. No new passes. |

Moss and background have no runtime estimate: they failed and would need new sources first.

## Recommendation

- **Family 1:** READY FOR VISUAL REVIEW. LeafSet022 is the proposed broad-leaf source.
- **Families 2 and 3:** they fail with the approved sources. Should they get a narrowly targeted source search? That is your decision:
  - a volumetric moss clump or fringe atlas;
  - a wide submerged-ribbon or soft stem-plant atlas.

No integration and no further search have started.
