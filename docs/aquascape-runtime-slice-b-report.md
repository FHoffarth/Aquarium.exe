# Aquascape Runtime Translation: Slice B

Branch `claude/aquascape-runtime-slice-b`, base `67d8814` (Hero Fish 1B, which contains Slice A `c15957e`). Not merged.

The approved Aquascape Hero Frame Pass 2 (`9c2db27`) was used only as the frozen visual reference: its report and evidence were read from that branch, and nothing was merged or cherry-picked. The offline composition script was consulted for composition data and ported, not imported.

## Result

The Windows wallpaper now defaults to **Slice B**, a real-time translation of composition B, with the **real 10-fish school rendered by Hero Fish 1B at scale 0.75**.

- `?art=slice-a` and `?art=procedural` remain for comparison.
- Any Slice B asset failure falls back to the procedural habitat with the classic fish, reporting `habitat-asset-failure:` as before.
- The five defining characteristics survive: the left hardscape anchor, three connected root gestures, composed plant masses, calm deep-teal open water on the right, and a warm focal light on the hardscape.

## How Hero Fish 1B was translated

- `createHeroFishRenderer` (unchanged from Pass 1B) now renders the whole school in Slice B: `capacity = fishCount` (10), scale `SCHOOL_HERO_SCALE = 0.75`.
- It is still 2 instanced meshes (body + eyes, fins), 3 draw calls in total.
- Per-fish swim state comes from `createSwimAnimator`, which reads simulation state and never writes it. The simulation, `behavior.js` and frame pacing are untouched.
- The upright orientation (no left-swimmer roll) and the C-bend, pectoral and caudal motion come for free.
- The fish geometry was not simplified. Measured at 10 fish it is not the bottleneck: 60 FPS at target 60 on the host.
- The hero review mode (`?heroFish=1`) is unchanged.

## How the Pass 2 aquascape was translated

The goal was to preserve perception, not polygons: 0.9–1.1 M offline triangles became **52.9k**.

- **Pipeline:** new `art/tools/slice_b_layout.py` (shared composition data and terrain functions), `build_slice_b.py` (Blender) and `prepare_textures_slice_b.py` (NumPy), plus Slice B entries in `build_manifest.py` and `build_all.py`.
- **Hardscape:**
  - 13 rocks from the approved CC0 set in the Pass 2 hierarchy: 2 primaries, 2 front secondaries, and transition and secondary stones, decimated to 450–2400 triangles, partly buried, plus 12 pebbles.
  - The original procedural driftwood root keeps its three gestures, surface roots and stubs, with bark UVs along the grain.
  - It sits 0.3 units further back than offline, so it stays behind the fish swim volume (the simulation has no obstacle avoidance).
  - Moss sprigs are concentrated at joints and low surfaces.
  - Contact shading is baked into vertex colour.
- **Plants:** the hardscape planting, rock and wood epiphytes, small rosettes, hairgrass clusters and six ribbon clumps are **solid vertex-coloured leaf geometry** (16k triangles, no alpha, no overdraw).
- **Background:** the 11 stem masses are 59 camera-facing **cards**, each rendered from the fixed habitat camera angle in Blender from the Pass 2 stem generator (four plant characters, two variants each).
- **Carpet:** baked into a unique substrate texture (coverage mask, broken sand clearing, contact darkening, fade into water), with 36 low relief cards.
  - The substrate texture uses a non-linear depth mapping (front rows get about 70% of the texels).
  - The floor continues to z −6 and dissolves into depth haze matched to the backdrop, so there is no back-glass line.
- **Light, economically** (no shadow maps, no post-processing):
  - one warm `SpotLight` from the upper left keys the hardscape;
  - cooler, weaker top, fill and ambient light elsewhere;
  - a new backdrop shader (`waterBackgroundSliceBFragmentShader`) adds a deep-teal gradient, a faint warm glow and restrained shafts at the upper left, and darker, calmer water to the upper right.
  - Existing caustics and depth haze are reused.
- **MSAA:** off for Slice B. It is now enabled only for the procedural baseline, because alpha-tested cards and MSAA were the measured Slice A cost.

## Measurements

| | Slice A (compare) | **Slice B** |
|---|---|---|
| Draw calls | 13 | **11** |
| Rendered triangles | 69,582 | **100,824** (environment 52.9k + fish ~48k) |
| Host FPS, target 60 | 60.0 | **59.1 / 60.0 / 60.0 / 60.0** (four runs) |
| Host FPS, target 30 | – | **30 / 30 / 24.9** (the 24.9 window had ~500 pointer events and a cursor reaction) |
| Host GPU, WebView2 + host PIDs, all engines | 61.5% (1 run) | **65.4–79.1%**, median ≈ 69% (5 runs) |
| Pause | – | **0.00% GPU**, no metrics while paused; probe answers `paused=true`; resume returns to 60 FPS |
| Asset load / bytes | 716 ms / 5.85 MB | 620–836 ms / 5.54 MB |

- **Environment:** 53k of the per-group 90k budget, 6 of 8 primitives.
- **Budgets:** no budget was raised. The budget test is now scoped per art group; Slice B is held to Slice A's numbers.
- **GPU method:** the real host at 1920×1080 on Intel UHD, with the browser pane closed. The GPU figure is the sum of all GPU-engine utilisation for the Aquarium/WebView2 PIDs over five 1 s samples. It is not comparable to the audit's 45% figure, which used a different sampler.

## Tests and build

- **JS:** `node --test tests/habitat/*.test.mjs`: 67/67 pass. New or updated tests:
  - art-mode default is `slice-b`;
  - a Slice B failure falls back to procedural with classic fish;
  - per-group asset budgets;
  - original-art provenance.
- **Native** (patched `build.ps1` copy for the VS 2026 DevShell issue): `/W4 /WX` build of `AquariumSpike.exe`, fish-logic tests PASS, host-policy tests PASS, WebView2 SDK probe PASS (Runtime 153.0.4234.48).
- **`git diff --check`:** clean. **`src/`:** unchanged.
- **Behaviour:**
  - normal motion and cursor reaction (host: reactions 18 → 33 while the cursor moved);
  - pause/resume (host `--pause` / `--resume`, plus browser Space);
  - probe;
  - diagnostics toggle (browser `D`: hidden → shown → hidden).

**Provenance change:** the manifest now allows `origin: "original"` for Aquarium.exe's own procedural art (the Slice B card atlas), with no third-party sources but a required, existing in-repo generator. Everything derived still names its GREEN CC0 sources.

## Evidence (`docs/evidence/aquascape-runtime-slice-b/`)

Frames were captured in headless Microsoft Edge (Chromium, same engine as WebView2, D3D11 ANGLE) at 1920×1080 with real-time waits. The in-app preview pane pauses rendering when hidden.

| | File |
|---|---|
| A: full runtime aquarium | `a-runtime-full-1920x1080.png` (and `-t2` a few seconds later) |
| A vs approved target | `comparison-pass2-vs-runtime.jpg` (Pass 2 top, runtime bottom) |
| B: hardscape close view | `b-hardscape-close.png` |
| C: open water + fish | `c-open-water-fish.png` |
| D: diagnostics | `d-diagnostics.png` |
| E: real Windows desktop screenshot | **not captured.** It would require minimizing the user's open windows. The real host was measured, but not photographed. |

## Known visual compromises

- **Background stem masses** are cards: lighter and more uniform than offline, reading slightly as a reed band in the centre.
- **The carpet is mostly a baked floor texture**, flatter than the offline 3D cushion. Relief cards were reduced to 36, because at 70 they read as floating strips.
- **The floor takes more visual weight** than in the offline frame: a darker, larger open area centre-right.
- **Solid leaf geometry is flat-shaded and polygonal** up close (broad leaves, fern tufts); moss tufts read spiky.
- **The warm key is a single unshadowed spot**, so it lights plants behind the rocks too.
- **The fish sometimes overlap the hero branch in screen space** when they swim in front of it. The wood is behind the swim volume, so there is no intersection.

## Known performance compromises

- **About 10–15 points more host GPU than Slice A** at the same 60 FPS. Likely contributors, not yet profiled:
  - 10 physical-material fish with clearcoat and iridescence (each fish reflects its own environment map);
  - double-sided plant geometry;
  - the additional spot light.
- **Triangles are about 45% higher than Slice A** (fish ~48k).

Both are inside the guardrails (≤150k triangles, ≤20 draw calls). No optimisation was attempted, per the brief.

## Recommendation

**READY FOR WINDOWS VISUAL REVIEW**
