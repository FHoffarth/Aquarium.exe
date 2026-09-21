# Sprint 1B — Habitat Performance Audit

## 1. Decision summary

The persistent ~40 FPS result is explained. Aquarium receives callbacks at essentially 60 Hz, but `FrameClock.tick()` applies another exact 60 FPS threshold. Timestamp jitter causes roughly one third of callbacks to fall just below that threshold; those callbacks are rejected, and the following callback renders after roughly 33.3 ms. This produces the measured mix of ~16.7/33.3 ms render intervals and approximately 40–41 rendered FPS.

The intended 10-fish simulation is not a material bottleneck. GPU cost responds strongly to internal pixel count and render cadence, while fish-count changes have only a small effect. True pause is effective. Habitat Foundation is safe to merge for continued development, subject to explicit frame-policy and offline-privacy follow-ups before MVP.

## 2. Scope and branch

- Branch: `audit/habitat-performance`
- Start: `feature/habitat-foundation` at `1a3a1ab51bbd324cf395cde459c8b9241addb056`
- Native host boundary: frozen and unchanged
- Experiments: narrowed by instruction to six automatically terminating runs
- No visual, schooling, environment, host, or product-default change was made.

## 3. Test environment

- Windows 11 Pro 25H2, exact build **26200.9457**
- Display: 1920×1080
- GPU: Intel(R) UHD Graphics, driver `32.0.101.7085`
- Logical processors: 4
- WebView2 Runtime: `153.0.4234.48`
- Habitat content: local `https://aquarium.local/` mapping; no CDN or package runtime

Aquarium successfully reported `SESSION RUNNING` and no attachment failure in every retained run. The Codex window was foreground during measurement, so the desktop wallpaper could be partly covered; this audit does not claim a visibility/occlusion comparison. Desktop composition and interaction remain established by the preceding feasibility and Habitat Foundation runs.

## 4. Measurement methodology

The sampler waits for `SESSION RUNNING`, warms WebView2 for three seconds, recursively discovers current Aquarium descendants, classifies their command lines, and creates persistent Windows `GPU Engine` counters only for exact descendant PID tokens. Counter discovery happens outside the timed interval. The timed interval takes CPU snapshots at both boundaries, reads the already-open per-PID GPU counters approximately once per second, and records two per-process memory snapshots.

CPU is normalized across four logical processors. GPU values are sums of the matching process's engine counters. This method attributes Aquarium/WebView2 engines, but intentionally excludes DWM/compositor cost and may sum simultaneous engines. Chromium shared pages make working-set totals non-additive in a strict ownership sense.

Every retained run reports `CONCLUSIVE`, stayed within 0.06 seconds of its requested timed duration, contained repeated GPU samples, and terminated Aquarium automatically.

## 5. Sampler repair and validation

The repaired sampler:

- renamed the profile flow so it cannot collide with PowerShell's automatic `$PROFILE` variable;
- takes explicit CPU boundary snapshots;
- separates slow GPU counter discovery from the timed window;
- reads persistent counters repeatedly instead of treating one wildcard query as an average;
- retains PID, role, command line, CPU, working set, private bytes, and per-PID GPU values;
- gives each control invocation a five-second timeout and marks insufficient sampling `INCONCLUSIVE`.

The first short validator correctly marked itself `INCONCLUSIVE` because it had one GPU point. Its one allowed retry also marked itself `INCONCLUSIVE` because slow wildcard discovery overran and discovered children too early. Those data were not used. The replacement persistent-counter path was validated by the first 15.019-second normal run before the remaining comparisons; it produced 14 repeated GPU samples and passed every validity check.

## 6. Frame pacing result

The approximately 15-second steady window contained three consecutive five-second reports:

| Metric | Result |
|---|---:|
| rAF callbacks | 901 |
| Rendered frames | 613 |
| Gate-rejected callbacks | 288 (32.0%) |
| Derived rendered FPS | 40.76 |
| Callback interval mean / median / p95 | 16.666 / 16.7 / 16.8 ms |
| Callback interval min / max | 15.9 / 17.5 ms |
| Render interval mean / median / p95 | 24.535 / 16.8 / 33.4 ms |
| Render interval min / max | 16.7 / 33.7 ms |

Callback histogram (rounded to 1 ms): **16 ms: 52, 17 ms: 845, 18 ms: 1**.

Rendered-frame histogram: **17 ms: 321, 18 ms: 1, 32 ms: 1, 33 ms: 283, 34 ms: 4**.

This directly confirms quantization: rAF is stable near 60 Hz, while actual rendering alternates between one- and two-vsync-sized intervals.

## 7. Exact responsible code path

`FrameClock.tick()` in `habitat/core/engine.js` calculates `renderInterval = 1000 / targetFps`, then accepts a render only when:

```text
currentNowMs - lastRenderMs + 1e-9 >= renderInterval
```

At target 60, nominal rAF deltas frequently arrive slightly below 16.6667 ms. A rejected callback leaves `lastRenderMs` unchanged, so the next callback is accepted near 33.3 ms. When accepted, the code resets `lastRenderMs` to the current timestamp rather than maintaining an ideal cadence. This explicit second gate—not fish work, WebGL duration, display refresh, or WebView2 throttling—creates the ~40 FPS plateau.

No fix was made. A correct timing-policy change deserves a separate test and before/after visual validation rather than being folded into this audit.

## 8. Normal 10-fish process cost

The 15.019-second normal sample measured:

- whole-tree normalized CPU: **8.32%**;
- PID-filtered GPU: **45.06% mean**, **40.04% min**, **48.34% max**, 14 samples;
- last whole-tree working set: **533.1 MiB**;
- last private bytes: **339.3 MiB**.

CPU time was attributed approximately to the WebView2 GPU process (**4.99% normalized**) and renderer process (**3.33%**); native host, browser, utility, crashpad, and console processes were below the sampler's interval resolution in this run. All nonzero GPU Engine values belonged to the WebView2 GPU-process PID. DWM cost is not included.

## 9. Normal process-tree memory

Mean per-process observations during the normal run:

| Role | Working set | Private bytes |
|---|---:|---:|
| Native host | 41.9 MiB | 40.0 MiB |
| WebView2 browser | 122.8 MiB | 38.9 MiB |
| Renderer | 79.0 MiB | 39.5 MiB |
| GPU process | 198.7 MiB | 185.1 MiB |
| Network service | 31.3 MiB | 10.2 MiB |
| Storage service | 17.9 MiB | 7.9 MiB |
| Crashpad | 14.1 MiB | 2.9 MiB |
| Console host | 9.5 MiB | 1.7 MiB |

The approximately 500 MiB footprint is predominantly Chromium/WebView2 process architecture and GPU allocations, not fish state.

## 10. Fish-count scaling

| Fish | Simulation mean | Fish projection mean | Render mean | CPU | GPU mean (range) | Derived FPS |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.013 ms | 0.041 ms | 1.835 ms | 9.94% | 43.71% (39.76–48.65) | 39.51 |
| 10 | 0.277 ms | 0.285 ms | 1.237 ms | 8.32% | 45.06% (40.04–48.34) | 40.42 |
| 50 diagnostic | 0.917 ms | 0.455 ms | 1.299 ms | 9.94% | 46.76% (33.35–52.72) | 40.49 |

Simulation scales as expected, but remains below 0.3 ms at 10 fish and below 1 ms even at the diagnostic 50-fish load. CPU did not increase monotonically, GPU ranges overlap, and FPS stayed around 40. The 10-fish behavior/projection work does not materially explain current cost.

## 11. Pixel-cost sanity check

| Internal scale | CPU | GPU mean (range) | Working set | Private bytes | Derived FPS |
|---:|---:|---:|---:|---:|---:|
| 1.0 | 8.32% | 45.06% (40.04–48.34) | 533.1 MiB | 339.3 MiB | 40.42 |
| 0.5 | 9.95% | 26.82% (25.09–29.32) | 420.9 MiB | 234.8 MiB | 39.91 |

Half scale reduced attributed GPU by **40.5%** and substantially reduced GPU-associated memory without changing the ~40 FPS plateau. This is strong evidence that GPU cost is primarily pixel/render/composition related. It also proves that reducing pixel cost cannot repair the frame gate. No resolution change was retained.

## 12. Explicit 30 FPS hypothesis

| Setting | CPU | GPU mean (range) | Render interval median / p95 | Derived FPS |
|---|---:|---:|---:|---:|
| Current target 60 | 8.32% | 45.06% (40.04–48.34) | 16.8 / 33.4 ms | 40.42 |
| Target 30 | 7.46% | 28.57% (22.75–30.82) | 49.9 / 50.0 ms | 22.08 |

The lower cadence reduced attributed GPU by **36.6%** and CPU by approximately **10%**, although CPU resolution is coarse. It did not deliver 30 FPS: the same gate interaction rejected 447 of 716 callbacks and settled around 22 FPS, dominated by ~50 ms intervals.

In the ordinary-browser preview, fish continued to move and individual frames remained visually coherent at the measured 22–23 FPS. Still screenshots cannot establish motion smoothness; subjectively verifying whether a true 30 FPS cadence is sufficient remains a small product follow-up after the gate is corrected. The product default remains unchanged.

## 13. Pause result

The bounded 5.046-second paused interval measured:

- normalized whole-tree CPU: **0.00%** at sampler resolution;
- PID-filtered GPU: **0.00% mean/min/max** across five samples;
- animation callbacks: **0**;
- rendered frames: **0**;
- simulation, projection, environment, render, and callback timing samples: **0**.

The native cursor bridge continued around 21–22 Hz, but its measured CPU remained below the sampler's resolution. Pause behavior is acceptably idle.

## 14. Network reproduction

The earlier TCP observation reproduced in every retained run. Each run showed two established TLS connections owned by the WebView2 **browser** process, with varying remote endpoints in the `40.99.x.x` or `52.97/52.98.x.x` ranges, plus two bound sockets. The habitat assets themselves remained local, and this audit did not identify or investigate the remote service.

Separate follow-up finding: **WebView2 background network activity / offline privacy audit required before MVP**.

No product networking behavior was changed.

## 15. Feasibility baseline

`feasibility-v1` was not rebuilt. Doing so would require reconstructing a different historical content/runtime build while the bounded current sampler depends on audit instrumentation added after that tag. Existing measurements remain historical and non-equivalent: approximately 38–43 FPS, ~5.5% normalized CPU in one short sample, ~504 MiB working set, and variable 26–44% attributed GPU.

The important comparable fact remains that both the primitive feasibility scene and Habitat Foundation settled near 40 FPS. The newly measured gate behavior explains why richer habitat content did not materially change that plateau.

## 16. Bottleneck diagnosis

- **FPS ceiling:** explicit JavaScript render gate interacting with 60 Hz rAF timestamps.
- **10-fish simulation:** inexpensive; ~0.28 ms simulation and ~0.29 ms projection mean.
- **Per-render JavaScript/WebGL submission:** roughly 1–2 ms, far below the 16.7 ms callback budget.
- **GPU:** dominated by the WebView2 GPU process and strongly sensitive to internal pixel count.
- **Composition:** DWM cost was not attributed, so the split between WebGL GPU work and final Windows composition remains unknown.
- **Native host/cursor bridge:** below CPU sampling resolution in the retained runs.

## 17. Optimization decision

No optimization was committed. The frame gate is a clear local defect, but changing cadence policy without a dedicated before/after timing and motion test would violate the audit boundary. No fish, renderer, resolution, native host, or default-FPS setting was changed.

## 18. Instrumentation impact and limitations

Audit instrumentation is local and disabled by default. When disabled, it performs no additional clock reads or timing-array writes. Enabled reports batch snapshots at the existing low-frequency diagnostics boundary.

Limitations:

- CPU attribution is approximate and coarse over 10–15 second windows.
- GPU counters exclude DWM and can sum parallel engines.
- The 15-second resource window sits inside a longer startup/warm-up diagnostic log; the reported pacing distribution uses three consecutive steady five-second batches.
- Foreground Codex UI could cover part of the wallpaper during runs.
- The qualitative 30 FPS judgment is limited because the current gate produced ~22 FPS and automation captured still frames rather than video.

## 19. Changes and evidence

Useful retained tooling:

- disabled-by-default runtime timing and audit profiles;
- bounded per-process CPU/memory/GPU sampler;
- generated-build-only profile switcher;
- sampler helper and timing-recorder tests.

Raw evidence is under `docs/evidence/performance/`, with `bounded-summary.json` as the compact derived index. No binaries, user data directory, generated profile, or native-host instrumentation is retained.

## 20. Recommended production performance strategy

Habitat Foundation can enter main for continued development. Follow-up work should, in order:

1. correct and separately benchmark the rAF/render-rate policy;
2. evaluate a true 30 FPS power mode after that correction;
3. retain dynamic resolution only as a future evidence-backed power option, not as the default;
4. perform the required WebView2 offline/privacy audit;
5. add cover, battery, lock, and display-off policies before MVP.

READY TO MERGE WITH FOLLOW-UP
