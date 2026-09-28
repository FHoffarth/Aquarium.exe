# Bright freshwater material and lighting recovery (`?art=lush-live`)

Continues from the true-water pass (`947ee50`). Geometry, placement, camera, fish geometry/behaviour/scale/mapping, the water-path model and the extinction coefficients are unchanged. No effects, post-processing or assets were added.

## Material audit: why `947ee50` looked grey-green

I compared three things:
- the approved Blender source (`lush-water-reference.blend`, material node graphs and lights dumped to `art/work/lush-live/material-audit-source.txt`);
- the glTF export;
- the runtime.

| Family | Source intent | glTF / runtime | Root cause |
|---|---|---|---|
| All materials | Principled BSDF mixed 50/50 with a blue-green **emission** (0.055, 0.19, 0.23) on camera rays, fading with view distance; noise-driven colour ramps and bump | Flat base colour only | The source's own "water glow" and procedural variation were lost. The glow is now represented by the water model's in-scattering. |
| Lighting | **~3.6 kW of large area lights**: wide overhead lamp 1900 W, leaf transmission light 1000 W *behind* the plants, front-glass fill 800 W, right overhead 900 W; world ambient (0.22, 0.31, 0.38) | One spot, a hemisphere and one weak directional | The pale sand and bright leaves depended on these lights. At runtime, the same dark source albedos (gravel 0.08–0.24, leaves 0.02–0.27 linear) render grey and dark. This was the main cause. |
| Output | Blender **AgX**, look *Medium High Contrast*, exposure −0.2 | three.js ACES Filmic, exposure 1.4 | ACES desaturates and greys the mid-tones, which is exactly where sand and leaves sit. |
| Photographed broad leaves | Atlas with an **HSV node: saturation 1.25, value 2.0** | Atlas only | The export dropped the ×2 brightening, so broad leaves were half their intended value. |
| Foliage | Double-sided, subsurface 0.035, a dedicated back light | Mostly double-sided, no transmission | Back faces of ribbon and broad leaves receive only the hemisphere, so they go near-black. |
| Wood / stones | Texture × noise; warm under warm-white lamps | Texture only | Fine, but read cold and grey under the old light. |
| Rear | Emission blue ramp (0.015, 0.055, 0.08) → (0.18, 0.55, 0.72) | Unlit dark blue-green gradient | Correctly real geometry, but far too dark and grey after the water model. |

## Changes, in stages (each captured headless at the approved camera)

The code is `habitat/core/lush-live-look.js` (new) plus small wiring in `lush-live.js` and `scene.js`.

**A: Material recovery** (`3-material-recovery.png`). Materials are cloned per plant family: the shared glTF leaf materials become one instance per family. The mesh–material pairs are the same, so draw calls don't change.
- **Plant-family tints** (linear multipliers on the source colour):
  - front plants ×(1.35, 1.45, 0.9), fresh green;
  - small-leaf bushes ×(1.2, 1.3, 1.0), mature;
  - feather plants ×(1.9, 1.6, 0.8), light yellow-green new growth;
  - ribbons ×(1.45, 1.5, 1.0);
  - tall grass ×(1.7, 1.35, 0.75), olive;
  - medium stems ×(1.25, 1.25, 0.95);
  - supporting stems ×(1.1, 1.1, 0.9).
  - The rust and golden-olive accent stems are kept as sourced.
- **Broad leaves:** the source's HSV value 2.0 is restored as a colour factor (1.75, 2.0, 1.55).
- **Two-sided foliage:** a thin-leaf transmission term adds light passing through a leaf from the key lamp to the far side. It is weighted 0.2–0.55 per family and replaces the offline light behind the plants. Foliage is double-sided with roughness ≥ 0.55.
- **Sand:** gravel colours ×(2.7, 2.75, 2.75), roughness 0.92. This gives a pale warm-neutral that keeps the five gravel tones' variation.
- **Wood:** ×(1.45, 1.12, 0.82), warm brown, roughness 0.85.
- **Stones:** ×(1.2, 1.18, 1.12), roughness 0.9.

**B: Lighting and output transform** (`4-lighting-recovery.png`). Positions come from the offline layout.
- **Key:** a wide overhead aquarium lamp above the tank centre, a SpotLight at (−0.8, 9.2, 0.6), 330 cd, inverse-square falloff toward the rear. White (0xfbfbf6) in the final stage.
- **Fill:** front-glass fill, directional 0.85, cool white.
- **Hemisphere:** sky 0xc9dde0 over ground 0x7a7560, 0.95, after the source world colour.
- **Tone mapping:** Khronos PBR Neutral. Three.js AgX has no *Medium High Contrast* look and rendered flat and grey; ACES greyed the mid-tones. Neutral keeps hue, which matters for green leaves, pale sand and red fish. Exposure is 1.5 in the final stage.
- **Tried and rejected:** separate rear and right overhead directional lights (see Performance).

**C: Rear boundary** (`5-rear-recovery.png`). It stays real geometry with an unlit material inside the water model.
- A smooth three-stop height gradient, recomputed per fragment: `#24535e` → `#468896` → `#8ccbe0` in the final stage, lighter in the lamp-lit upper water and deeper toward the floor.
- A ±3% very low-frequency analytic brightness drift so it does not read as a flat card. No texture.

**D: Final balance** (`6b-final-headless-same-camera.png`, real desktop `6-final-full-frame.png`).
- Exposure 1.15 → 1.5.
- Sand factor slightly cooler and paler.
- The rear top lifted toward clear blue.
- **One bounded water change: the in-scatter colour `[0.058, 0.112, 0.118]` → `[0.08, 0.215, 0.31]` (linear).**
  - **Reason:** after the material and lighting fixes, the water column's own light was still dark grey-teal. It made the water read murky and pulled the rear plants toward grey. The source's water emission colour is (0.055, 0.19, 0.23) at strength 0.8, so the new value moves toward that intent.
- **Extinction coefficients are unchanged:** R 0.13, G 0.08, B 0.058, reference distance 3.5, glass z +5. A test protects them.

## Fish

Unchanged: the palette (`freshwater-approved`), geometry, scale, mapping, behaviour and the water treatment on the fish.

At desktop size the red belly bands and fins read on front and mid fish. They are dimmer than the offline reference's glowing red fish. The fish use their own physical metal and clearcoat material and the environment map, which this pass did not touch.

## Performance (real host, 1920×1080, Intel UHD, Lively closed)

| | `947ee50` | Final |
|---|---|---|
| FPS, target 60, 8 × 5 s after warm-up | 59.5–59.8 | **59.45 / 59.70** |
| Frame time mean (max window) | 16.7–16.8 ms | **16.75–16.82 ms (17.06)** |
| Draw calls / triangles | 82 / 392,471 | **82 / 392,471** |
| GPU (Aquarium processes) | 70–76% | **71–76%** |
| Target 30 | 30.0 | **30.0**, 55.8% GPU |
| Pause / resume | 0% / 60 | **0.00%**, no metrics while paused; resume 60.0 |
| Texture memory | 38.7 MiB | unchanged (no new textures) |

**Measured and fixed along the way:**
- **The regression:** the first lighting version had three directional lights plus the spot. It dropped the host to **49.7–50.7 FPS (20 ms)**.
- **The cause:** each light adds a full BRDF evaluation to every overlapping alpha-tested foliage fragment.
- **The fix:** folding the rear and right lamps into the hemisphere and the leaf-transmission term restored 59.5–59.7 FPS with no visible difference (compare `fw-D4` and `fw-D5` in `art/work`). A test now keeps the scene at one directional light.

## Tests and build

- **JS:** 93/93 pass (`node --test tests/habitat/*.test.mjs`). New `tests/habitat/lush-live-look.test.mjs` covers:
  - per-family material cloning without touching the source;
  - pale sand factor, two-sided foliage with alpha test, depth write, transmission and family differentiation;
  - the rear material: real geometry, lighter above and bluer than grey, bounded variation, no texture;
  - the lighting configuration: key above the tank, at most one directional light, no shadows, neutral tone mapping and bounded exposure;
  - the water constants.
- **Updated:** the water test now inspects the per-family materials.
- **Native:** `/W4 /WX` build, fish-logic and host-policy tests, and the WebView2 probe all pass.
- **`git diff --check`:** clean.

## Evidence (`docs/evidence/lush-live-freshwater/`)

- **Requested set:**
  - `1-reference-6dfd62d.png`;
  - `2-before-947ee50.png` (real desktop);
  - `3-material-recovery.png`, `4-lighting-recovery.png`, `5-rear-recovery.png` (headless stage frames);
  - `6-final-full-frame.png` (real desktop);
  - `7-three-way-reference-before-after.jpg`;
  - `8-foreground-crop.png`, `9-midground-crop.png`, `10-background-crop.png` (real desktop final);
  - `real-desktop-final-45s.mp4`: the clean first 45 s of a 50 s recording. A notification and then a window appeared after about 47 s, so that part was cut.
- **Extras:**
  - `stages-A-B-C-D.jpg` (all stages side by side, same camera);
  - `before-after-depth-crops.jpg`;
  - `6b-final-headless-same-camera.png`.

The stage frames are headless Edge (same engine, same camera, no desktop icons). Before and final are real-desktop captures.

## Assessment

**Clearly better than `947ee50` at normal desktop size, without labels. Depth is intact.**
- **Better:**
  - The dominant grey-green cast is gone.
  - The sand is pale natural aquarium sand instead of concrete.
  - Plant masses separate: fresh front greens, light yellow-green feather plants, olive grass, darker mature bushes.
  - Ribbon and broad leaves are no longer near-black silhouettes.
  - The wood reads warm brown against the sand.
  - The upper water reads as blue-teal water rather than murky haze.
  - The rear plants still recede into the water, and the rear wall does not read as a flat card.
- **Still short of `6dfd62d`:**
  - The water is a muted teal, not the reference's luminous clear blue. The reference's glow came from Cycles area lights plus a per-material emission that the runtime only approximates.
  - The foliage has no procedural colour or bump variation within a plant, so masses look smoother and more uniform than offline.
  - The fish are the weakest element. The red accents read, but less vividly than the reference, and small fish at the back are grey silhouettes.
  - Leaf backs are plausible now, but some broad-leaf interiors are still dark.
  - Sand in the far corners of the front glass is slightly flat (a single key lamp, no area-light softness).
- **Not fixed here, on purpose:** fish material brightness is protected in this pass. Per-plant variation would need a material or texture pass.
