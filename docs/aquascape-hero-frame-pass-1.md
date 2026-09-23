# Aquascape Hero Composition Pass 1

Branch `claude/aquascape-hero-frame` (from Slice A `c15957e`). This is composition only: no runtime integration, no changes to the scene code, host, simulation or Hero Fish. Not merged.

**AQUASCAPE HERO FRAME: READY FOR VISUAL REVIEW**

## 1. Chosen concept: B, a left root mass with sweeping diagonals

Three low-cost clay studies were compared (`docs/evidence/aquascape-hero-frame/studies-clay.jpg`):

| Study | Read | Verdict |
|---|---|---|
| A: strong left triangular hardscape | a single dominant boulder; static; no flow into the open water | rejected |
| **B: left root mass, sweeping diagonal branches** | a hardscape that grows from the substrate; the diagonals carry the eye up-right into the open water | **chosen** |
| C: lower-left island, open upper water | calm, but flat and weak; no focal energy | rejected |

B was the only study that answered the flow question: the eye moves from the hardscape, along the diagonal, into open water, then into depth. Only B was refined.

Frame structure, dense to open:

- **Left third:** the visual anchor. Two primary stones (rear), two secondary stones (front) and a trail of transition stones, all partly buried. The driftwood root emerges between them. Moss is concentrated on the upper wood, the branch joints and the rock/wood contact. Broad-leaf masses sit at the rock bases, small dark leaf clusters on the stones, and fern-like tufts in the wood.
- **Far-left column:** kept low and dark, because that is where Windows places desktop icons. The top-left is quiet water.
- **Centre:** transition. The hero branch reaches over the midground, a low stem-plant band and hairgrass tufts lead the eye right, and a sand clearing opens from the front centre and curves back to the right.
- **Right:** mostly open swimming water. A soft clump of tall ribbon plants at the back right leans with an implied current and frames the open space without filling it.
- **Top:** quiet water with a few restrained light shafts from the upper left.

## 2. Depth layers

1. **Foreground:** a low, continuous round-leaf carpet with organic noise-driven edges, densest around the hardscape base, thinning to the right and absent on the sand clearing. A few small rosettes and hairgrass tufts. No wall of foreground plants.
2. **Midground:** the hardscape (wood, stones, moss, epiphytes), a low mid-back stem-plant band and hairgrass in the transition.
3. **Background:** taller stem-plant masses behind the hardscape (several distinct plant characters), a continuous low band along the back that hides the substrate/back-glass line, and tall ribbon clumps at the back right and back left.
4. **Open water:** centre-right and the whole upper frame.
5. **Distant depth:** a denser water volume toward the back, so distant plants dissolve into teal, plus a dark background film behind the tank. The frame never reads as objects against a flat wall.

**Lighting:** a warm key light from the upper left and front, a dim cool front fill, a surface-ripple occluder whose holes cast soft moving-water light through the volume, and faint additive shafts from the upper left. Caustics fall on up-facing substrate, stone and wood only; they are barely present on leaves.

**Grade** (`art/tools/grade_hero_frame.py`): darker lower corners and edges, and a gentle cool-shadow / warm-highlight split. An ungraded copy is included.

## 3. Evidence (`docs/evidence/aquascape-hero-frame/`)

| | File |
|---|---|
| **Hero frame, 1920×1080, without fish** | `hero-frame-1920x1080.png` |
| Hero frame, ungraded | `hero-frame-ungraded.jpg` |
| Clay / silhouette composition frame (same light, one neutral material) | `clay-silhouette-1920x1080.png` |
| Optional: three small neutral fish silhouettes for scale | `hero-frame-with-fish-for-scale.png` |
| Blur / downscale test | `blur-test.png` |
| Composition studies A/B/C (clay, half resolution) | `studies-clay.jpg` |
| Iteration history of B (half resolution) | `iterations-B.jpg` |

## 4. Silhouette and blur tests

**Clay frame:**
- a clear focal mass in the left third;
- the left feels anchored: stones sunk 30–42%, wood entering the substrate, roots running over and into it;
- the centre and right are open;
- the diagonal leads the eye to the open water;
- the back band and haze give depth.

**Blur test** (1/16 downscale, then blurred): the image still separates into dark water, a left hardscape mass, green planting along the bottom and back, and open swimming space centre-right. It does not collapse into uniform noise.

## 5. Existing assets used

All are approved CC0 Poly Haven sources already fetched for Slice A; nothing new was downloaded.

| Source | Use |
|---|---|
| `rock_moss_set_02` (rocks 08–13) | Two primary, two secondary and two transition stones, plus 12 small trail stones. Partly buried, re-graded darker and less saturated. |
| `moss_01` | About 1,500 sprigs on the upper wood, joints, rock tops and rock/wood transitions. Own material (dithered alpha, hue shifted toward aquatic green). |
| `dry_branches_medium_01` | **Bark texture only** (diffuse and normal), darkened and desaturated, and mixed with procedural along-grain fibres for waterlogged driftwood. |
| `gravelly_sand` | Main substrate. |
| `coast_sand_03` | Sand clearing (blended at 70%, so the clearing is subtle rather than a path). |

## 6. Existing assets deliberately rejected

| Source | Reason |
|---|---|
| `fern_02` | Reads as forest-floor fern. |
| `nettle_plant` | Reads as a roadside weed; the old right-hand "stem" cards came from it. |
| `shrub_sorrel_01` | Clover-like: a terrestrial ground cover. |
| `anthurium_botany_01` | Reads as a houseplant at the scale needed for aquarium broad-leaf plants. |
| `dry_branches_medium_01` **geometry** | Twig-proportioned. Kitbashed at hero scale it gave the floating "Kraken arm" and the cut-stump faces. |

## 7. Custom geometry (all procedural, in `art/tools/compose_hero_frame.py`)

- **Driftwood root:** tapered tubes with parallel-transport frames and real bark UVs along the grain. Gnarled radius, noise-bent spines, four main limbs (a hero sweep to the centre, a steep rise, a back-left arm and a secondary rise), four surface roots that run over and into the substrate, side twigs, and forked tips so no limb ends in a single horn.
- **Substrate:** a mound under the hardscape, a slope toward the back, a low right side, and a slightly lowered, noise-edged clearing. Contact and depth darkening via attributes.
- **Aquatic vegetation** (no botanical species claims; forms are chosen to read as aquatic):
  - round-leaf foreground carpet: 6-leaf discs forming a cushion (the densest layer);
  - hairgrass-like blades;
  - broad-leaf rosettes: elliptic, folded, glossy dark;
  - small lanceolate dark clusters on stones;
  - fern-like tufts on the wood: long, wavy, twisted lance leaves;
  - small crypt-like rosettes;
  - stem plants in four characters: whorl count, leaf size and top tint vary per bush, with restrained warm tips on one character;
  - tall ribbon plants that lean with the current and twist toward the camera.
- **Water:** the main volume (teal scatter and absorption), a denser back volume, a dark background film, a surface-ripple shadow occluder, soft light-shaft sheets and about 70 barely visible particles.

## 8. New external assets proposed

None are required for this frame, and none were downloaded. If a later pass wants more botanical richness, candidates would be CC0 aquatic-plant scans (a broad-leaf rhizome plant or a real moss clump scan). Each would need explicit per-asset approval under the GREEN-only policy.

## 9. Rough runtime complexity estimate (for the later integration pass)

The offline scene is about 0.9–1.1 M triangles, dominated by the carpet (~0.2 M) and stem plants (~0.4 M). That is not a runtime budget. A faithful runtime rebuild would use:

| Layer | Runtime approach | Estimate |
|---|---|---|
| Stones | decimated meshes, one draw | ~18k tris |
| Driftwood | baked, decimated tube mesh | ~6–8k tris |
| Moss | a few hundred sprigs merged into one mesh (alpha test), or a moss decal band on the wood | ~10–15k tris |
| Carpet | instanced leaf clusters (≈2k instances × ~30 tris) or camera-facing cards from the fixed view | 20–60k tris |
| Stem plants and ribbons | camera-facing card atlases (the camera is fixed) plus a few mesh ribbons for sway | ~10–20k tris |
| Broad-leaf, epiphytes, hairgrass | merged meshes | ~15k tris |
| Substrate | the existing baked-substrate approach | ~6k tris |
| Water, haze, shafts, caustics, particles | existing Slice A effect uniforms (depth haze, caustics, shafts) | shader only |

That gives roughly 90–140k triangles and 10–14 draw calls with atlasing. This is comparable to Slice A's 90k-triangle / 8-primitive budget, but would need that budget raised modestly or the carpet carded.

**Integration risks:**
- The fish swim volume (z −0.65…0.65) overlaps the hero branch's reach; the branch sits at z −0.85…−1.2, behind it.
- The post grade (vignette, split tone) would move into the existing background/haze shader.

## 10. Known weaknesses

- **The driftwood is a procedural tube root.** Convincing at wallpaper scale, but its bark is less detailed up close than a scanned root would be.
- **Stem plants are fine at desktop distance,** but read somewhat uniform within a bush close up.
- **The substrate/back-glass line is hidden by the back band,** and still faintly visible at the extreme left and right edges (darkened by the grade).
- **The frame uses the runtime camera (38° fov, centred).** That camera gives the substrate ~35% of the frame height, more than typical aquascape photography. A slightly lower camera or narrower lens would help if the camera may change later.
- **Light shafts are faked as additive sheets.** EEVEE volumetric shadows alone were too weak at this water density.
