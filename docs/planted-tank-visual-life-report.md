# Aquarium.exe frame-pacing closure and Planted Tank visual-life report

Date: 2026-09-22

Test machine: Windows 11 Pro 25H2, build 26200.9457, 1920×1080, Intel UHD Graphics 32.0.101.7085, WebView2 Runtime 153.0.4234.48

## 1. Pre-flight state

Work began from clean `audit/habitat-performance` at `634db31216380c1373e5bc6ea11e07a19375c1eb`. Remote `main`, Habitat Foundation, and audit refs matched `33fc492`, `1a3a1ab`, and `634db31`. `feasibility-v1^{}` resolved to `db13c6b`. The native `src/` tree was unchanged from `main`.

## 2. Integration strategy

`audit/habitat-performance` was already a linear descendant of Habitat Foundation, so no merge was needed. Branch `codex/planted-tank-visual-life` was created directly from `634db31`, preserving the product runtime and disabled-by-default audit tooling/evidence.

## 3. Exact frame-pacing root cause

`FrameClock.tick()` compared `currentNowMs - lastRenderMs` against the exact nominal interval and reset `lastRenderMs` to the current callback. Normal 16.6/16.7 ms rAF jitter therefore rejected about one third of nominal 60 FPS callbacks and quantized output to a 16.7/33.3 ms mix. The same defect turned requested 30 FPS into approximately 22 FPS.

## 4. Exact frame-pacing fix

The clock now carries a render-time accumulator and uses half of the current callback quantum as a nearest-callback window. Accepted renders subtract one nominal interval instead of resetting cadence to the jittered callback. The accumulator is capped so a long stall does not trigger a burst. Fixed-step simulation, rAF ownership, pause/resume, diagnostics, and FPS-zero idle behavior were not redesigned.

## 5. Before/after 60 FPS

- Before: 40.42 derived FPS, 1,219 rendered frames from 1,793 callbacks, 574 skips in the historical 15-second audit.
- After: steady Windows reports were 60.0 FPS with zero gate skips at target 60; the closure run measured 12.42% normalized CPU and 62.05% mean attributed GPU while actually rendering every display callback.

## 6. Before/after 30 FPS

- Before: 22.08 derived FPS.
- After: 30.0 FPS. Approximately every second 60 Hz callback is intentionally skipped; rendered intervals center at 33.3 ms rather than the former 33/50 ms mixture.

Raw closure measurements are in `docs/evidence/frame-pacing-closure/`.

## 7. Pause behavior

The bounded closure sample measured 0% CPU and 0.088% mean attributed GPU (0–0.442% sampling noise). In the final real desktop run, two screen captures 1.2 seconds apart had 0 changed samples across 16,625 sampled habitat pixels. Resume returned to 60.0 FPS. No render/simulation scheduler redesign was made.

## 8. Fish visual architecture

Simulation state remains authoritative. Each fish now carries deterministic archetype, role, visual phase, and weak roam-anchor data. `deriveFishVisualState()` is a pure one-way projection that calculates silhouette dimensions, orientation, banking, pitch, tail angle, fin angle, and palette without mutating simulation state. Five shared `InstancedMesh` parts render bodies, accent bands, tails, two eyes per fish, and three fin suggestions per fish.

## 9. Archetypes and personalities

- `copper`: deeper warm-bodied silhouette with a larger fan tail;
- `silver`: longer, slimmer silhouette;
- `shadow`: shorter/deeper olive silhouette.

Roles are schooling, curious, cautious, and one intentionally more cursor-interested follower. Size, speed, visual phase, tail cadence, response, and palette variation are deterministic but non-identical. A weak per-fish roam anchor prevents the long-running school from collapsing into a single rotating clump while preserving schooling forces.

## 10. Environment changes

The Planted Tank now has a darker blue-green animated depth gradient, restrained caustic suggestion and vignette, contoured substrate, asymmetric instanced rocks and driftwood, low foreground leaves, medium plant masses, taller edge stems, restrained particles, fog, and top/fill/rim lighting. The middle and upper-right regions retain quiet negative space for desktop readability.

## 11. Performance before/after

The pre-visual 60 FPS closure sample measured 12.42% normalized CPU, 62.05% mean attributed GPU, and about 540 MiB working set. The final 10-second visual guardrail sample measured 17.37% CPU, 49.21% mean attributed GPU (47.51–51.47%), 551.2 MiB working set, and 356.1 MiB private bytes at 60.0 FPS. These short samples were captured under different foreground/coverage conditions and are not benchmark-equivalent. They show higher CPU and no catastrophic FPS/GPU regression; production power optimization remains later work.

## 12. Draw calls and triangles

The scene increased from 9 calls / 4,024 triangles to 13 calls / 7,418 triangles. Fish remain five population-independent instanced draw parts; the environment uses eight draw parts. No fullscreen post-processing, shadow map, downloaded model, or large transparent overlay was added.

## 13. Windows host regression result

Actually tested on the stated Windows machine:

- the habitat visibly rendered beneath real Explorer icons;
- `WindowFromPoint` at both icon and blank-desktop coordinates returned Explorer `SysListView32` PID 6736 after recovery;
- a real icon click visibly selected the Git Bash desktop icon;
- blank-space input was delivered to Explorer rather than Aquarium;
- Aquarium never became the interactive desktop surface;
- cursor movement increased fish reactions (13 → 18 before recovery and later 121 total);
- pause/resume passed the zero-difference and 60 FPS checks;
- Show Desktop exposed the habitat and normal icons;
- Explorer restarted from PID 7356 to 6736 and Aquarium recovered in-process at WebView generation 8;
- post-recovery rendering, pointer updates, and desktop composition resumed;
- `--quit` removed all eight tracked Aquarium/WebView2 processes.

The unchanged native host continues to rely on the undocumented raised `Progman > SHELLDLL_DefView > Aquarium > WorkerW` topology and the previously documented WebView2 composition-parent split.

## 14. Browser preview

The same habitat implementation loaded from the optional Python loopback server with no package install or runtime dependency. It rendered at 60.0 FPS in the steady preview and retained pointer, diagnostics, and Space pause/resume behavior. Both the square in-app preview and 1920×1080 wallpaper composition rendered without viewport clipping.

## 15. Visual evidence

- `docs/evidence/planted-tank-visual-life/browser-preview.png`
- `docs/evidence/planted-tank-visual-life/desktop-final.png`
- `docs/evidence/planted-tank-visual-life/desktop-after-explorer-restart.png`
- `docs/evidence/planted-tank-visual-life/fish-close-view.png` (an unmodified crop of the real browser capture)
- `docs/evidence/planted-tank-visual-life/performance.json`

The desktop images contain machine-specific icons and were intentionally retained as private engineering evidence.

## 16. Tests and build

`build.ps1 -Target All` passed with 42 Node tests, native fish-logic tests, native host-policy tests, the WebView2 runtime probe, and the x64 `/W4 /WX` host build. Tests cover cadence at 60/30/20, pause/resume, deterministic archetypes/roles, pure visual projection, long-run school coverage, personal spacing, environment layout, configuration validation, and the existing behavior/runtime contracts.

## 17. Files changed

Frame closure changed `habitat/core/engine.js` and `tests/habitat/engine.test.mjs` and added three raw evidence files. The visual pass changed `habitat/core/behavior.js`, `environment.js`, `fish.js`, `habitat.js`, Planted Tank `config.js`, `water-background.js`, and the behavior/render-contract tests; it added the evidence listed above. No file under `src/` changed.

## 18. Commits

- `4923bc0` — `fix: correct habitat frame pacing`
- `58f8113` — `feat: bring planted tank habitat to life`

This report is a separate documentation commit. No merge, tag, release, force-push, history rewrite, visibility change, or public publication occurred.

## 19. Branch state

Feature implementation completed on `codex/planted-tank-visual-life` at `58f81138db56dde89519f6fd2e4f3df5369c0bc5` before this report commit. The final documentation SHA is reported in the task handoff.

## 20. Known limitations

- The procedural fish and foliage are deliberately stylized, not biologically exact or final production art.
- Archetype palette differences are subtle under the dark aquarium lighting; silhouette/size differences read more strongly than hue.
- The weak roam anchors prevent one long-running clump but can produce temporary sub-schools, which is acceptable for this pass and should be art-directed later.
- Short CPU/GPU samples vary with desktop coverage and are guardrails, not power benchmarks.
- WebView2 background network activity still requires the separately recorded pre-MVP offline/privacy audit.
- Power/session policy, multi-monitor behavior, adaptive quality, settings, installer, and product packaging remain out of scope.

## 21. Recommendation

**READY FOR VISUAL REVIEW**

The pacing defect is closed on the tested 60 Hz Windows environment, the same browser/WebView2 habitat is visibly alive beneath real icons, and the visual pass remains within the frozen native-host boundary. Continue product art review and later power/privacy work; do not treat this as release-ready artwork or a cross-machine wallpaper-host guarantee.
