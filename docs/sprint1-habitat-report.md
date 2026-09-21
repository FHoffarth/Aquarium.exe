# Aquarium.exe Sprint 1 — Habitat Foundation validation

Date: 2026-09-21

Branch: `feature/habitat-foundation`

Frozen native baseline: `33fc492966ba24de267e3489583d1ba61bb31ee9`

Test machine: Microsoft Windows 11 Pro 25H2, build 26200.9457, x64

GPU: Intel UHD Graphics, driver 32.0.101.7085

Display under test: 1920×1080, one monitor

## Result

Sprint 1 passes its bounded habitat-foundation acceptance on the tested machine. Ten procedural fish rendered and moved beneath the real Explorer desktop icons; Explorer retained icon and blank-desktop input; native global cursor input increased fish reactions; true pause stopped visible changes and GPU use; resume restarted the same runtime; Win+D preserved the wallpaper; and Aquarium recovered in-process after one forced Explorer restart.

This is an observed result for the stated machine, not a general Windows compatibility claim. The broader recommendation remains **GO WITH CONDITIONS** because the proven WebView2 composition-parent split is not a documented stable wallpaper API, the workload missed 60 FPS, and resource use remains high for a lightweight desktop utility.

## Architecture implemented

The native host boundary was not changed. It still owns Explorer discovery, `Progman`/`WorkerW` attachment, DirectComposition and WebView2 lifetime, global cursor polling, controls, and recovery. Production content is still served locally through the existing `https://aquarium.local/` virtual-host mapping.

The browser-side path is:

```text
habitat.js adapter
  -> core/engine.js fixed-step lifecycle
  -> habitats/planted-tank/scene.js composition
  -> core/behavior.js authoritative deterministic simulation
  -> core/fish.js one-way instanced Three.js projection
  -> core/environment.js procedural visual environment
  -> local Three.js 0.186.0 / WebGL2
```

The explicit invariant is enforced by tests: **simulation state is authoritative, and rendering is a one-way projection of simulation state**. Behavior imports neither Three.js nor DOM APIs. Rendering reads position, velocity, scale, seed, and simulation time and writes instance matrices without changing the school. Fish bodies, tails, eyes, and fins are four `InstancedMesh` draw parts independent of population size. The environment adds a local shader background, substrate, one particle field, instanced plant silhouettes, fog, and two lights.

The same `index.html`, entry module, engine, habitat, simulation, renderer, environment, shader, and bundled Three.js files execute in WebView2 and in the optional loopback browser preview. Python is only an optional development static-file server and is not imported or required by the runtime.

## Automated verification

`./build.ps1 -Target All` passed before the Windows run:

- 24 Node built-in tests passed: 12 behavior, 8 engine/lifecycle, and 4 render-contract tests;
- native fish-logic tests passed;
- native host-policy tests passed;
- the WebView2 SDK/runtime probe passed against installed Runtime 153.0.4234.48;
- the unchanged C++ host built x64 with `/W4 /WX`;
- `git diff main -- src` was empty.

The tests cover seeded repeatability, configuration bounds, finite zero-distance steering, flocking forces, personality-weighted cursor behavior, pointer-out recovery, soft bounds/depth, fixed-step catch-up caps, true scheduler cancellation, fresh resume timing, FPS-zero idle, diagnostics equivalence, one outstanding frame, renderer authority, fixed instancing, and deterministic visual layout.

## Browser preview — actually tested

The optional command `python -m http.server 8000 --bind 127.0.0.1` served `habitat/` without packages. The Codex in-app browser loaded only loopback module files. No console warning/error occurred and no external request was observed; the only incidental failure was the browser's initial local `/favicon.ico` request before a data favicon was added.

Observed in the shared runtime:

- 10 moving fish;
- 9 total scene draw calls and 4024 triangles;
- canvas pointer input changed `pointerCount` from 0 to 1 and reactions from 0 to 7, later 36;
- Space set `paused=true`; metrics remained byte-for-byte unchanged during a 1.2-second wait; the next Space restored `paused=false`;
- `D` hid the diagnostics overlay;
- approximately 39.7–43.0 FPS in the in-app browser.

The browser FPS is recorded only as preview evidence and is not used as the Windows wallpaper performance result.

## Windows desktop acceptance — actually tested

The final run lasted 16 minutes 11.966 seconds, from 19:59:46.763 through the deliberate clean stop at 20:15:58.729.

### Attachment and rendering

Initial discovered/attached topology was:

```text
Progman 0x31063E
  z=0 SHELLDLL_DefView 0x1101B2
  z=1 Aquarium host 0xC0534
       └ renderer child 0x60256
  z=2 WorkerW 0x230780
```

The host logged `ATTACH ASSUMPTION VERIFIED`, `ATTACH STRUCTURE OK`, `habitat-ready:three-webgl2`, and `STARTUP SUCCESS`. No ordinary always-on-bottom fallback exists. The screenshot [`sprint1-planted-tank.png`](../sprint1-planted-tank.png) was captured from the real Windows desktop after recovery and shows the habitat beneath normal Explorer icons.

Ten fish were visible and moved non-synchronously as one loose procedural school. A screen-difference sample taken while the desktop was actually shown compared 61,100 pixels at four-pixel stride over the habitat region across 1.5 seconds; 2,249 samples (3.681%) changed. This is direct screen evidence of visible animation, while the runtime independently reported continuous render frames.

### Desktop input ownership

Before restart, both `(180,40)` over the Git Bash icon and `(1000,400)` over blank desktop returned Explorer `SysListView32` PID 14788. A real synthesized left click selected `Git Bash`; a blank click cleared the selection; foreground remained Explorer `Progman` after both clicks.

After restart, the same checks returned replacement Explorer `SysListView32` PID 31876. `Git Bash` again became selected, blank click again cleared it, and replacement `Progman` remained foreground. Aquarium did not become the active interactive surface. Icon dragging was not separately repeated in Sprint 1.

### Cursor, pause, and resume

The native bridge polled the global cursor at approximately 23–25 Hz. Fish reaction count increased from 0 to 120 before Explorer restart while Aquarium remained input-transparent. After the final recovery it increased again from 0 to 57, confirming that bridge input continued to affect the recreated habitat.

`--pause` produced `paused=true`. A 1.2-second screen sample over 15,322 points showed exactly zero changed samples, no habitat metrics were emitted while paused, and three attributed GPU samples were `0, 0, 0%`. `--resume` restored approximately 40–43 FPS and reactions continued increasing. The new engine resets its timestamp and accumulator on resume, so paused wall time is not simulated.

### Win+D and Explorer recovery

Win+D/Show Desktop exposed the rendered habitat and normal icons without changing the validated desktop Z-order or input ownership.

One forced Explorer restart changed Explorer PID 14788 to 31876 while Aquarium remained PID 33496. The 1 Hz health check first detected the missing host, refused a fallback, backed off through 250/500/1000 ms, rediscovered the raised desktop, and logged `RECOVERY SUCCESS cycle=1`. The delayed `TaskbarCreated` broadcast then intentionally triggered a second defensive rebuild from the same single Explorer restart; the final stable runtime was generation 8 and logged `RECOVERY SUCCESS cycle=2`. Post-recovery rendering, pointer reactions, topology, icon selection, blank click, Win+D, and diagnostics all passed.

This duplicate rebuild is a known efficiency/stability caveat, not a hidden failure. The final host remained valid until deliberate quit.

### Clean shutdown

The tracked eight-process Aquarium/WebView2 tree exited within the 12-second verification window after `--quit`; no tracked PID remained. The final log line is `Aquarium.exe WebView2 composition wallpaper spike stopped`.

## Performance observations

These are short observations, not benchmarks:

| Measurement | Sprint 1 observation | Feasibility baseline |
|---|---:|---:|
| Habitat FPS at 1920×1080 | mostly 39–43 FPS; observed low 35.4 | mostly 38–43 FPS |
| Total scene draw calls | 9 | 9 |
| Triangles | 4024 | not previously recorded |
| Whole process-tree CPU, normalized over 4 logical CPUs | 9.98% over 10.02 s | 5.53% final five-second sample |
| Working set | 521.3 MiB pre-restart; 499.6 MiB post-recovery | 504.2 MiB post-recovery |
| Private bytes | 320.3 MiB pre-restart; 308.9 MiB post-recovery | 311 MiB post-recovery |
| GPU Engine, running | 38.67% average; 30.60–42.46% over five samples | variable 26.03–27.27% final and 40.09–44.05% earlier |
| GPU Engine, paused | 0.00% across three samples | 0.00% across two samples |
| Aquarium-owned TCP connections | 0 | 0 |

The new CPU sample is materially higher than the recorded feasibility sample. GPU remains within the earlier probe's variable high range, memory is essentially unchanged, and the target 60 FPS was not reached. Optimization and power-policy work are required before calling the product lightweight.

## Tested, inferred, and future work

### Tested here

- deterministic 10-fish simulation and one-way instanced projection;
- actual local WebView2/WebGL2 composition below Explorer icons;
- Explorer icon selection and blank-desktop input before and after restart;
- global cursor reaction without forwarding pointer input into WebView2;
- true pause/resume, screen stability, and paused GPU idle;
- Win+D;
- one forced Explorer restart with final in-process recovery;
- browser preview using the identical habitat implementation;
- zero Aquarium-owned TCP connections and no external habitat requests.

### Inferred from current APIs/design, not tested in Sprint 1

- the existing native `rate` bridge can request reduced rendering rates;
- the engine's `targetFps=0` lifecycle can serve display-off/lock idle once the native host supplies those signals;
- simulation/render separation permits fish geometry and materials to be replaced without behavior changes.

### Future architecture, not implemented or verified here

- 60 FPS on AC after profiling/optimization;
- approximately 30 FPS or another measured cap on battery;
- coverage estimation and reduced/stopped rendering when materially covered;
- session lock and display-power notifications driving rate zero;
- cursor polling capped to the useful render/input rate and stopped at rate zero;
- visual tuning to improve fish brightness, spacing, silhouettes, and plant/substrate finish;
- multi-monitor support, settings, packaging, installer, updates, habitat selection, feeding, and product UI.

## Risks and limitations

- WorkerW/Progman child topology is undocumented for third-party live wallpaper hosting.
- The working WebView2 arrangement deliberately uses a hidden offscreen CompositionController parent while attaching its root visual to the desktop renderer child's DirectComposition tree. Microsoft does not explicitly promise this split.
- The delayed `TaskbarCreated` signal caused a redundant second rebuild after the health-check recovery.
- This validation covers one Windows build, one WebView2 Runtime, one GPU/driver, one 1920×1080 monitor, and one Explorer restart.
- The school can cluster tightly and the deliberately subdued materials read dark in the captured desktop image. That is a visual-tuning limitation, not a rendering or input failure.
- No battery, substantial-cover, lock, display-off, suspend/resume, multi-monitor, DPI-transition, or long-duration soak policy was implemented or tested.
- The full WebView2 process tree remains heavy and the measured frame rate/CPU/GPU cost is not yet suitable for a claimed lightweight release.

## Files created or changed

Created:

- `docs/superpowers/specs/2026-09-21-habitat-foundation-design.md`
- `docs/superpowers/plans/2026-09-21-habitat-foundation.md`
- `habitat/package.json`
- `habitat/core/behavior.js`
- `habitat/core/engine.js`
- `habitat/core/environment.js`
- `habitat/core/fish.js`
- `habitat/habitats/planted-tank/config.js`
- `habitat/habitats/planted-tank/scene.js`
- `habitat/shaders/water-background.js`
- `tests/habitat/behavior.test.mjs`
- `tests/habitat/engine.test.mjs`
- `tests/habitat/render-contract.test.mjs`
- `docs/evidence/sprint1-habitat-final.log`
- `docs/sprint1-habitat-report.md`
- `sprint1-planted-tank.png`

Changed:

- `README.md`
- `build.ps1`
- `habitat/habitat.js`
- `habitat/index.html`
- `THIRD_PARTY_NOTICES.md`

No file under `src/` changed.

## License and reuse

The existing vendored Three.js 0.186.0 modules remain under the MIT license recorded in `habitat/vendor/three/LICENSE.txt`; the existing WebView2 SDK notices remain unchanged. No package, CDN dependency, model, texture, fish asset, Lively code, or `desktop-habitats` code was added. The simulation, renderer composition, procedural geometry, shader, environment, tests, and adapter code are original Aquarium.exe work. `desktop-habitats` and Lively remain behavioral/architectural references only.

## Recommendation

**GO WITH CONDITIONS** for the next bounded MVP step, not for release. Keep WebView2 + locally bundled Three.js as the recommended content architecture because the shared runtime, deterministic simulation boundary, instanced projection, native bridge, desktop composition, input ownership, pause, and recovery all worked on the target machine. Before a real MVP claim, reduce CPU/GPU/memory cost, improve visual readability/spacing, implement and test the power/session policy, eliminate or tolerate redundant recovery, and validate the undocumented host split across supported Windows/WebView2/GPU configurations.

Full machine-specific HWND/PID diagnostics are intentionally retained as historical engineering evidence in this private repository in `docs/evidence/sprint1-habitat-final.log`; the associated screenshot intentionally contains this machine's desktop icons.
