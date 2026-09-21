# Habitat Performance Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain Aquarium.exe's persistent 39–43 FPS presentation rate, attribute CPU/GPU/memory cost across the native/WebView2 pipeline, and produce enough controlled evidence to decide whether Habitat Foundation may merge.

**Architecture:** Preserve the native wallpaper host and add disabled-by-default, local-only timing hooks around the existing Habitat Runtime boundaries. Use repeatable Windows process/GPU sampling plus generated audit profiles to compare the immutable feasibility baseline, Habitat Foundation, isolated scene components, fish counts, render scales, and FPS caps; make no optimization until measurements identify a root cause.

**Tech Stack:** PowerShell 7, Windows performance counters/CIM, JavaScript ES modules, Node 24 built-in tests, Three.js/WebGL2, WebView2 CompositionController, existing Win32 control protocol.

**Spec:** User-provided “Aquarium.exe Product Sprint 1 — Habitat Performance Audit” brief attached 2026-09-21.

## Global Constraints

- Work only on `audit/habitat-performance`, forked exactly from `feature/habitat-foundation` at `1a3a1ab51bbd324cf395cde459c8b9241addb056`.
- Do not merge, tag, release, or change `main`, `feature/habitat-foundation`, or `feasibility-v1`.
- Measure `feasibility-v1` and Habitat Foundation before optimizing.
- Freeze Progman/WorkerW, DirectComposition, CompositionController parenting/visual targeting, recovery generations, and native input ownership; temporary native instrumentation must be reverted.
- Attribute GPU only from PID-qualified Windows GPU Engine counters; never report adapter-wide utilization as Aquarium-specific.
- Diagnostic modes stay local, disabled by default, and must not add packages, telemetry, cloud, or external network access.
- 25/50 fish are audit-only; the product default remains 10.
- Any retained optimization requires an isolated before/after measurement, unchanged behavior/visual result, full tests, and a clean revert path.

## Review Focus

- Profiling overhead can perturb frame pacing: disabled mode must preserve existing timing, while enabled mode batches reports and avoids per-frame allocation.
- Chromium process identities change after every run/recovery: sampling must discover descendants from the current Aquarium root and classify roles from command lines each time.
- GPU counters can double-count engines or unrelated PIDs: filter exact current descendant PIDs and report summed per-engine samples with method limitations.
- rAF and explicit FPS gating can quantize intervals: retain raw presentation intervals and report clusters, median, p95, min, and max rather than only averages.
- Generated audit profiles can leak into a product run: each run must record the active profile, restore the default profile, and final verification must prove product default 10/60/scale 1.

---

### Task 1: Reproducible audit controls and timing model

**Files:**
- Create: `habitat/core/performance.js`
- Create: `habitat/audit-config.js`
- Create: `tests/habitat/performance.test.mjs`
- Modify: `habitat/habitat.js`
- Modify: `habitat/habitats/planted-tank/scene.js`
- Modify: `habitat/index.html`
- Modify: `build.ps1`

**Interfaces:**
- Produces: `createPerformanceRecorder({ enabled, reportIntervalMs, now })` with allocation-bounded `beginFrame`, `record`, `finishFrame`, and `snapshot` methods.
- Produces: frozen `readAuditConfig(location)` with defaults `{ enabled:false, mode:'full', fishCount:10, renderScale:1, targetFps:null, pointerMode:'normal' }`.
- Extends diagnostics only when enabled with raw frame intervals and aggregate `simulationMs`, `fishProjectionMs`, `environmentMs`, `renderMs`, and `callbackMs`.

- [ ] **Step 1: Write failing tests for disabled no-op behavior, statistics, interval clusters, config validation, and snapshot reset**

Run: `node --test tests/habitat/performance.test.mjs`

Expected: FAIL because `performance.js` and `audit-config.js` do not exist.

- [ ] **Step 2: Implement the recorder and audit configuration**

Use fixed numeric arrays sized for at most 4096 intervals per report, sorted only during low-frequency snapshot creation. Reject unsupported modes, fish counts outside 0–50, render scales outside `(0,1]`, FPS outside 0–60, and pointer modes outside `normal|stationary|ignore`.

- [ ] **Step 3: Add opt-in boundary timing without changing the default runtime path**

Measure the fixed-step simulation in `step`, fish instancing, environment update, `renderer.render`, and total animation callback. Add actual render-to-render intervals separately from rAF callback deltas. When disabled, skip `performance.now` calls and timing-array writes.

- [ ] **Step 4: Add audit-only scene modes and generated-profile loading**

Support `full`, `fish-only`, `environment-only`, `minimal-render`, and `no-render` modes. Audit fish counts may be 0/1/10/25/50; renderer capacity follows the audit count, but the normal validated configuration remains 10. Apply render scale only to WebGL pixel ratio, not window size.

- [ ] **Step 5: Run all tests and commit diagnostic tooling**

Run: `./build.ps1 -Target All`

Commit: `chore: add local habitat performance diagnostics`

### Task 2: Equivalent feasibility and Habitat Foundation baselines

**Files:**
- Create: `tools/performance/Measure-AquariumRun.ps1`
- Create: `docs/evidence/performance/baseline-feasibility.json`
- Create: `docs/evidence/performance/baseline-habitat.json`

**Interfaces:**
- Produces one JSON result per run containing OS/display/runtime versions, active profile, timestamps, process roles/PIDs, per-process CPU/memory, PID-filtered GPU samples, native log metrics, TCP count, and run validity checks.

- [ ] **Step 1: Implement a read-only run sampler and validate it against a paused/running control**

The script must discover descendants recursively, classify `browser|renderer|gpu|network|storage|crashpad|native|console`, normalize CPU by four logical processors, and filter GPU Engine instances by exact PID tokens. It must refuse results if Aquarium is not attached/running or another Aquarium instance exists.

- [ ] **Step 2: Build and measure `feasibility-v1` in a temporary detached worktree**

Run at least three equivalent 15-second running samples plus one paused sample at 1920×1080. Record FPS/log output, CPU, GPU, working set, private bytes, process roles, cursor rate, and zero/nonzero TCP state.

- [ ] **Step 3: Build and measure unmodified Habitat Foundation under the same conditions**

Use the same durations, desktop state, cursor position, and sampling code. Do not enable detailed JavaScript timing yet.

- [ ] **Step 4: Compare variance before forming a bottleneck hypothesis**

Report medians and ranges across repeats. Explicitly separate comparable whole-tree measurements from native-host-only historical log numbers.

### Task 3: Frame pacing and component isolation matrix

**Files:**
- Create: `tools/performance/Set-AquariumAuditProfile.ps1`
- Create: `docs/evidence/performance/frame-and-component-matrix.json`

**Interfaces:**
- Consumes: Task 1 audit profiles and Task 2 sampler.
- Produces controlled rows keyed by `{ mode, fishCount, renderScale, targetFps, pointerMode }`.

- [ ] **Step 1: Measure full-scene raw frame intervals at target 60**

Capture at least 1,000 rendered intervals. Report mean, median, p95, min/max, and 1 ms interval buckets; identify alternating/quantized clusters directly from the data.

- [ ] **Step 2: Measure fish-count scaling**

Run environment-only/0 fish and full scene with 1, 10, 25, and 50 fish. Compare simulation, fish projection, renderer, total callback, CPU, GPU, and memory. Treat 25/50 solely as diagnostic loads.

- [ ] **Step 3: Isolate scene and rendering components**

Measure full, fish-only, environment-only, minimal-render, and no-render profiles at otherwise identical settings. Use this to distinguish JavaScript/simulation cost from WebGL/Chromium/composition cost.

- [ ] **Step 4: Measure render scale**

Measure full scene at 1.0, 0.75, and 0.5 internal scale while retaining the same desktop window dimensions. Compare GPU, render timing, FPS distribution, and subjective screenshot equivalence separately.

- [ ] **Step 5: Measure FPS caps**

Measure target 60, 45, 30, and 20 FPS. Record achieved interval clusters, CPU/GPU, pause cost, and a separate subjective motion note for 30 FPS.

### Task 4: Cursor bridge, pause, memory, and browser preview

**Files:**
- Create: `docs/evidence/performance/cursor-pause-browser.json`

- [ ] **Step 1: Attribute steady-state memory by process role**

Record native, browser, renderer, GPU, network, storage, crashpad, and console working/private bytes for baseline and Habitat Foundation; explain shared-page and process-model limitations.

- [ ] **Step 2: Reconfirm pause/idle**

Measure callbacks, simulation steps, native and whole-tree CPU, PID-attributed GPU, and bridge update rate while paused for the same duration as running samples.

- [ ] **Step 3: Compare cursor modes**

Measure normal stationary input, normal cursor movement, and JavaScript pointer-ignore mode. If ambiguity remains, temporarily suppress only the native cursor `PostWebMessageAsJson`, measure once, and revert the native diff immediately.

- [ ] **Step 4: Run the identical runtime in ordinary-browser preview**

Serve with `python -m http.server 8000 --bind 127.0.0.1`. Measure raw frame pacing and runtime component timing with the same profile; record browser process CPU/GPU only when PID attribution is unambiguous.

### Task 5: Root-cause decision and optional low-risk optimization

**Files:**
- Modify only if evidence justifies: `habitat/core/engine.js`, `habitat/habitat.js`, or the narrow measured hotspot
- Modify corresponding test under: `tests/habitat/`

- [ ] **Step 1: State one evidence-backed root-cause hypothesis**

Trace the ~40 FPS result through rAF callback intervals, the engine's explicit render gate, WebGL render timing, and PID-attributed GPU results. Do not change code until the measured layer is identified.

- [ ] **Step 2: Test the smallest reversible hypothesis change**

Add a failing timing-policy test first. Change one variable only, rerun the same baseline profile at least three times, and retain the change only if it is behaviorally safe and its effect is repeatable.

- [ ] **Step 3: Revert unsuccessful or purely experimental changes**

Final source must contain no native-host alteration, higher default fish count, permanent reduced resolution, or forced lower frame cap.

### Task 6: Report, verification, and audit-branch publication

**Files:**
- Create: `docs/sprint1b-performance-audit.md`
- Retain useful raw evidence under: `docs/evidence/performance/`
- Remove generated/temp profiles and temporary worktree

- [ ] **Step 1: Write the 20-section audit report**

Separate actual measurements, supported inference, subjective motion notes, and remaining uncertainty. Finish with exactly one of the three recommendations supplied in the audit brief.

- [ ] **Step 2: Verify branch boundaries and defaults**

Run `git diff feature/habitat-foundation -- src`, confirm it is empty, verify product defaults 10 fish/60 target/scale 1, and confirm no generated audit profile or external network dependency remains.

- [ ] **Step 3: Run final build and tests**

Run: `./build.ps1 -Target All`

Expected: all JavaScript/native tests pass and the unchanged native host builds with `/W4 /WX`.

- [ ] **Step 4: Commit and push only the audit branch**

Push `audit/habitat-performance`; do not merge, tag, release, or create product work.
