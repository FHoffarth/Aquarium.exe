# Hero Fish Visual Pass 1B: proportion and desktop readability

Branch `claude/hero-fish`, following Pass 1 (`2241c18`). Not merged.
Recommendation: **READY FOR VISUAL REVIEW**.

This pass corrects the fish's art direction only. The architecture, simulation, environment, lighting, camera, material system and production renderer are unchanged.

## Proportion changes (`habitat/core/hero-fish.js`)

| | Pass 1 | Pass 1B | Change |
|---|---|---|---|
| Greatest body depth | 0.300 SL at s≈0.40 | 0.200 SL at s≈0.37 | −33% |
| Greatest half-width | 0.056 | 0.042 | −25% |
| Head depth at the eye (s=0.10) | ≈0.17 | ≈0.11 | −35% (head volume ≈ −30%) |
| Depth at s=0.23 (head/trunk transition) | 0.26 (86% of peak) | 0.17 (85% of a much slimmer peak), smoother rise | smoother forehead, no bulbous head |
| Belly | ventral fullness 2.1–2.35 (rounded) | ventral 1.95–2.0, and the ventral half-depth is now smaller than the dorsal | shallow, flat belly line |
| Peduncle depth (s=0.90) | 0.088 | 0.066 (0.33 of peak) | kept thin; the taper from s 0.52 to 0.90 is longer and more gradual |
| Snout | blunt, bulbous | finer, slightly longer taper; mouth lift 0.011 → 0.008 | |
| Eye radius | 0.034 | 0.027 | −21%; also sits lower (lift 0.024 → 0.017) and slightly forward |
| Gill-cover position / lip | s 0.238, lip 2.2% | s 0.215, lip 1.2% | follows the smaller head; softer seam |
| Caudal | lobes to s 1.33, spread ±0.17, notch at s 1.165 | lobes to s 1.355, spread ±0.155, notch at s 1.14; caudal membrane alpha ×1.3 | deeper, more elegant fork; slightly stronger silhouette; still translucent |
| Dorsal height | 0.148 | 0.122 | proportional to the slimmer body |
| Anal depth | 0.10 | 0.072 | thin |
| Pelvic / pectoral length | 0.10 / 0.13 | 0.075 / 0.10 | restrained |
| Swim amplitude | 0.09 + 0.2·speed + 0.16·escape | 0.08 + 0.17·speed + 0.14·escape | about −15%, so the slim body does not go eel-like |
| Default `heroScale` | 1.8 | 1.0 | review now defaults to true desktop size |

Two further tunings:
- The head's darker "nape" tint was reduced from 0.5 to 0.3, so the smaller head no longer reads as a helmet.
- The gill-cover tint was reduced from 0.2 to 0.12.

No colour redesign. The adipose fin was kept; it is small and only reads at close range.

A second variant (deeper-bodied rasbora) was not needed. The slender tetra profile with a slightly raised dorsal arc (tops +6–8% over s 0.23–0.52) was clearly the better of the two intermediate states tried.

## Desktop scale

The acceptance frames (F, G) use `heroScale=0.75`. The fish is then about 125 px long at 1920×1080, a size at which 10–15 fish could share the tank.

`heroScale=1` (the production school's current size) is about 165 px long. Choosing the final school size is left for the school pass.

## Evidence (`docs/evidence/hero-fish-1b/`)

| | File |
|---|---|
| A: Pass 1 side profile (same camera, light, scale) | `a-pass1-side-profile.png` |
| B: Pass 1B side profile | `b-pass1b-side-profile.png` |
| A/B sheet | `comparison-pass1-vs-pass1b.jpg` |
| C: diagnostic close-up | `c-pass1b-close-up-diagnostic.png` |
| D: 3/4 view | `d-pass1b-three-quarter.png` |
| E: turning C-bend | `e-pass1b-turn-c-bend-toward.png`, `e-pass1b-turn-c-bend-quarter.png` |
| **F: full 1920×1080 frame, realistic size, open water** | `f-pass1b-desktop-full-open-water.jpg` (crop for inspection: `f-pass1b-desktop-crop.png`) |
| **G: full 1920×1080 frame, fish crossing the planted corner** | `g-pass1b-desktop-full-vegetation.jpg` (crop: `g-pass1b-desktop-crop.png`) |
| Pass 1 at the same F/G positions and scale | `pass1-desktop-full-open-water.jpg`, `pass1-desktop-full-vegetation.jpg`, `pass1-desktop-crop.png` |
| Motion (3/4 so the lateral wave is visible) | `m-cruise-front-1/2.png`, `m-escape-front-1/2.png`, `m-hover.png` |

The Pass 1 comparison frames were rendered from an untouched export of `2241c18` served in parallel, so conditions are identical.

## Performance

- **Triangles:** unchanged, because the grid resolution is unchanged. 3,712 body+eyes plus 542 fins, with 4,796 rendered (the fins draw in two passes).
- **Vertices:** 2,362.
- **Draw calls:** 3.
- **Real host FPS** (1920×1080, pane closed):

| Variant | FPS |
|---|---|
| Hero ×0.75 | 58.7 |
| Baseline, 10 production fish | 58.5 |

## Tests

`node --test tests/habitat/*.test.mjs`: 63/63 pass.

The Pass 1 anatomy test asserted a deep body (> 0.28 SL). It now asserts the Pass 1B intent:
- depth between 0.17 and 0.23;
- the peak over the forward trunk;
- a small head;
- a ventral half-depth smaller than the dorsal;
- a thin peduncle.

All other tests are unchanged and still cover:
- NaN-free, valid geometry;
- the shader injection hooks;
- the simulation left untouched;
- the production contract;
- the review flags;
- upright orientation.

## Remaining visual weaknesses

- **Head-on, mid-turn, the fish still reads a little pale and rounded** (`e-pass1b-turn-c-bend-toward.png`), less than in Pass 1.
- **At close-up the scale net and the head/gill-cover shading are visible.** At desktop scale they disappear.
- **Pure side views hide most of the lateral body wave.** This is physically correct; the 3/4 motion frames show it.
- **The production renderer's left-swimmer upside-down bug is unchanged** (out of scope). The hero keeps the upright orientation.
