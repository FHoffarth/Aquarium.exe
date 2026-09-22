# North-Star Slice A — planted corner (report)

Date: 2026-09-22 · Branch: `claude/north-star-slice-a` (from accepted `2ac73d0`)

Question: can Aquarium.exe approach the North-Star feeling with a real production asset
pipeline while remaining a viable live Windows wallpaper? Fish are the accepted Pass 2
fish; the environment is the experiment. Visual Pass 3 (`2e47c45`) was neither merged
nor cherry-picked.

## What was built

- **Pipeline** (`art/`): reproducible fetch -> Blender 5.2 LTS (headless) -> textures ->
  manifest. Deterministic output. See `art/README.md`.
- **Assets**: approved GREEN CC0 Poly Haven sources only; no Sketchfab. Shipped runtime
  set is 14 files, 5.85 MB (`habitat/assets/`), each with SHA-256 + provenance in
  `manifest.json`; license evidence archived in `art/licenses/`.
- **Runtime**: vendored three.js glTF loader (unmodified, same verified 0.186.0 tarball)
  via an import map; every asset is size- and SHA-256-verified before use; any failure
  reports `habitat-asset-failure:` (info, deliberately not `habitat-failure:` which makes
  the host rebuild) and falls back to the accepted procedural habitat.
- **A/B**: default art mode is `slice-a` (the host always loads `index.html` without a
  query); `?art=procedural` shows the accepted Pass 2 environment unchanged.
- **Fin capacity fix** (isolated commit `bf18ea5`): the fin InstancedMesh held
  `maximumFish` instances while projection writes three per fish; now `maximumFish * 3`,
  with a regression test that fails on the old baseline.

## Art decisions

| Element | Solution |
|---|---|
| Hero wood | Kitbash of `dry_branches_medium_01` (plan A). Branches are twig-proportioned, so they are radially thickened (x2.3-2.9) and joined into one forked sweep rising from behind the rocks toward centre at mid-height. Plan B (own sculpt) was not needed. |
| Rocks | `rock_moss_set_02`, 6 rocks decimated to ~2.6k tris + 12 pebble copies, grouped and partially sunk. |
| Moss | 520 real CC0 moss sprigs (`moss_01`) scattered on up-facing wood/rock surfaces. |
| Broad-leaf + fern | `anthurium_botany_01` (decimated 67k -> 1.5k tris per plant) and `fern_02`, 2x1 atlas. |
| Carpet + stems | Camera-facing cards rendered in Blender from the fixed habitat camera angle (`shrub_sorrel_01` with flowers removed; `nettle_plant`, one bronze variant). |
| Substrate | One unique baked 2048x1024 texture (no tiling possible with a fixed camera): two CC0 sands blended by hardscape proximity, Cycles contact occlusion, darkening into the rear. |
| Water | Existing caustics extended onto up-facing surfaces; soft light shafts in the existing backdrop shader (upper centre-right, top-left kept calm); depth haze mixed after encoding so the floor dissolves into the backdrop. |
| Swim volume | Tall hardscape sits behind the fish volume: the simulation has no obstacle avoidance, and an early build showed a fish passing through the wood. |

## Guardrails (real Windows host, 1920x1080, Intel UHD, target 60)

| Configuration | FPS | Draw calls | Triangles |
|---|---:|---:|---:|
| Procedural A/B (MSAA on) | 57-60 | 13 | 7,610 |
| Slice A with 4x MSAA | ~31 | 13 | 69,582 |
| **Slice A as shipped (MSAA off)** | **57-59.8** | **13** | **69,582** |

- Environment geometry 63,180 triangles (rocks 17,758; plants 22,858; moss 8,722; wood 7,500; substrate 6,144; cards 198).
- Estimated GPU texture memory 80.0 MiB (RGBA8 + mips; budget 96).
- Asset load (fetch + SHA-256 + parse + decode) 0.7-1.4 s in the host; `habitat-ready` well inside the host's 30 s deadline.
- Pause -> `paused=true`; resume -> 59.8 FPS; clean `--quit`.

**Regression found and resolved:** with the accepted 4x MSAA, Slice A ran at ~31 FPS in the
real host. Targeted host measurements: no vegetation ~45, render scale 0.75 ~45, MSAA on
with alpha-to-coverage off ~34.5, **MSAA off ~59**. The cost is 4x multisampled bandwidth
multiplied by the planted corner's alpha-tested overdraw on an integrated GPU, not any one
asset. Slice A therefore renders without MSAA; at 1:1 the difference is subtle
(`msaa-on-left-off-right-1to1.png`) but edges are harder and swaying leaves can crawl
slightly. The procedural baseline keeps MSAA. Trade-off: because the WebGL context is
created before assets load, a fallback to procedural after an asset failure also runs
without MSAA.

## Validation

- `node --test tests/habitat/*.mjs`: 54/54 (43 existing + art mode, fallback, manifest integrity, asset budget, fin capacity).
- `build.ps1` equivalent: JS 54/54, native fish-logic PASS, host-policy PASS, WebView2 Runtime 153.0.4234.48 probe PASS, x64 `/W4 /WX` host build PASS. Note: the installed VS 2026 Build Tools (18.9.2) `Launch-VsDevShell.ps1` calls `exit` after entering the shell, which ends a dot-sourcing script; `build.ps1` then falls into an interactive prompt. Validation used an identical copy that enters the dev shell via the DevShell module. `build.ps1` itself was only changed to run the new test files. This toolchain incompatibility should be fixed separately.
- Failure path end-to-end: one flipped byte in `environment.glb` -> "SHA-256 mismatch" reported, procedural habitat running at its baseline numbers.
- Real host: attach OK, startup success, `art=slice-a`, assets verified and loaded over `https://aquarium.local/`.
- `src/`, `behavior.js`, `engine.js`: unchanged. Explorer-restart recovery was not re-run (host unchanged; each WebView generation re-verifies and reloads assets, ~1 s).

## Visual gate (honest)

| Question | Answer |
|---|---|
| Rocks read as real rock? | Yes. |
| Wood reads as real wood/root? | Yes; forked, mossy, strong diagonal. One branch end reads as a flat sawn stump. |
| Plants form believable masses? | Left mass yes (fern + broad-leaf + carpet); right stems plausible but a little uniform. |
| Substrate natural rather than a plane? | Yes; no tiling; front band is calm and plain. |
| Hardscape embedded? | Yes (grit, contact occlusion, planting around the bases). |
| Depth? | Moderate: foreground carpet, midground planting, hazed rear stems, shafts, dissolving horizon. No distant background planting. |
| Open water calm? | Yes, well over half the frame; top-left icon region stays dark and calm. |
| Materially closer to the North Star? | Yes, a different class from every procedural pass. Still less lush and less luminous than the reference. |

Known weaknesses: the Pass 2 fish now look toy-like against realistic materials (Slice B
is the answer); lushness and luminance are below the reference; right side is sparser
than the left; flat branch end; the whole look was tuned in this one environment
(1920x1080, one iGPU) and has not been seen on other displays.

## Evidence (`docs/evidence/north-star-slice-a/`)

- `slice-a-desktop-1920.png` — shipped configuration, full 1920x1080 frame from the drawing buffer
- `slice-a-detail-planted-corner.png`, `slice-a-detail-right-stems.png` — native-resolution crops
- `procedural-ab-desktop-1920.png` — `?art=procedural` A/B baseline, same resolution
- `slice-a-with-msaa-comparison-1920.png`, `msaa-on-left-off-right-1to1.png` — MSAA trade-off

Real Windows desktop review with icons remains the final visual gate.
