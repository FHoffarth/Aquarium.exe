# Aquarium.exe — Claude Handoff — 2026-09-22

## Executive State

**OBSERVED:** Aquarium.exe has a working Windows 11 wallpaper host, a shared browser/WebView2 Three.js habitat runtime, deterministic fish simulation, corrected frame pacing, and an intermediate Planted Tank visual-life pass. On the tested machine, the habitat rendered beneath real Explorer desktop icons while Explorer retained desktop input. Pause/resume, global-cursor reaction, Show Desktop, and Explorer-restart recovery were exercised successfully.

**Current delivery state:** `READY FOR VISUAL REVIEW`, not production-ready artwork and not a cross-machine host guarantee. Feature development is intentionally stopped at this checkpoint. The next agent should continue only after reviewing this handoff with Flo.

**Test machine:** Windows 11 Pro 25H2, build `26200.9457`, 1920×1080, 60 Hz, Intel UHD Graphics driver `32.0.101.7085`, WebView2 Runtime `153.0.4234.48`.

## Git State

State frozen before the handoff/report documentation commit:

- current branch: `codex/planted-tank-visual-life`
- implementation HEAD: `58f81138db56dde89519f6fd2e4f3df5369c0bc5` (`feat: bring planted tank habitat to life`)
- frame-pacing fix: `4923bc0` (`fix: correct habitat frame pacing`)
- audit baseline: `634db31216380c1373e5bc6ea11e07a19375c1eb`
- Habitat Foundation: `1a3a1ab51bbd324cf395cde459c8b9241addb056`
- `main`: `33fc492966ba24de267e3489583d1ba61bb31ee9`
- `feasibility-v1` logical target: `db13c6b8cd0c5ab13f32eb9d625f7ac937969946`
- remote: `origin = https://github.com/FHoffarth/Aquarium.exe.git`
- history from `main` through the current branch is linear
- `src/` is unchanged by the frame-pacing and visual-life work

Before this file was added, the only untracked file was `docs/planted-tank-visual-life-report.md`; it is intentional work and is included with this handoff. The final handoff commit SHA and remote verification are reported outside this document after the push.

No merge, tag, release, force-push, history rewrite, remote visibility change, or public publication is authorized by this handoff.

## Proven Architecture

**VERIFIED on the test machine:**

- native Windows host attaches to Explorer's raised desktop topology;
- WebView2 supplies the GPU-backed HTML/Three.js habitat surface;
- the same habitat implementation runs in WebView2 at `https://aquarium.local/` and in the optional static browser preview;
- normal desktop icon and blank-desktop input remains owned by Explorer;
- Aquarium receives global cursor coordinates out of band and does not become the interactive desktop surface;
- the native host recovered its habitat after an Explorer restart.

The observed desktop relationship is:

```text
Progman
├─ SHELLDLL_DefView / SysListView32 (Explorer icons and desktop input)
├─ Aquarium host/composition surface
└─ WorkerW
```

This relies on undocumented Explorer/WorkerW/Progman behavior. It is proven on Windows build `26200.9457`, not guaranteed by a documented Windows wallpaper-host contract. The native WebView2 composition-parent split and recovery behavior are documented in the feasibility and Sprint 1 reports.

## Work Completed Today

Two focused changes were completed:

1. Frame pacing was corrected without redesigning the engine. The exact-threshold timestamp gate was replaced with a bounded accumulator and nearest-callback acceptance window. Fixed-step simulation, rAF ownership, pause/resume, and diagnostics contracts remain intact.
2. The Planted Tank received an intermediate procedural visual-life pass: deterministic fish roles/archetypes, articulated instanced fish parts, weak roam anchors, a richer shader background, contoured substrate, plants, rocks, driftwood, particles, fog, and restrained lighting.

Commits before this handoff documentation:

- `4923bc0` — `fix: correct habitat frame pacing`
- `58f8113` — `feat: bring planted tank habitat to life`

Evidence is retained under `docs/evidence/frame-pacing-closure/` and `docs/evidence/planted-tank-visual-life/`. Desktop images contain machine-specific icons and diagnostics and are intentionally retained as historical engineering evidence in the private repository.

## Frame Pacing Status

**Root cause — VERIFIED:** `FrameClock.tick()` required `currentNowMs - lastRenderMs >= nominalInterval` and then reset cadence to the jittered callback timestamp. A realistic 16.6/16.7 ms rAF sequence therefore skipped about one third of callbacks at a nominal 60 FPS and produced mixed ~16.7/~33.3 ms render intervals. The same error reduced a requested 30 FPS to about 22 FPS.

**Fix — VERIFIED:** `habitat/core/engine.js` now accumulates callback time, caps accumulated debt, accepts the nearest feasible callback using half the current callback quantum, subtracts one nominal interval after rendering, and still renders the first frame immediately.

**Regression coverage — VERIFIED:** a deterministic 120-callback 16.6/16.7 ms sequence produces exactly 120, 60, and 40 renders for 60, 30, and 20 FPS targets. Pause/resume coverage remains present.

**Windows closure — OBSERVED on this 60 Hz machine:**

- 60 FPS target: steady `60.0 FPS`; steady snapshots showed zero explicit-gate skips;
- 30 FPS target: steady `30.0 FPS`; approximately every other 60 Hz callback was intentionally skipped;
- paused: `0 FPS`, 0% sampled CPU, and 0.088% mean attributed GPU sampling noise;
- real desktop pixel comparison while paused: 0 changed samples across 16,625 sampled habitat pixels over 1.2 seconds; resume returned to `60.0 FPS`.

**Status:** closed for the tested 60 Hz environment. Do not reopen or redesign frame pacing unless it reproduces on another refresh configuration or a new regression test fails. Different refresh rates are algorithmically covered but **NOT YET TESTED** on physical displays.

## Planted Tank Current State

The scene retains 10 simulated fish. Each fish has deterministic role, archetype, visual phase, and a weak roam anchor. Roles are schooling, curious, cautious, and one more cursor-interested follower. Archetypes are:

- `copper`: deeper warm body and larger fan tail;
- `silver`: longer, slimmer silhouette;
- `shadow`: shorter/deeper olive silhouette.

`deriveFishVisualState()` is a pure projection that derives orientation, pitch, bank, tail/fin articulation, dimensions, and palette from simulation state and time. Five shared instanced fish parts render body, accent, tail, eyes, and fins. Environment rendering uses an animated water/depth shader, contoured substrate, three instanced plant layers, instanced rocks/driftwood, particles, fog, and ambient/top/rim lighting.

**OBSERVED:** the scene renders correctly in both optional browser preview and production WebView2 mapping. It rendered beneath real desktop icons after Show Desktop and after Explorer restart. Cursor reaction counts increased during real movement.

## Current Visual Limitations

This is an intermediate procedural art pass, not final art:

- fish still read too dark/metallic under current lighting;
- palette distinctions are subtler than silhouette distinctions;
- schooling can still form temporary sub-groups despite passing long-run spread checks;
- procedural plants, rocks, and driftwood remain visibly placeholder-like rather than naturally authored;
- fish silhouettes and articulation are stylized, not biologically exact;
- water/lighting integration and desktop readability need further art direction across more wallpapers, displays, and icon layouts;
- no external art assets, model pipeline, or post-processing system was introduced.

The next visual iteration should improve those specific shortcomings without changing the simulation/rendering ownership boundary or frozen native host.

## Performance Knowledge

**Historical pre-fix audit:** 60 FPS requested produced 40.42 derived FPS, with 1,219 renders from 1,793 callbacks and 574 explicit-gate skips. Fish simulation and projection were approximately 0.28 ms and 0.29 ms respectively, so 10-fish behavior was not the dominant cost.

**Frame-closure sample:** 60.0 FPS, 12.42% normalized CPU, 62.05% mean attributed GPU, about 540 MiB working set.

**Final visual guardrail sample:** 60.0 FPS, 17.37% normalized CPU, 49.21% mean attributed GPU (47.51–51.47%), 551.2 MiB working set, 356.1 MiB private bytes.

The two samples were taken under different foreground/coverage conditions and are **not benchmark-equivalent**. They establish a guardrail, not a production power profile. The final scene increased from 9 draw calls / 4,024 triangles to 13 draw calls / 7,418 triangles and retained steady 60 FPS on the test machine.

**INFERRED:** most current GPU cost is rendering/composition/pixel related rather than 10-fish behavior. **NOT YET TESTED comprehensively:** production battery behavior, adaptive quality, occlusion policy, multi-monitor cost, and broad hardware coverage.

## Privacy / Network Follow-Up

**OBSERVED during the bounded audit:** a WebView2 process showed background TCP activity. It was reproduced once and attributed to the WebView2 process tree, but the remote service and exact trigger were deliberately not investigated during the performance/visual sprint.

Required separate pre-MVP finding:

`WebView2 background network activity / offline privacy audit required before MVP`

Do not claim a zero-network product until that audit identifies and, if needed, disables or controls background WebView2 networking. The habitat assets and Three.js runtime themselves remain bundled locally, and no Aquarium account, analytics, telemetry, or cloud feature was added.

## Architecture Invariants

**SIMULATION STATE IS AUTHORITATIVE. RENDERING IS A ONE-WAY PROJECTION OF SIMULATION STATE.**

Three.js objects and instance transforms must never become the source of truth for fish position, velocity, personality, archetype, or behavior. Behavior code must not read rendered mesh transforms. Future fish geometry, materials, or animation presentation must remain replaceable without rewriting simulation behavior.

Additional frozen invariants:

- deterministic simulation remains independent of Three.js;
- diagnostics are observational only and must not alter simulation behavior or timing semantics beyond unavoidable measurement overhead;
- browser preview and WebView2 execute the same habitat implementation;
- Python is only an optional development static server, never a product dependency;
- Three.js and habitat assets remain local; no CDN dependency;
- desktop input remains with Explorer; Aquarium is not an ordinary interactive desktop surface;
- native host changes require explicit approval because feasibility behavior is already proven.

## Tests / Build Status

**VERIFIED after the final implementation changes:** `build.ps1 -Target All` passed:

- 42 Node tests;
- native fish-logic tests;
- native host-policy tests;
- WebView2 runtime probe (`153.0.4234.48`);
- x64 native host build at `/W4 /WX`.

Tests cover cadence at 60/30/20, pause/resume, deterministic roles/archetypes, pure non-mutating visual projection, long-run school coverage, spacing, environment/configuration contracts, and existing lifecycle behavior.

Windows integration observations include real desktop rendering, Explorer-owned hit testing, icon selection, blank-space delivery to Explorer, cursor reaction, pause/resume, Show Desktop, Explorer restart/recovery, and clean process shutdown. Native CUA was unavailable, so the final native interaction checks used the same narrowly scoped Win32 `CopyFromScreen`, `WindowFromPoint`, and click fallback used in prior feasibility work. Do not represent that limitation as automated end-to-end UI coverage.

## Known Risks

- WorkerW/Progman desktop attachment is undocumented and may vary across Windows/Explorer builds.
- WebView2 background network behavior requires a dedicated offline/privacy audit.
- only one primary 1920×1080 60 Hz Intel iGPU setup is evidenced by the latest run;
- multi-monitor, DPI combinations, HDR, variable refresh, battery policy, display-off/lock, and broad GPU coverage remain untested;
- short CPU/GPU samples are noisy and coverage-sensitive;
- Explorer blank-space ownership was proven by hit testing, but the helper's selection-index result was inconsistent, so do not overclaim that the latest blank click visibly cleared selection;
- visual assets are procedural placeholders and may need a deliberate art/content pipeline later;
- temporary fish sub-clumping remains possible.

## Files to Read First

Read in this order:

1. `docs/claude-handoff-2026-09-22.md`
2. `docs/planted-tank-visual-life-report.md`
3. `docs/sprint1-habitat-report.md`
4. `docs/sprint1b-performance-audit.md`
5. `habitat/habitat.js`
6. `habitat/core/engine.js`
7. `habitat/core/behavior.js`
8. `habitat/core/fish.js`
9. `habitat/core/environment.js`
10. `habitat/habitats/planted-tank/config.js`, `habitat/core/scene.js`, and `habitat/shaders/water-background.js`
11. `tests/habitat/`

Then inspect the real evidence under `docs/evidence/frame-pacing-closure/` and `docs/evidence/planted-tank-visual-life/`. Do not infer success from code alone when an observed result is available.

## Exact Next Steps

Claude's exact first action should be:

> Check out and pull `codex/planted-tank-visual-life`, confirm the remote HEAD matches the handoff commit reported by Codex, then read this handoff and `docs/planted-tank-visual-life-report.md` before changing any file.

After that, and only with Flo's direction:

1. run `./build.ps1 -Target All` to reproduce the frozen baseline;
2. do not revisit frame pacing unless another display refresh reproduces a defect;
3. if continuing the visual pass, change one visual variable at a time: reduce dark/metallic fish response, strengthen deterministic archetype color/silhouette readability, reduce transient clumping without breaking behavior tests, and make plants/hardscape more organic;
4. preserve approximately 13 draw calls / 7,418 triangles and steady 60 FPS as current guardrails rather than launching a broad optimization audit;
5. capture honest browser and real Windows desktop evidence for Flo; do not create mock evidence;
6. schedule the separate WebView2 offline/privacy audit before any MVP claim;
7. request explicit authorization before merging or crossing the native-host boundary.

## Things Not To Do

- Do not refactor or redesign the native `src/` host without explicit approval.
- Do not replace WebView2, Three.js, DirectComposition, or the proven desktop-attachment approach during the visual pass.
- Do not make rendered Three.js transforms authoritative.
- Do not add Koi, feeding, habitats, settings, installer, auto-update, telemetry, accounts, analytics, cloud services, branding polish, or product framework work.
- Do not add CDN-hosted code/assets, external runtime dependencies, Python packages, a package manager, or a new development framework.
- Do not resume the exhaustive performance matrix or begin an optimization campaign.
- Do not claim cross-build reliability, zero networking, final art, or production power behavior from the current evidence.
- Do not hide attachment failure behind a normal always-on-bottom window.

## Git / Delivery Rules

- Work from `codex/planted-tank-visual-life` unless Flo explicitly requests a new isolated branch.
- Keep commits scoped and preserve the existing linear history.
- Do not merge to `main` without explicit authorization.
- Do not create or move tags, create releases, publish binaries, configure CI/CD, rewrite history, squash existing commits, or force-push.
- Do not change repository visibility or publish private engineering evidence elsewhere.
- Preserve the machine-specific screenshots and diagnostic HWND/PID evidence already approved for the private repository.
- Before handing back work, run the relevant tests, `git diff --check`, verify the intended remote ref, and leave a clean working tree.
