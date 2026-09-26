# Natural Environment Runtime: Slice C

Branch `claude/natural-env-runtime-slice-c`, created from `claude/aquascape-runtime-slice-b` (`099cc72`: Hero Fish 1B + Slice B runtime). Not merged.

The Windows wallpaper now defaults to **Slice C**: the locked Natural Environment vocabulary with the unchanged Hero Fish 1B school. `?art=slice-b`, `?art=slice-a` and `?art=procedural` remain. Any Slice C asset failure falls back to the procedural habitat with classic fish, as before.

## Vocabulary (locked)

- **Scanned Poly Haven rock family:**
  - `rock_07` (rear-left primary), `boulder_01` (centre-left primary) and 2× `rock_09` (front secondaries);
  - welded and decimated to 3.6k / 5.2k / 1.9k+1.9k triangles, from 27.8k / 124k / 23.3k source faces;
  - `rock_moss_set_02` secondaries, transition stones and ~20 partly buried fragments.
- **Composition B root:** Slice B's procedural port, unchanged gestures, still 0.3 units behind the fish volume, with `bark_willow_02` graded to the approved waterlogged brown and the fibre-aligned cracks baked in.
- **`LeafSet022` broad-leaf clusters:** 425 photographed leaves, each cut along its own outline into a tight 8-row strip, in camera-specific clusters at the rock/root/substrate seams only.
- **Not present:** no moss, no background plant wall, no carpet, no sand path. Open dark water is intentional negative space.

## `rock_07` flecks: fixed

- **Cause:** the source roughness map is a uniform ~0.30, which glinted as white flecks.
- **Fix:** Slice C ships no roughness maps for stone. All stone uses one matte roughness (0.86), and isolated bright albedo specks are clamped to the 99.5th luminance percentile.
- **Tone:** `rock_07` carries its own tone in glTF `COLOR_0`, which multiplies base colour. It is now kept under the contact shading, which restores the approved dark reddish stone.

## P0: floor and horizon

- **Terrain:** the substrate now rises only into low soil shoulders at the rock bases, then **falls away behind the hardscape**. The crest's depth varies with x (noise), so the drop is never a straight line (`slice_c_layout.substrate_height`, `crest_z`).
- **Baked floor colour:** it converges to water *before* the crest (`depth_fade`). The runtime haze colour equals the backdrop value at the projected crest (horizon 0.31). The haze range [−0.35, −2.7] completes the dissolve, so the floor sinks into dark water instead of ending in a lit line.
- **Camera:** a subtle upward tilt (`lookAt(0, 0.24, 0)`, about 2°) reduces the visible floor share. The offline candidate's floor was ~40% of the frame; on the real desktop the floor is now ~22% (plus taskbar). The whole fish volume stays in view.
- **Soil zone:** an irregular, noise-edged dark soil/gravel zone surrounds the hardscape. Finer sand stays only as breathing room in front of the hardscape. The floor's tonal hierarchy is baked: key-lit left-centre, darker right and front edge.
- **Burying:** rocks sit deeper than offline, soil shoulders rise around their bases, and fragments are 45–65% buried.
- **Micro-gravel:** baked into the substrate texture. No runtime gravel pieces.

## Light and water

- Restrained warm spot on the left hardscape (80, was 95), with a cooler, weaker top, fill and ambient light.
- The backdrop's upper-right "calm" darkening rises from 0.35 to 0.5 via a new `uCalm` uniform (Slice B keeps 0.35).
- No shadow maps, no post-processing, no MSAA.

## Figures

| | Slice B | **Slice C** |
|---|---|---|
| Rendered triangles (real host) | 100,824 | **93,960** (environment 46.0k + fish ~48k) |
| Draw calls (real host) | 11 | **12** (7 environment meshes + backdrop + particles + 3 fish) |
| Environment meshes | 6 | 7 |
| GPU texture memory (RGBA8 + mips) | 64.0 MiB | **69.3 MiB** |
| Asset bytes / load | 5.54 MB / 620–836 ms | **4.54 MB / 564–602 ms** |

Environment triangles:

| Mesh | Triangles |
|---|---|
| rock_07 | 3,600 |
| boulder_01 | 5,200 |
| rock_09 ×2 | 3,800 |
| stones and fragments | 8,098 |
| root | 4,952 |
| leaves | 11,900 |
| substrate | 8,448 |

Textures:

| Texture | Resolution |
|---|---|
| `rock_07` albedo | 2K |
| `rock_07` normal, `boulder_01` albedo and normal, bark albedo, leaf atlas | 1K |
| `rock_09`, stones, bark normal, leaf normal | 512 |
| Substrate albedo | 2048×1024 |
| Substrate normal | 1024×512 |

`rock_07`'s UV islands use about half its map, which is why it needed 2K colour.

## Real-host measurements (1920×1080, Intel UHD)

- **Conditions:** Lively Wallpaper closed by the user.
- **GPU figure:** all GPU-engine utilisation for AquariumSpike and its own WebView2 processes (filtered by user-data path), averaged over 5 × 1 s.

| | Result |
|---|---|
| Target 60, after 20 s warm-up | **60.0 FPS sustained**: two runs of 10 × 5 s windows, lowest window 59.6 |
| GPU at 60 | **76.6% / 77.3%**. Slice B in the same session: 60.0 FPS at 78.9% |
| Target 30 | **30.0 FPS** (8 × 5 s windows), 57.8% GPU |
| Pause | **0.00% GPU**, no metrics while paused, probe answers `paused=true` |
| Resume | back to 60.0 FPS |
| Cursor reaction | scripted cursor sweep through the open water: fish reactions 13 → 23 |
| Diagnostics overlay | shown on the real desktop (`4-real-desktop-diagnostics*.png`) |

With Lively running (contended GPU, ~57% used by Lively), Slice C held 48–56 FPS where Slice B held 34.

## Tests and build

- **JS:** `node --test tests/habitat/*.test.mjs`: **70/70 pass**. New or changed tests:
  - default art mode is `slice-c`;
  - a Slice C failure falls back to procedural with classic fish;
  - Slice C budget: ≤ 50k environment triangles, per-mesh limits, ≤ 8 meshes, ≤ 72 MiB textures;
  - provenance across Poly Haven + ambientCG records.
- **Native** (patched `build.ps1` copy for the VS 2026 DevShell issue, as in Slice B): `/W4 /WX` build of `AquariumSpike.exe` passes, fish-logic tests PASS, host-policy tests PASS, WebView2 SDK probe PASS (Runtime 153.0.4234.48).
- **Code hygiene:** `git diff --check` clean. `src/` unchanged. Simulation, fish, frame pacing and pause code are unchanged.

## Changed files

- **Runtime:**
  - `habitat/core/slice-c-environment.js` (new);
  - `habitat/core/art-mode.js` (default `slice-c`);
  - `habitat/habitats/planted-tank/scene.js` (Slice C group, Hero Fish school for B/C, per-environment camera target);
  - `habitat/shaders/water-background.js` (`uCalm` uniform);
  - `habitat/core/slice-b-environment.js` (passes `uCalm` 0.35: unchanged look);
  - `habitat/habitat.js` (comment).
- **Assets:** `habitat/assets/slice-c/` (1 GLB + 14 WebP) and `habitat/assets/manifest.json` (41 files, 14 sources, all GREEN CC0 with SHA-256).
- **Pipeline:**
  - `art/tools/slice_c_layout.py`, `build_slice_c.py`, `prepare_textures_slice_c.py` (new);
  - `build_slice_b.py` (main guard only, so Slice C reuses its helpers; Slice B output unchanged);
  - `build_manifest.py` (multi-source provenance, ambientCG);
  - `build_all.py`;
  - `fetch_stage1_sources.py`, `fetch_stage2_sources.py`, `leaf_atlas_profiles.py` (from the offline study).
- **Provenance and licenses:**
  - `art/provenance/stage1/` (the four shipped Poly Haven sources);
  - `art/provenance/stage2/` (LeafSet022);
  - `art/licenses/ambientcg-license-page.html`;
  - `THIRD_PARTY_NOTICES.md` (Slice C credits).
- **Tests:** `tests/habitat/art-mode.test.mjs`, `asset-budget.test.mjs`, `asset-manifest.test.mjs`.

## Evidence (`docs/evidence/natural-env-runtime-slice-c/`, real Windows desktop, 1920×1080)

The desktop was shown with Win+D (approved) and captured with GDI `CopyFromScreen`. Desktop icons and the taskbar are part of the real frame.

| | File |
|---|---|
| 1. Clean desktop | `1-real-desktop-clean.png` |
| 2. Fish through the open water | `2-real-desktop-fish-open-water.png` |
| 3. Hardscape crop | `3-real-desktop-hardscape-crop.png` |
| 4. Diagnostics | `4-real-desktop-diagnostics.png`, `4-real-desktop-diagnostics-crop.png` |
| 5. Slice B vs Slice C | `5-comparison-slice-b-vs-slice-c.jpg` (+ `5-real-desktop-slice-b-reference.png`) |
| Cursor sweep frame | `6-real-desktop-cursor-sweep.png` |

## Known visual weaknesses

- **Desktop icons sit on top of the hardscape.** The left icon column covers x < ~480 px, which is where the rock/root/leaf mass lives. On a desktop with many icons, half of the natural material is behind them.
- **The frame is sparse and dark by design.** Open water is ~65% of the screen, and with few fish in view the right half can read empty rather than calm.
- **The floor right of centre is still a plain dark sand plane.** It no longer ends in a line, and it is much smaller, but it carries no detail.
- **`rock_07` is inherently smooth** (soft scan texture). It reads as a dark slab rather than a pitted stone.
- **Leaves read like cut leaves up close.** At desktop distance they form a mass at the base, mostly in the dark lower-left, often under icons and the taskbar.
- **Fish still cross the root in screen space** (no intersection: the wood is behind the swim volume).
- **The camera tilt moves the cursor-to-water mapping slightly.** The simulation maps the pointer linearly to its bounds, not through the camera, so the effective reaction point is about 0.2 units off vertically. Fish still react (measured).
- **Texture memory is 5.3 MiB above Slice B** (69.3 vs 64.0 MiB), mainly from `rock_07`'s 2K colour.

## Recommendation

**READY FOR WINDOWS VISUAL REVIEW.** Slice C is running on the real desktop now.

---

## Composition polish (bounded visual pass, 2026-09-26)

- **Verdict it answers:** Slice C *technical* PASS, *visual* not yet. The left hardscape read as a compact pile, the landscape ended at about a third of the frame, the right-of-centre sand was one smooth plane, and the fish were too dark.
- **Unchanged:** no new assets, no search, no background plants, no moss, no carpet. Architecture, performance strategy, fish geometry and scale, simulation, host, frame pacing, camera and the floor/horizon solution are unchanged.

### What changed (`slice_c_layout.py`, `build_slice_c.py`, `prepare_textures_slice_c.py`, `slice-c-environment.js`, `scene.js`)

- **Hardscape gesture:**
  - The hero root now sweeps lower and farther, reaching about x = 1.1 (≈1190 px, was ≈1065 px): a diagonal from lower left into the open water.
  - The steep rise is slightly lower, so the pair reads less like antlers.
  - The boulder stands apart from rock_07 (x −1.7 → −1.4), and two small secondaries left the root base, so the root emerges visibly between the primaries.
  - A fifth surface root runs out along the floor toward the centre.
  - A shrinking trail of four buried stones leads from the transition stone toward the centre.
- **Broad leaves (LeafSet022 only):**
  - One primary mass sits *in front of* the flat front stones, hiding their bases instead of sitting on them.
  - Fewer seams behind, with dark gaps between them.
  - Two small transition groups: one against the transition stone, one beside the head of the stone trail. The transition groups are never randomly skipped.
  - Fewer rosettes are sampled on rock flanks, and only right at the ground line.
  - 291 leaves, down from 425; the density is not increased.
- **Floor:**
  - The sand gets large, soft tonal fields, a slight warm/cool drift and faint darker sediment patches (baked; no geometry).
  - The soil zone's edge has broader tongues plus finer fraying and follows the stone trail toward the centre.
  - The crest, fade and haze (the horizon fix) are untouched.
- **Fish readability:** the diagnosis was that the fog was *not* the cause (front fish ~0%, back ~5% haze). The school was dark because Slice C had lowered the top light. The fix:
  - top light back to Slice B's 1.35;
  - a faint cool view-side fill (0.35) for the silver flanks;
  - the school gets its own haze range [0.75, −3.4], so front fish stay clear and back fish take a little teal, making depth visible.

  Hero Fish code is unchanged; the school simply receives `fishEffectUniforms` when the environment provides them.

### Figures after the polish

| | Before (Slice C) | After |
|---|---|---|
| Environment triangles | 46.0k | 42.5k |
| Rendered triangles (real host) | 93,960 | 90,432 |
| Draw calls | 12 | 12 |
| Host FPS, target 60 (Lively closed) | 60.0 | 60.0 (8 × 5 s windows) at 76.4% GPU |
| Asset bytes | 4.54 MB | 4.35 MB |

- **Tests:** JS 70/70.
- **Native:** `/W4 /WX` build, fish-logic and host-policy tests, and the WebView2 probe pass.
- **Not re-run for this pass:** 30 FPS, pause and cursor checks. This visual-only pass changed no timing, pause or input code.

### Evidence (`docs/evidence/natural-env-runtime-slice-c-polish/`, real Windows desktop, 1920×1080)

- `1-real-desktop-clean.png`
- `2-real-desktop-fish-open-water.png`
- `3-real-desktop-hardscape-crop.png`
- `4-real-desktop-diagnostics.png` and its crop
- **BEFORE/AFTER** against yesterday's real-desktop Slice C frame:
  - `5-before-after-real-desktop.jpg`
  - `5-before-after-hardscape-crop.jpg`

### Still open

- The boulder is now the dominant front mass and reads somewhat blocky.
- The stone trail and the second transition group are small at desktop distance.
- The right-of-centre floor is quieter but remains a simple dark plane.
- Desktop icons still cover the left third (accepted).

**READY FOR WINDOWS VISUAL REVIEW.**
