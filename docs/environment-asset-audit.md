# Aquarium Environment Asset Audit

Branch `claude/environment-asset-audit`, from runtime `099cc72` (Slice B). Research only: nothing was downloaded for production, no runtime/shader/fish/build/native file was touched, and the running wallpaper is unchanged.

Licenses were verified at the source:
- Poly Haven license page;
- ambientCG license page (`docs.ambientcg.com/license`);
- Sketchfab's per-model API (`license.slug` / `license.url`) plus the model description.

Contact sheets of source previews are for internal evaluation only and are **not committed**: `art/work/asset-audit/contact_{sketchfab,wood,polyhaven,ambientcg}.jpg` (gitignored).

## 1. Why the current environment looks synthetic

1. **The vegetation has no real leaf information.** Every Slice B plant is our own generator's geometry: flat vertex colour, no venation, no translucency variation, identical leaf outlines. At desktop distance the eye reads repeated identical silhouettes, so it reads as procedural.
2. **Background stems are one card family** (4 characters × 2 variants), seen 59 times at similar heights, so the background forms a hedge.
3. **The carpet is a texture, not a surface.** A top-down render baked into the floor has no silhouette or self-shadow, so it looks pasted.
4. **The hardscape has the right gesture but no material truth.** The procedural root has tube topology with a tiled bark map: no cracks, no hollow ends, no fibre direction changes at junctions. The rocks are pale and uniformly lit, so they read as props.
5. **Transitions are constructed.** Nothing physically overlaps across the seams: moss is sprig cards, and no plant grows out of a crevice. Each element ends where the next begins.
6. **Moss is built from single sprig cards** (moss_01), which is why it reads spiky.
7. **Floor dominance** follows from 1–3: when nothing on the floor has relief, the floor is just a large flat texture.

**Conclusion:** the problem is source data, not placement. Real scanned leaf, moss, root and stone data is what's missing. A better generator would not fix it.

## 2. Existing repo assets

| Asset | Current use | Verdict | Why |
|---|---|---|---|
| `rock_moss_set_02` (PH, CC0) | all Slice A/B rocks | **KEEP (secondary role)** | Good real stones. Too pale and too uniform to carry the primary masses. Keep for secondary and transition stones and pebbles; give the primary role to darker, more weathered scans. |
| `dry_branches_medium_01` (PH, CC0) | Slice B: bark texture only | **REJECT** (after Stage 1) | Twig-scale bark tiled on procedural tubes is part of the "realtime prop" look. A real root scan brings its own bark. |
| `moss_01` (PH, CC0) | moss sprig cards | **REJECT** | Individual sprigs on cards read as spikes. Aquarium moss reads as a dense cushion or mat. |
| `gravelly_sand` (PH, CC0) | substrate base | **MAYBE → replace** | Beach-beige and coarse. The runtime already had to darken it heavily. Better dark "aquasoil" candidates exist. |
| `coast_sand_03` (PH, CC0) | sand clearing | **MAYBE** | Acceptable for the clearing. `sand_02` or ambientCG fine gravel read more like aquarium sand. |
| `anthurium_botany_01` (PH, CC0) | rejected | **REJECT** | Houseplant. No extraordinary reason found. |
| `fern_02` (PH, CC0) | rejected | **REJECT** | Forest-floor fern. |
| `nettle_plant` (PH, CC0) | rejected | **REJECT** | Roadside weed. |
| `shrub_sorrel_01` (PH, CC0) | rejected | **REJECT** | Clover ground cover. |
| Procedural driftwood tubes (ours) | Slice B wood | **REJECT** (Stage 1) | Correct composition gestures, wrong material truth. Keep the gestures as the placement target only. |
| Procedural leaves, stem cards, carpet bake (ours) | Slice B plants | **REJECT** (Stages 2–3) | The source of "procedural broccoli". |

## 3. Recommended strategy: hybrid, scan-derived, camera-baked (B + C + D)

- **Hardscape: real scans (strategy A/B).** Decimate aggressively and cut hidden back faces for the fixed camera. Bake the high-poly detail into 1–2K normal and albedo maps. Bake contact AO into vertex colour.
- **Plants: real scanned leaf data, re-composed (C/D).** Take a few scanned specimens per role and:
  - decimate each to an opaque cluster mesh (no alpha on leaves; scanned leaves are real geometry);
  - build 3–5 cluster variants per role by rotation, scale and leaf-subset selection;
  - place them as intentional masses.

  This beats alpha foliage for our overdraw-bound GPU: a 3k-triangle opaque cluster costs less than a stack of alpha cards.
- **Background stems: cards baked from a real scan (D).** They sit in haze at a fixed angle, so cards are appropriate here and only here. The difference from today is the source: real *Egeria* geometry rendered in several clump arrangements and lightings, instead of our generator.
- **Moss and carpet: shell meshes.** A low-poly cushion or mat mesh, opaque, with baked colour and normals from the moss scans; only the rim needs alpha. This fixes both the spiky moss and the pasted carpet with low overdraw.
- **Substrate:** a real dark planted-soil texture, real fine sand for the clearing, and a blend mask, as today but from better sources.

No strategy relies on large overlapping transparent foliage.

## 4. Candidate shortlist

Legend:
- **PH** = Poly Haven, **ACG** = ambientCG, **SF** = Sketchfab.
- CC0 = CC0 1.0 (no attribution required).
- CC-BY = CC BY 4.0: commercial use, modification and redistribution allowed, with attribution. Under our asset policy that is **REVIEW**, needing explicit per-asset approval plus a credits/NOTICE entry.
- "faces" are source counts.

### Rocks / stone

| Candidate | Source / URL | License, author | Source cost | Fit | Runtime treatment | Risks |
|---|---|---|---|---|---|---|
| **rock_09** | PH https://polyhaven.com/a/rock_09 | CC0, Jenelle van Heerden | 23k faces, textures up to 8K | Dark, deeply weathered, fractured slab (74×145×33 cm). Reads like aquascaping stone when dark-graded. | Primary stone, 2–3 rotated instances, ~3k tris each, 2K atlas | Warm tint needs grading toward charcoal |
| **rock_07** | PH https://polyhaven.com/a/rock_07 | CC0, Jenelle van Heerden | 28k faces, 8K | Massive dark-brown block with strong planes. A good primary anchor. | Primary, ~3k tris | Single strong form; use one instance only |
| **boulder_01** | PH https://polyhaven.com/a/boulder_01 | CC0, Rico Cilliers | 124k faces, 8K | Eroded, holed, lichen surface; the most "material presence". | One hero stone decimated to ~4k, baked normal | Lichen colour must be graded down; heavy source |
| **rock_moss_set_02** (have) | PH https://polyhaven.com/a/rock_moss_set_02 | CC0, Kless Gyzen | 58k (7 rocks) | Secondary and transition stones, pebbles | As today | Pale; grade darker |
| rock_moss_set_01 | PH https://polyhaven.com/a/rock_moss_set_01 | CC0, Kless Gyzen | 63k | Same family, more variety | Secondary | Same tone issue |
| *Rejected* | PH namaqualand_boulder_0x, stone_01, moon_rock_*; SF "Climbing/Dragon stone" (5.8k, CC-BY), "Roca de Dragón" (3.3k, CC-BY) | – | – | Desert orange / quartz / lunar; the SF "dragon stones" are low-poly game rocks | – | – |

### Driftwood / root wood

No good CC0 candidates exist. Every convincing branching root found is CC-BY 4.0. The PH roots (`root_cluster_01/02`, `single_root`, `pine_roots`) are roots embedded in a ground patch, not freestanding wood. PH `dead_quiver_branch_01/02` are smooth pale forks: the same tusk problem we already have.

| Candidate | Source / URL | License, author | Source cost | Fit | Runtime treatment | Risks |
|---|---|---|---|---|---|---|
| **Rathtrevor Beached Tree Root** | SF https://sketchfab.com/3d-models/rathtrevor-beached-tree-root-31ac4c155b074b5ab9b73396aa165eb5 | CC-BY 4.0, Lesterm | 76k faces | A dense, spidery, bleached root mass: exactly the "spider/root wood" silhouette of high-end aquascapes | Hero root, cut to camera-visible side, ~8k tris, 2K baked albedo+normal, darkened (waterlogged) | Bleached colour needs strong grading; attribution |
| **Real Aquarium Wood 3D scan** | SF https://sketchfab.com/3d-models/real-aquarium-wood-3d-scan-c53807eff7c4427faacfde6c1b581532 | CC-BY 4.0, grafi (zdenkoroman) | 40k faces (low-poly photogrammetry) | An actual aquarium root with natural taper and cracks | Secondary root or the low back-left gesture, ~5k tris | Small single piece; must combine with the hero root |
| **Decorative driftwood** | SF https://sketchfab.com/3d-models/decorative-driftwood-5fe23ea13be54e56b99325e2fb0bf681 | CC-BY 4.0, yelizegi | 1.0M faces, HD textures | The most beautiful sweeping, twisted gestures, a close match to the approved diagonal | Hero sweep, heavily decimated (~8–10k), baked from the 1M source | Heavy source; long bake; attribution |
| Driftwood 3D scan | SF https://sketchfab.com/3d-models/driftwood-3d-scan-mJUa0nux6YAp3LqHPWmxHuBgVRr | CC-BY 4.0, jasonwebb | 68k | Multi-branch weathered bundle | Alternative hero root | Scan from 2013; texture quality unknown |
| *Rejected* | SF Driftwood Scan (HeartOfLines), Driftwood (Lion1469), Uprooted Stump, Dried tree root, Roots Photogrammetry, Mossy Root, Large Pine Driftwood; SF "Driftwood Scan" by milkislegit (CC-BY-**NC**) | – | – | Single thin stick, flat log, stumps with ground, or a non-commercial license | – | – |

### Broad-leaf plants (Anubias / Java-fern type)

| Candidate | Source / URL | License, author | Source cost | Fit | Runtime treatment | Risks |
|---|---|---|---|---|---|---|
| **Aquariumplants like Anubia Barteri** | SF https://sketchfab.com/3d-models/aquariumplants-like-anubia-barteri-4dbbcb2abf864ee2af70ea7f2b2c691e | CC-BY 4.0, Nullified (Nullifiedit) | 198k faces | Real aquarium Anubias forms (the author's own aquarium plants) | 3–4 opaque cluster variants at ~2.5k tris, instanced at rock and wood seams | Quality of textures unverified until download; attribution |
| **Aquariumplants like Microsorum and Salutuya** | SF https://sketchfab.com/3d-models/aquariumplants-like-microsorum-and-salutuya-4986172e532d4e73bc3941a69f77a123 | CC-BY 4.0, Nullifiedit | 569k | Java fern (*Microsorum*) already mounted on wood: an ideal epiphyte transition piece | Extract leaf clusters, decimate ~3k each | Heavy; attribution |
| **Weeping Fern, *Lepisorus thunbergianus*** | SF https://sketchfab.com/3d-models/cc0-weeping-fern-lepisorus-thunbergianus-251d6492a669403f998908a16e4dcf45 | **CC0**, ffish.asia / floraZia | 176k | Epiphytic lance-leaf fern, very close to narrow Java fern | Epiphyte clusters on wood, ~2k tris each | Few leaves per specimen; build clusters from several |
| **Tongue Fern, *Pyrrosia lingua*** | SF https://sketchfab.com/3d-models/cc0-tongue-fern-pyrrosia-lingua-b052ebcaef59407cbfba0226c5d6dec9 | **CC0**, ffish.asia / floraZia | 597k | Leathery elliptic leaves on a creeping rhizome; reads Anubias/Buce-like at desktop distance | CC0 alternative for the broad-leaf role | Paler leaf underside; grade |
| Ribbon Fern, *Neocheiropteris ensata* | SF https://sketchfab.com/3d-models/cc0-ribbon-fern-neocheiropteris-ensata-f1c7fd5dd1be4708a1fca41c03303f14 | CC0, ffish.asia / floraZia | 991k | Broad lance leaves | Larger Java fern stand-in | Very heavy; few leaves |
| *Rejected* | SF Plants Anubias (Pala_002, 6.5k, hand-modelled), Tiger lotus low poly (stylised), Pond Weed (Valery.Li, stylised) | – | – | Not better than what we have | – | – |

### Rosette plants (Cryptocoryne type)

**Gap.** No CC0 or CC-BY Cryptocoryne scan was found (searched: cryptocoryne, crypt, aquarium plant).

- **Best available:** the Staurogyne and Vallisneria pieces inside Nullifiedit's "Aquariumplants (Java Fern, Vallisneria etc)" (CC-BY 4.0, 131k, https://sketchfab.com/3d-models/aquariumplants-java-fern-vallisneria-etc-f34fac656a364f8eaeab0918179d6df6).
- **Alternative:** small-scale *Pyrrosia* rosettes (CC0).
- **Recommendation:** drop the crypt role rather than fake it; the composition does not depend on it.

### Ribbon plants (Vallisneria type)

| Candidate | Source / URL | License, author | Fit | Treatment | Risks |
|---|---|---|---|---|---|
| **Vallisneria (in "Aquariumplants (Java Fern, Vallisneria etc)")** | SF link above | CC-BY 4.0, Nullifiedit | A real aquarium ribbon plant | Extract 2–3 clumps; opaque ribbons (~1.5k each) with vertex sway | Unknown leaf count/texture; attribution |
| Maximowicz's Sedge, *Carex maximowiczii* | SF https://sketchfab.com/3d-models/cc0-maximowiczs-sedge-carex-maximowiczii-5737d74736ab440cb5b87f1c23ff96ff | CC0, ffish.asia / floraZia | Real narrow-leaf monocot; ribbon-like once the flower spikes are removed | Leaves only, bent by the sway shader | Stiffer and more terrestrial than Vallisneria; fallback only |
| *Rejected* | SF Triangular Club-rush (CC0) | – | Reed with flower heads; reads terrestrial | – | – |

### Stem / background plants

| Candidate | Source / URL | License, author | Fit | Treatment | Risks |
|---|---|---|---|---|---|
| **Brazilian Waterweed, *Egeria densa*** | SF https://sketchfab.com/3d-models/cc0-brazilian-waterweed-egeria-densa-27a8b0cd2d1d4619a5929975389568c2 | **CC0**, ffish.asia / floraZia | A genuine aquarium stem plant (whorled leaves) | Offline: compose 6–10 clump arrangements at several heights from the scan and render cards from the camera angle (replaces our generator's cards). Near stems: decimated opaque stems (~800 tris) | 734k source; a single species, so vary it by tint, density and height to avoid a new hedge |
| Egeria/Elodea in "Aquariumplants" sets | SF (Nullifiedit) | CC-BY 4.0 | Second stem character | Same | Attribution |

### Carpet

**No convincing CC0 or CC-BY Monte-Carlo/hairgrass scan exists.** Recommended instead:

| Candidate | Source / URL | License, author | Fit | Treatment | Risks |
|---|---|---|---|---|---|
| **Fern Moss, *Thuidium* sp.** | SF https://sketchfab.com/3d-models/cc0-fern-moss-thuidium-spspp-20a5b262b32440a78925649223b49da3 | **CC0**, ffish.asia / floraZia | A dense, finely feathered mat. Reads as a carpet or moss lawn, which aquascapes genuinely use | Bake to colour, normal and height; apply to low relief shell patches (~1.5k tris each) and to the floor under them | 2.4M source faces (bake only, never ship) |
| Staurogyne clumps (Nullifiedit set) | SF link above | CC-BY 4.0 | Low aquarium foreground plant | Scattered opaque clumps at carpet edges | Attribution |
| ACG **Moss002 / Moss003** | https://ambientcg.com/view?id=Moss002, https://ambientcg.com/view?id=Moss003 | CC0 (ambientCG) | Moss surface texture | Tiling detail layer for carpet and moss shells | Too uniform alone |

### Moss / epiphytes

| Candidate | Source / URL | License, author | Fit | Treatment | Risks |
|---|---|---|---|---|---|
| **Beautiful Branch Moss, *Callicladium haldanianum*** | SF https://sketchfab.com/3d-models/cc0-beautiful-branch-moss-c-haldanianum-c5e1e73fce7d4caf803ecd8abd0797e1 | **CC0**, ffish.asia / floraZia | A dense, irregular cushion with a soft edge (the opposite of spiky) | Bake onto 4–6 cushion shell variants (~600–1,500 tris), placed on wood joints and rock/wood seams | 1.3M source (bake only) |
| **Fern Moss, *Thuidium*** | see Carpet | **CC0** | Mat moss for rock tops | Shared bake with the carpet | – |
| *Rejected* | PH moss_01 (sprigs); SF Common Liverwort (CC0, umbrella gametophores read terrestrial) | – | – | – | – |

### Substrate

| Candidate | Source / URL | License, author | Fit | Treatment | Risks |
|---|---|---|---|---|---|
| **Ground048** | https://ambientcg.com/view?id=Ground048 | CC0 (ambientCG) | Dark organic soil with fine debris, the closest to planted "aquasoil" | Base layer under planting and hardscape | – |
| **gravel_stones** | PH https://polyhaven.com/a/gravel_stones | CC0, Amal Kumar | Dark, fine, mixed gravel | Main open-floor layer | Up to 16K source; grain scale must be checked (aquarium grain ≈ 2–3 mm) |
| **sand_02** | PH https://polyhaven.com/a/sand_02 | CC0, Charlotte Baglioni | Fine pale sand | Clearing, blended at low contrast | Beach look if too bright |
| ACG Gravel024 / Gravel023 | https://ambientcg.com/view?id=Gravel024 (dark), https://ambientcg.com/view?id=Gravel023 (light) | CC0 | Alternatives for gravel and clearing | – | – |

### Small detail

Kept deliberately minimal:
- a few `rock_moss_set_02` pebbles (have, KEEP);
- the moss shells at the seams, which double as the "grown" transition.

Rejected:
- leaf litter and bark debris (PH `bark_debris_01`, forest-floor textures): terrestrial;
- shells (SF "Shells & Stones", CC0): marine.

### Sources considered and rejected as a whole

- **Quaternius, Kenney, Poly Pizza:** stylised low-poly, the wrong visual language.
- **Quixel Megascans via Fab (Fab Standard License):** raw asset files would ship extractable inside the app, which needs legal review. **NEEDS CLARIFICATION**, not pursued.
- **BlenderKit "Royalty Free":** redistribution terms for shipped raw files are unclear. **NEEDS CLARIFICATION**, not pursued.
- **Sketchfab NC/ND licenses:** incompatible. Examples: "Driftwood Scan" by milkislegit, "Terrarium/Aquarium Synthetic Rock", photorobot's aquarium stones.

## 5. Top picks and final vocabulary (11 source assets)

| Role | Pick | License |
|---|---|---|
| ROCK FAMILY A (primaries) | PH **rock_09** + PH **rock_07** (+ PH **boulder_01** as the single hero stone) | CC0 |
| ROCK FAMILY B (secondary, pebbles) | PH **rock_moss_set_02** (already in repo) | CC0 |
| ROOT A (hero sweep) | SF **Decorative driftwood** (yelizegi) *or* SF **Rathtrevor Beached Tree Root** (Lesterm), decided by a Stage 1 side-by-side | CC-BY 4.0 |
| ROOT B (secondary / back-left) | SF **Real Aquarium Wood 3D scan** (zdenkoroman) | CC-BY 4.0 |
| BROAD LEAF A | SF **Aquariumplants like Anubia Barteri** (Nullifiedit); CC0 fallback: *Pyrrosia lingua* | CC-BY 4.0 (fallback CC0) |
| EPIPHYTE / JAVA-FERN B | SF **Weeping Fern, *Lepisorus thunbergianus*** (ffishAsia) | CC0 |
| RIBBON C | SF **Aquariumplants (Java Fern, Vallisneria etc)**, Vallisneria + Staurogyne parts (Nullifiedit); CC0 fallback: *Carex maximowiczii* | CC-BY 4.0 (fallback CC0) |
| STEM D | SF **Brazilian Waterweed, *Egeria densa*** (ffishAsia) | CC0 |
| MOSS A | SF **Beautiful Branch Moss** (cushions) + SF **Fern Moss *Thuidium*** (mats/carpet) | CC0 |
| SUBSTRATE A/B | ACG **Ground048** (planted soil) + PH **gravel_stones** (open floor) + PH **sand_02** (clearing) | CC0 |

**All-CC0 variant:** if attribution licenses are declined, the vocabulary still works:
- rocks: PH;
- roots: **no CC0 root reaches the bar**, so keep the procedural gestures and replace only their surface with baked high-detail bark from a CC0 texture such as PH `bark_willow`;
- broad leaf: *Pyrrosia*;
- epiphyte: *Lepisorus*;
- ribbon: *Carex*;
- stems: *Egeria*;
- moss: the two ffish mosses;
- substrate: ACG and PH.

The expected result is clearly better than today but weaker on wood and ribbons.

## 6. Performance estimate

These are orders of magnitude, not measurements.

| Group | Treatment | Triangles | Draw calls |
|---|---|---|---|
| Rocks (2–3 primaries, 8 secondary, pebbles) | merged, 2K atlas | 18–25k | 1 |
| Roots (hero + secondary) | merged, 2K atlas | 12–18k | 1 |
| Broad-leaf + epiphyte clusters (12–18 instances) | instanced opaque | 30–45k | 1–2 |
| Ribbons (4–6 clumps) | merged opaque, sway | 6–10k | 1 |
| Near stems + background stem cards | opaque stems + ~50 cards | 8–15k | 1–2 |
| Moss cushions + carpet shells | merged, alpha only at rims | 15–25k | 1 |
| Substrate | as today | ~8k | 1 |
| **Environment** | | **~100–145k** | **8–10** |
| Fish (unchanged) | | ~48k | 3 |
| Backdrop, particles | | – | 2 |
| **Total** | | **~150–195k** | **13–15** |

- **Triangles:** likely above the 150k guideline once the fish are included. The pixel/overdraw profile should be lower than Slice B, because foliage moves from alpha cards to opaque clusters. Two levers keep the total near 150k:
  - cap the environment at about 100k;
  - later, a camera-distance LOD for the fish body (not preemptively).
- **Texture memory:** about 6–8 atlases (rocks 2K, roots 2K, plants 2K, moss 1–2K, substrate 2K, cards 2K, normals) come to roughly 90–130 MiB RGBA+mips. At or over the 96 MiB Slice budget, so most normal maps should be 1K and roughness packed.
- **FPS:** Slice B holds 60 FPS on Intel UHD at about 69% attributed GPU. Opaque clusters should not raise pixel cost much. The risk is vertex cost from ~200k triangles with the sway shader, which must be measured in Stage 2.

## 7. License and provenance table

| Asset | Source | License | Attribution required | Status |
|---|---|---|---|---|
| rock_09, rock_07 (Jenelle van Heerden) | polyhaven.com | CC0 1.0 | no | GREEN |
| boulder_01 (Rico Cilliers) | polyhaven.com | CC0 1.0 | no | GREEN |
| rock_moss_set_02 (Kless Gyzen), already in repo | polyhaven.com | CC0 1.0 | no | GREEN |
| gravel_stones (Amal Kumar), sand_02 (Charlotte Baglioni) | polyhaven.com | CC0 1.0 | no | GREEN |
| Ground048, Moss002/003, Gravel023/024 | ambientcg.com | CC0 1.0 | no | GREEN |
| *Egeria densa*, *Lepisorus thunbergianus*, *Pyrrosia lingua*, *Carex maximowiczii*, Branch Moss, Fern Moss (ffish.asia / floraZia) | sketchfab.com (CC0 in model license field and in the author's description) | CC0 1.0 | no | GREEN |
| Decorative driftwood (yelizegi) | sketchfab.com | CC BY 4.0 | **yes** | REVIEW: needs your approval plus a credits/NOTICE entry |
| Rathtrevor Beached Tree Root (Lesterm) | sketchfab.com | CC BY 4.0 | **yes** | REVIEW |
| Real Aquarium Wood 3D scan (grafi / zdenkoroman) | sketchfab.com | CC BY 4.0 | **yes** | REVIEW |
| Aquariumplants like Anubia Barteri; Aquariumplants (Java Fern, Vallisneria etc) (Nullified / Nullifiedit) | sketchfab.com | CC BY 4.0 | **yes** | REVIEW |
| Megascans (Fab), BlenderKit | – | proprietary | – | NEEDS CLARIFICATION: not recommended |
| Any CC-BY-NC / ND model | – | incompatible | – | REJECT |

**CC BY 4.0 in a desktop app:** commercial use, modification and redistribution of adapted material are allowed if the creator, the license and "modified" are credited "in any reasonable manner based on the medium".

The practical implication: a `THIRD_PARTY_NOTICES` / credits file shipped with the app, plus the manifest provenance fields. That is a product decision for you, and the asset policy requires per-asset approval.

## 8. Implementation plan (not started)

**Natural Environment Pass.** Each stage is a separate branch and commit with before/after frames from the same runtime camera, and is revertible on its own.

0. **Approval and acquisition.** You approve the list, especially whether CC-BY is allowed. Then `fetch_sources.py` gets entries with source URL, license, author and SHA-256, exactly like the Poly Haven acquisitions, and the licenses are archived in `art/licenses/`.
1. **Stage 1: rocks + wood.**
   - Replace the procedural root with ROOT A and ROOT B, posed to the approved three gestures.
   - Replace the primaries with ROCK A, keeping `rock_moss_set_02` for secondaries.
   - Cut hidden back faces, bake normals, albedo and contact AO, and grade to waterlogged dark wood and charcoal stone.
   - Measure: triangles, FPS, and a visual side-by-side with Slice B.
2. **Stage 2: major plant masses.**
   - Build cluster variants from the Anubias, *Lepisorus* and Vallisneria sources.
   - Render new background stem cards from the *Egeria* scan.
   - Re-place masses on the existing composition layout (`slice_b_layout.py` data stays the placement truth).
   - This is the main vertex-cost check.
3. **Stage 3: substrate transitions + moss.**
   - New dark soil, gravel and sand bake.
   - Moss cushion and mat shells baked from the ffish moss scans at the seams, plus a carpet shell patch.
   - Remove the old carpet relief cards.
4. **Stage 4: lighting integration.** Re-tune the key light, haze and grade for the new albedos. Real materials are darker and more varied, so expect the key and exposure to change.

**Tooling:** the same pattern as Slice B. Blender scripts turn the sources into decimated, camera-baked runtime meshes and 1–2K textures, then the manifest and budget tests. There are no runtime architecture changes beyond material assignment in a `slice-c-environment.js` (or a Slice B revision).

## 9. Biggest uncertainty and next experiment

**Biggest uncertainty:** whether the Sketchfab scans' textures (unknown until downloaded) and the heavy ffish scans hold up after decimation to runtime budgets at the desktop camera. Thumbnails cannot show texture resolution, UV quality or scan holes.

**Next experiment:** a **Stage 1 look-dev spike**, offline and not in the runtime.
- Download 5 sources: rock_09, rock_07, boulder_01 (CC0), plus **Decorative driftwood** and **Rathtrevor Beached Tree Root** (CC-BY, only if you approve CC-BY).
- Decimate and bake them in Blender.
- Place them into the approved Pass 2 composition.
- Render one frame from the runtime camera beside the current Slice B hardscape.

This decides ROOT A and whether scans give the material presence we are missing, before any plant work. A parallel CC0-only mini-spike could test *Egeria* cards and a Branch Moss cushion.
