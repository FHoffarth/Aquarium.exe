# WebView2 Habitat Host Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Demonstrate a local WebView2/Three.js habitat through the proven DirectComposition desktop host and recover it in-process after three consecutive Explorer restarts.

**Architecture:** Preserve Spike #2's Progman/WorkerW host and replace only its D3D swap-chain content with a WebView2 CompositionController attached to the existing DirectComposition visual tree. A stable hidden control window and a small state machine rebuild desktop-bound HWND, composition, and WebView2 resources after Explorer loss.

**Tech Stack:** Win32 C++20, D3D11, DirectComposition, WebView2 native SDK 1.0.3405.78, local HTML/JavaScript, Three.js/WebGL2.

**Spec:** `docs/sprint3-architecture.md`

## Global Constraints

- Start from commit `00e0b58` on branch `codex/webview2-habitat-host`.
- Preserve the raised-desktop discovery and `SHELLDLL_DefView > Aquarium > WorkerW` attachment behavior.
- Use WebView2 CompositionController; never fall back to a conventional HWND controller or ordinary bottom window.
- Keep all habitat content local; no CDN, runtime network, accounts, analytics, telemetry, downloaded aquarium assets, or input hooks.
- Keep Windows hosting and habitat simulation separate.
- Do not install or introduce a .NET SDK dependency.

## Review Focus

- WebView creation callbacks arriving after a recovery generation has been abandoned must not publish stale COM objects.
- Explorer disappearing during asynchronous WebView initialization must enter recovery without terminating the process.
- Pause state and rate hint must survive resource recreation.
- Control commands must remain reachable while the desktop-bound host is absent.
- Exit must close controllers and leave no Aquarium-owned WebView2 processes.

---

### Task 1: Vendor the minimum native WebView2 build dependency

**Files:**
- Create: `third_party/webview2/include/WebView2.h`
- Create: `third_party/webview2/include/WebView2EnvironmentOptions.h`
- Create: `third_party/webview2/x64/WebView2Loader.dll.lib`
- Create: `third_party/webview2/x64/WebView2Loader.dll`
- Create: `third_party/webview2/LICENSE.txt`
- Create: `third_party/webview2/NOTICE.txt`
- Create: `THIRD_PARTY_NOTICES.md`
- Modify: `build.ps1`

**Interfaces:**
- Produces: native headers and `WebView2Loader.dll` beside `AquariumSpike.exe`; no package manager or .NET requirement.

- [ ] Copy only the named artifacts from official NuGet package 1.0.3405.78 and record its SHA-256 `D035807B2AABA871E8C014759626F566E96934E6CE6F0587056EE81D5228C373`.
- [ ] Add a compile-only include/link probe to the existing warning-as-error build.
- [ ] Run `./build.ps1 -Target All`; expect the existing fish test and executable build to pass.
- [ ] Commit the dependency/build baseline.

### Task 2: Add tested recovery and bridge policies

**Files:**
- Create: `src/host_policy.h`
- Create: `tests/host_policy_tests.cpp`
- Modify: `build.ps1`

**Interfaces:**
- Produces: `RecoveryBackoff`, `HostState`, and locale-independent JSON message builders consumed by `main.cpp`.

- [ ] Write tests for 250/500/1000/2000/5000 ms capped backoff, recovery state transitions, pointer-out JSON, normalized pointer JSON, paused state, and render-rate JSON.
- [ ] Run the policy test before implementation; expect compile failures for the missing policy API.
- [ ] Implement the smallest header-only policy API.
- [ ] Run all C++ tests; expect all to pass.
- [ ] Commit the policy layer.

### Task 3: Prove WebView2 CompositionController with local Canvas content

**Files:**
- Create: `src/webview_runtime.h`
- Create: `src/webview_runtime.cpp`
- Create: `habitat/index.html`
- Create: `habitat/habitat.js`
- Modify: `src/main.cpp`
- Modify: `build.ps1`

**Interfaces:**
- `WebViewRuntime::Initialize(HWND, IDCompositionDevice*, IDCompositionVisual*, RECT, path, generation, callback)` creates the asynchronous composition controller.
- `WebViewRuntime::PostJson`, `SetVisible`, and `Shutdown` are used by the native host.
- Produces: local Canvas habitat readiness and diagnostics through web messages.

- [ ] Build a minimal local habitat that paints a dark diagnostic field and posts `habitat-ready:canvas`.
- [ ] Implement the DirectComposition visual tree and CompositionController binding without a conventional controller fallback.
- [ ] Map only the local habitat folder to `https://aquarium.local`, block external navigation, and pass WebView readiness to the main loop.
- [ ] Replace the native D3D fish renderer while preserving top-level initialization-before-attachment and the existing desktop styles/order.
- [ ] Build and run on Windows; require an actual screen capture showing Canvas content beneath real Explorer icons. If absent, stop and document the exact HRESULT/topology.
- [ ] Commit the first composition proof.

### Task 4: Add the local Three.js/WebGL2 habitat

**Files:**
- Create: `habitat/vendor/three.module.min.js`
- Create: `habitat/vendor/THREE-LICENSE.txt`
- Modify: `habitat/index.html`
- Modify: `habitat/habitat.js`
- Modify: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Consumes the bridge message forms from Task 2.
- Produces three autonomous primitive fish, cursor repulsion, pause/resume, rate limiting, and diagnostic readiness/FPS messages.

- [ ] Pin and locally bundle one official Three.js npm distribution plus its MIT license.
- [ ] Implement three primitive fish with autonomous motion and native-cursor proximity response; keep the habitat browser-runnable and Windows-agnostic.
- [ ] Ensure pause cancels animation scheduling and resume/rate hints restore bounded scheduling.
- [ ] Run the host and require `habitat-ready:three:webgl2`, visible motion, cursor reaction, and no remote resource loads.
- [ ] Commit the habitat delta.

### Task 5: Implement in-process Explorer recovery

**Files:**
- Modify: `src/main.cpp`
- Modify: `src/webview_runtime.h`
- Modify: `src/webview_runtime.cpp`
- Modify: `tests/host_policy_tests.cpp`

**Interfaces:**
- Consumes recovery policy from Task 2 and WebView lifecycle from Task 3.
- Produces a stable hidden control HWND and repeatable `Discover -> Create -> Initialize -> Attach -> Running` lifecycle.

- [ ] Extend policy tests with stale-generation rejection and pause/rate state preservation; run RED.
- [ ] Route registered controls and `TaskbarCreated` through the stable hidden owner instead of the Explorer-owned host.
- [ ] Add a 1 Hz structural health check and capped retry schedule; log every loss, attempt, discovered handle, generation, and restored state.
- [ ] On loss, close stale WebView2/composition resources and recreate desktop-bound resources in-process once the replacement shell exists.
- [ ] Run tests GREEN, then reproduce one Explorer restart and verify the same Aquarium PID restores the habitat beneath icons.
- [ ] Commit recovery.

### Task 6: Execute the full Windows acceptance matrix

**Files:**
- Create: `docs/sprint3-test-log.md`
- Create: `spike3-webview2-screen.png`
- Create: `spike3-recovery-screen.png`

**Interfaces:**
- Produces observed evidence only; it does not change architecture.

- [ ] Verify initial startup, three fish animation, cursor reaction, icon selection, blank click, pause/resume, and Show Desktop.
- [ ] Run continuously for at least ten minutes and record frame/diagnostic progress.
- [ ] Restart Explorer three consecutive times; require the same Aquarium PID and visible restoration after each restart.
- [ ] Sample CPU, working set, WebView2 child-process count/working set, GPU counters, and observed FPS.
- [ ] Exit normally and verify no Aquarium-owned WebView2 processes remain.
- [ ] Save actual desktop and post-recovery screenshots and commit the evidence.

### Task 7: Update build and feasibility documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/feasibility-report.md`
- Modify: `docs/sprint3-architecture.md`
- Modify: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Produces the final tested/inferred/future distinction and sprint verdict.

- [ ] Document exact WebView2 runtime/SDK versions, hosting APIs, visual tree, bridge, recovery mechanism, tests, diagnostics, files, licenses, risks, and failures.
- [ ] Preserve Spike #1 and #2 as historical evidence and supersede them only with observed Sprint #3 results.
- [ ] Run `git diff --check`, the full build/test command, and a clean-exit smoke test.
- [ ] Commit the final report without merging or publishing.
