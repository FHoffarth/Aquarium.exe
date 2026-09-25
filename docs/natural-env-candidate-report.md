# Natural Environment Candidate (offline composition test)

Branch `claude/natural-env-stage1`. Offline Blender only. No runtime, wallpaper, fish-code or native change; nothing merged; no asset search.

`--plants candidate` in `art/tools/compose_hero_frame.py`. Renders come from `art/tools/render_candidate.sh`, sheets from `art/tools/candidate_sheets.py`.

## Vocabulary used (only what passed)

- **Scanned hardscape:** the Stage 1 Poly Haven rocks (`rock_07`, `boulder_01`, `rock_09`), the Composition B root and `bark_willow_02`. Same camera, light, water and grade.
- **Broad leaves:** Stage 2 `LeafSet022` only. `LeafSet003` is gone.
  - The strongest mass is at the left rock/root base and seams, with a few small clusters on stone and wood.
  - Density falls off toward the centre: two small groups at x −0.75 / −0.4, nothing in the right half.
- **Background:** no plants. Open dark water, depth haze and the existing light falloff only.
- **Substrate, no carpet:**
  - an irregular, noise-broken darker gravel/soil zone around the hardscape, opening to finer, lighter sand;
  - 45 partially buried fragments;
  - about 940 pieces of secondary gravel, clustered at the hardscape and thinning outward. Both use a decimated `rock_moss_set_02` stone, graded like the rocks.

## Moss test: REMOVED

**Scale correction.** The Hero Fish is 0.375 habitat units long, for a 4–5 cm fish, so 1 unit ≈ 12 cm. The `moss_01` sprigs (1.5–3.7 cm) are therefore at real scale at ≈ 8.3×. Pass 2's 6–11× was already roughly real scale, contrary to what I said in the gap search. The Pass 2 fern look came from sparse, upright, pale single sprigs, not from scale.

Two tests at real scale (8.3× ±15%, no enlargement):

- **q1** (`moss-test-q1-close-50pct.png`): dense cushions at every branch joint plus wood/stone contacts. Where the moss is visible (up on the branches), it reads as spiky conifer-like tufts.
- **q2** (`moss-test-q2-close-50pct.png`): believable low seams only, denser and flatter. The cushions disappear behind stone and leaves and contribute nothing at desktop distance.

Per the rule, `moss_01` is removed. It stays available only behind `--moss on`, off by default.

## Evidence (`docs/evidence/natural-env-candidate/`)

| File | Content |
|---|---|
| `CANDIDATE-full.png` | Final candidate, 1920×1080, 64 samples |
| `CANDIDATE-close.png` | Hardscape close-up |
| `CANDIDATE-fish.png` | With Hero Fish 1B at desktop scale 0.75 (offline static pose) |
| `comparison-candidate-vs-runtime-pass2.jpg` | Candidate, runtime Slice B (real host capture, `claude/aquascape-runtime-slice-b`), Pass 2 hero frame, candidate with fish |
| `blur-silhouette-check.jpg` | The same four frames downsampled ×16 and blurred |
| `moss-test-q1/q2-close-50pct.png` | The two moss tests (50% preview renders) |

## Reading at desktop distance

**Better than both references:**
- The hardscape reads as real material: scanned stone, bark and photographed leaves under one light.
- It is the first frame with no reed wall, hedge, wheat field or agave rosettes.
- The broad-leaf mass anchors the rocks and root base with dark gaps and a size hierarchy.
- The blur check shows one clear mass at the left and calm open water on the right.
- The fish silhouettes read cleanly against the dark teal.

**Still synthetic (composition, not assets):**
- **The floor.** It is about 40% of the frame height, and the substrate now carries almost the whole lower half.
  - Right of centre it reads as a large, uniform sand plane: an empty seabed, not an aquarium floor.
  - The gravel zone and fragments register only faintly at 1920×1080.
- **The horizon.** Substrate meets water in a straight, hard line, which reads as an endless seabed rather than depth inside a tank.
- **Smaller issues:**
  - `rock_07` still has glossy white flecks (a known roughness fix).
  - A few leaves catch a pale specular sheen.
  - Leaf groups on the top of the dark rock look placed rather than rooted.

## Runtime budget (derived, estimate)

| Element | Treatment | Triangles | GPU texture (with mips) |
|---|---|---|---|
| Scanned rocks (4 hero + secondaries) | Decimate to 2.5–4k each; bake albedo and normal into one 2K rock atlas | ~18–22k | ~11 MB |
| Root | Slice B mesh plus `bark_willow_02` (cracks and grade baked) | ~5k | ~3–11 MB (1K–2K) |
| LeafSet022 clusters | ~6 camera-specific baked clusters, 6-row outline strips, alpha test only at rims | ~8–10k | ~3–11 MB |
| Fragments / gravel | Fragments share the rock atlas; gravel baked into the substrate albedo/normal | ~5–7k | 0 extra |
| Substrate | Re-bake the Slice B substrate with the soil/sand mask, no carpet | as Slice B | as Slice B |
| Moss / background plants | None | 0 | 0 |
| **Environment total** | | **~40–50k** (Slice B env: 53k) | **~20–35 MB** |

- **Draw calls:** about 6–8 for the environment (rocks, fragments, root, leaves, substrate, backdrop), no more than Slice B.
- **Overdraw:** clearly lower than Slice B. The camera-facing stem cards, ribbons and carpet are gone, and the only alpha is at leaf rims.
- **Fish:** unchanged.

## Decision input

- **Vocabulary:** the materials pass the "natural enough" bar at desktop distance: scanned rocks, willow bark, LeafSet022 and open water.
- **Remaining gap:** the synthetic part is now the ground plane and the horizon line, which carry ~40% of the frame. That is a camera, haze and grade problem, not an asset gap. Addressing it would mean runtime camera and fog choices, which are out of scope here.

**READY FOR VISUAL REVIEW:** A (integrate this vocabulary) or B (stop and reconsider). Your call.
