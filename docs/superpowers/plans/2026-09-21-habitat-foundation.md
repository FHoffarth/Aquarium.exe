# Habitat Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three-fish feasibility scene with a reusable deterministic Habitat Runtime and a procedural 10-fish Planted Tank without changing the proven native Windows host.

**Architecture:** Plain JavaScript simulation state is authoritative and independent of Three.js. The engine advances fixed-step behavior, then an instanced renderer projects state one-way into shared fish geometry; the same runtime receives either WebView2 bridge input or browser-preview input. Production continues to use the existing local `aquarium.local` mapping.

**Tech Stack:** JavaScript ES modules, bundled Three.js 0.186.0/WebGL2, Node 24 built-in test runner, optional Python 3 static preview server, unchanged native C++20 Win32/WebView2 host.

**Spec:** `docs/superpowers/specs/2026-09-21-habitat-foundation-design.md`

## Global Constraints

- Work only on `feature/habitat-foundation`; do not merge to `main` or modify `feasibility-v1` or historical spike branches.
- Do not modify native host architecture or its pointer/state/rate/probe bridge contract.
- Simulation state is authoritative; behavior never reads Three.js transforms.
- Diagnostics are observational and must not alter random consumption, simulation decisions, or timing semantics.
- All content stays local; add no package, CDN, telemetry, downloaded model, texture, or runtime network dependency.
- Use 8–12 fish, default 10, with one coherent procedural visual language.
- Pause must cancel active simulation/render scheduling and resume with a fresh timestamp.
- Preserve `/W4 /WX` native build discipline and all existing tests.

## Review Focus

- A long pause or background stall must not enter simulation time or teleport fish; Task 2 pins clock reset and catch-up caps.
- Zero-distance neighbors and cursor overlap must not create NaN/Infinity steering; Task 1 tests finite bounded output.
- Pointer-out must decay awareness instead of leaving fish permanently reactive; Task 1 tests recovery.
- Diagnostics enabled versus disabled must produce identical simulation state for the same seed/input; Task 2 tests observational behavior.
- Renderer projection must not mutate authoritative fish state; Task 3 snapshots state before and after projection.

---

### Task 1: Deterministic configuration and fish behavior

**Files:**
- Create: `habitat/package.json`
- Create: `habitat/core/behavior.js`
- Create: `habitat/habitats/planted-tank/config.js`
- Create: `tests/habitat/behavior.test.mjs`

**Interfaces:**
- Produces: `createPlantedTankConfig(overrides = {}) -> frozen config`
- Produces: `validatePlantedTankConfig(config) -> config` or throws `RangeError`/`TypeError`
- Produces: `createSchool(config) -> { fish, elapsedSeconds, seed }`
- Produces: `stepSchool(school, input, dtSeconds, bounds) -> void`
- Produces: `createPointerState() -> { present, x, y, z, eventsReceived }`
- Fish state remains plain numeric data and contains no Three.js object.

- [ ] **Step 1: Add the ESM descriptor and failing deterministic/configuration tests**

```json
{
  "private": true,
  "type": "module"
}
```

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { createSchool, stepSchool } from '../../habitat/core/behavior.js';
import { createPlantedTankConfig } from '../../habitat/habitats/planted-tank/config.js';

test('same seed creates the same school', () => {
  const config = createPlantedTankConfig({ seed: 20260921, fishCount: 10 });
  assert.deepEqual(createSchool(config), createSchool(config));
});

test('population is constrained to the sprint range', () => {
  assert.throws(() => createPlantedTankConfig({ fishCount: 7 }), RangeError);
  assert.throws(() => createPlantedTankConfig({ fishCount: 13 }), RangeError);
});

test('steering remains finite and bounded at zero separation', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  school.fish[1].position = { ...school.fish[0].position };
  stepSchool(school, { present: false, x: 0, y: 0, z: 0 }, 1 / 60, config.bounds);
  for (const fish of school.fish) {
    assert.ok(Object.values(fish.position).every(Number.isFinite));
    assert.ok(Object.values(fish.velocity).every(Number.isFinite));
    assert.ok(Math.hypot(fish.velocity.x, fish.velocity.y, fish.velocity.z) <= fish.maximumSpeed + 1e-9);
  }
});
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run: `node --test tests/habitat/behavior.test.mjs`

Expected: FAIL because `behavior.js` and `config.js` do not exist.

- [ ] **Step 3: Implement validated configuration, seeded variation, school creation, and bounded steering**

Implement a small integer PRNG, plain `{x,y,z}` vector helpers, deterministic fish parameter creation, bounded neighbor pair accumulation, cohesion/alignment/separation, soft boundaries/depth preference, wander, and personality-weighted cursor notice/curiosity/threat/recovery. Reuse scratch numeric fields/objects inside the step; do not import Three.js.

- [ ] **Step 4: Extend tests for separation, cohesion/alignment, cursor personalities, pointer-out recovery, boundaries, and determinism**

Add explicit tests that:

- nearby overlapping fish gain separating velocity;
- a fish outside a local group receives a cohesion component;
- curious fish mildly approach at notice distance while cautious fish hold or retreat;
- close cursor input causes bounded avoidance;
- repeated pointer-out steps reduce cursor awareness;
- edge/depth forces point back into bounds;
- identical seeds and input sequences produce deeply equal states;
- different seeds produce non-identical personality values.

- [ ] **Step 5: Run the behavior suite**

Run: `node --test tests/habitat/behavior.test.mjs`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add habitat/package.json habitat/core/behavior.js habitat/habitats/planted-tank/config.js tests/habitat/behavior.test.mjs
git commit -m "feat: add deterministic fish behavior"
```

### Task 2: Engine timing, lifecycle, and observational diagnostics

**Files:**
- Create: `habitat/core/engine.js`
- Create: `tests/habitat/engine.test.mjs`
- Modify: `build.ps1`

**Interfaces:**
- Produces: `FrameClock` with `resume(nowMs)`, `pause()`, `setTargetFps(fps)`, and `tick(nowMs)`; `tick` updates `stepCount`, `shouldRender`, and `frameDeltaMs` without allocating a result object.
- Produces: `createHabitatEngine(options)` with `start()`, `setPaused(bool)`, `setTargetFps(number)`, `setPointer(pointer)`, `requestProbe()`, and `dispose()`.
- Consumes habitat lifecycle: `step(dt, pointer)`, `project(simulationTime)`, `resize(width,height)`, `getFishCount()`, `dispose()`.

- [ ] **Step 1: Write failing clock/lifecycle tests**

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { FrameClock } from '../../habitat/core/engine.js';

test('resume after pause discards paused wall time', () => {
  const clock = new FrameClock();
  clock.resume(1000);
  clock.tick(1017);
  clock.pause();
  clock.resume(100000);
  clock.tick(100017);
  assert.ok(clock.stepCount <= 2);
  assert.ok(clock.frameDeltaMs <= 17.1);
});

test('catch-up is capped after a long frame', () => {
  const clock = new FrameClock({ maxSteps: 4 });
  clock.resume(0);
  clock.tick(10000);
  assert.equal(clock.stepCount, 4);
});
```

- [ ] **Step 2: Run the clock suite and verify failure**

Run: `node --test tests/habitat/engine.test.mjs`

Expected: FAIL because `engine.js` does not exist.

- [ ] **Step 3: Implement `FrameClock` and engine scheduling**

Use injected `requestFrame`, `cancelFrame`, and `now` functions so lifecycle tests need no browser. Pausing cancels the scheduled callback. Resume clears accumulator and render timestamps. Rate zero uses the same idle state. The engine samples diagnostics after rendering and posts snapshots without calling simulation methods.

- [ ] **Step 4: Add engine tests with fake scheduler and habitat**

Verify one outstanding callback maximum, pause cancellation, no simulation/render while paused, smooth resume, target rate zero idling, pointer replacement, probe snapshot fields, and identical fake-habitat step history with diagnostics enabled or disabled.

- [ ] **Step 5: Add habitat tests to the existing test target**

Update `build.ps1` to require the already-present Node executable only for tests and run:

```powershell
node --test tests/habitat/behavior.test.mjs tests/habitat/engine.test.mjs
```

Do not install packages or alter the native compiler commands.

- [ ] **Step 6: Run all tests**

Run: `.\build.ps1 -Target Tests`

Expected: behavior/engine tests and all three native probes PASS.

- [ ] **Step 7: Commit**

```powershell
git add habitat/core/engine.js tests/habitat/engine.test.mjs build.ps1
git commit -m "feat: add habitat runtime lifecycle"
```

### Task 3: Instanced fish projection and procedural environment

**Files:**
- Create: `habitat/core/fish.js`
- Create: `habitat/core/environment.js`
- Create: `habitat/shaders/water-background.js`
- Create: `tests/habitat/render-contract.test.mjs`

**Interfaces:**
- Produces: `createFishRenderer(scene, maximumFish) -> { project(school,time), drawCallBudget, dispose() }`
- Produces: `createEnvironment(scene, config) -> { updateVisuals(time), dispose() }`
- Renderer consumes school state read-only.

- [ ] **Step 1: Write the failing renderer-authority test**

Create a Three.js `Scene`, build a deterministic school, deep-clone it, call `project`, and assert the school remains deeply equal. Assert the renderer exposes four instanced fish meshes and sets their instance count to the school population. Also read `behavior.js` as text and assert it contains no import/reference to `THREE` or DOM globals.

- [ ] **Step 2: Run the renderer contract test and verify failure**

Run: `node --test tests/habitat/render-contract.test.mjs`

Expected: FAIL because `fish.js` does not exist.

- [ ] **Step 3: Implement shared instanced fish geometry**

Create shared body, tail, eye, and fin geometry/materials. Use instance color and reusable matrices/quaternions/vectors. Derive heading, banking, tail phase, and scale from authoritative state and simulation time. Never write to the school.

- [ ] **Step 4: Implement the environment**

Add a low-contrast shader background, substrate plane, bounded `Points` particle field, instanced plant silhouettes, fog, hemisphere light, and one soft directional light. Allocate procedural positions deterministically from habitat seed.

- [ ] **Step 5: Run all JavaScript tests**

Run: `node --test tests/habitat/behavior.test.mjs tests/habitat/engine.test.mjs tests/habitat/render-contract.test.mjs`

Expected: all tests PASS and renderer projection leaves state unchanged.

- [ ] **Step 6: Commit**

```powershell
git add habitat/core/fish.js habitat/core/environment.js habitat/shaders/water-background.js tests/habitat/render-contract.test.mjs
git commit -m "feat: render instanced fish and planted environment"
```

### Task 4: Planted Tank composition, shared adapters, and preview

**Files:**
- Create: `habitat/habitats/planted-tank/scene.js`
- Modify: `habitat/habitat.js`
- Modify: `habitat/index.html`
- Modify: `README.md`

**Interfaces:**
- Produces: `createPlantedTank(renderer) -> engine habitat lifecycle object`.
- `habitat.js` selects WebView2 or preview input but creates exactly one Planted Tank path.
- Retains readiness string `habitat-ready:three-webgl2` and existing failure prefixes.

- [ ] **Step 1: Compose the habitat**

Create the scene, fixed perspective camera, validated configuration, authoritative school, fish renderer, and environment. Convert normalized pointer coordinates to a stable world plane and pass only plain coordinates into `stepSchool`.

- [ ] **Step 2: Replace the feasibility entry point**

Keep the existing WebGL2 requirement/error handling. Normalize WebView2 pointer/state/rate/probe messages into engine calls. When WebView2 is absent, attach local pointer move/leave, Space pause/resume, and `D` diagnostics toggle. Emit compact metrics containing FPS, frame time, fish count, calls, triangles, pointer count, and pause state.

- [ ] **Step 3: Update HTML and development documentation**

Rename feasibility/probe labels to product/habitat language, add an unobtrusive diagnostics element hidden by default, and document:

```powershell
cd habitat
python -m http.server 8000 --bind 127.0.0.1
```

State that Python is optional development-only and production still uses `aquarium.local`.

- [ ] **Step 4: Run automated validation**

Run: `.\build.ps1 -Target All`

Expected: all JavaScript/native tests PASS and `AquariumSpike.exe` builds with `/W4 /WX`.

- [ ] **Step 5: Run browser preview smoke**

Serve `habitat/` on loopback, open the preview, verify 10 moving non-identical fish, local pointer reaction/recovery, Space pause/resume, `D` diagnostics, and no external requests. Stop the server after the check.

- [ ] **Step 6: Commit**

```powershell
git add habitat/habitats/planted-tank/scene.js habitat/habitat.js habitat/index.html README.md
git commit -m "feat: add planted tank habitat"
```

### Task 5: Windows acceptance smoke, evidence, and branch publication

**Files:**
- Create: `docs/evidence/sprint1-habitat-final.log`
- Create: `sprint1-planted-tank.png`
- Create: `docs/sprint1-habitat-report.md`
- Modify only if results require documentation correction: `README.md`

**Interfaces:**
- No new code interface; validates the complete branch against the frozen host.

- [ ] **Step 1: Run final automated verification**

Run: `.\build.ps1 -Target All`

Expected: every JavaScript/native test passes and final executable builds.

- [ ] **Step 2: Execute the Windows desktop acceptance smoke**

Launch the built Aquarium and record actual observations for: below-icon composition, icon click, blank click, approximately 10 visible moving fish, non-synchronized movement, visible schooling, cursor reaction/recovery, pause idle, smooth resume, Win+D, one forced Explorer restart/recovery, and clean quit.

- [ ] **Step 3: Measure the final run**

Record continuous duration, habitat FPS/frame time, draw calls, triangles, fish count, process-tree working set/private bytes, normalized CPU, attributed GPU samples, cursor/pointer counters, and Aquarium-owned TCP connections. Compare to the feasibility observations without claiming improvement unless supported.

- [ ] **Step 4: Capture evidence and report**

Save one focused desktop screenshot and the final runtime log. Write the architecture, observed acceptance results, measurements, baseline comparison, limitations, native-file diff result, and recommendation in `docs/sprint1-habitat-report.md`.

- [ ] **Step 5: Verify frozen infrastructure and repository state**

Run:

```powershell
git diff main -- src
git diff --check
git status --short
```

Expected: no `src/` change, no whitespace errors, and only intended evidence/report changes before commit.

- [ ] **Step 6: Commit final evidence**

```powershell
git add docs/evidence/sprint1-habitat-final.log sprint1-planted-tank.png docs/sprint1-habitat-report.md README.md
git commit -m "docs: record planted tank validation"
```

- [ ] **Step 7: Final verification and push feature branch only**

Run the complete build once more, confirm a clean working tree, confirm `main` and `feasibility-v1` are unchanged, and push only:

```powershell
git push --set-upstream origin feature/habitat-foundation
```

Do not merge, tag, create a release, or start another sprint.
