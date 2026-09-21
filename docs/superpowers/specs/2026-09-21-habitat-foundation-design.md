# Aquarium.exe Habitat Foundation Design

## Purpose

Sprint 1 turns the successful Windows wallpaper feasibility probe into the first product-shaped habitat while preserving the proven host unchanged. The deliverable is a reusable browser-side Habitat Runtime and one explicit habitat, **Planted Tank**, containing 8–12 procedural fish whose movement, loose schooling, depth, cursor response, and environment begin to feel calm and alive.

The implementation remains fully local. Production continues to load the same habitat files through WebView2's existing `https://aquarium.local/` mapping. An ordinary browser can run those files through an optional development-only `python -m http.server`; Python is not a product or build dependency.

The visual target is: **real enough to feel alive, stylized enough to feel like Aquarium.exe.** This sprint establishes behavior, atmosphere, and replaceable rendering foundations rather than detailed species art.

## Frozen boundary

The native Windows host is frozen infrastructure. Sprint 1 does not redesign or refactor Progman/WorkerW discovery, Explorer hierarchy handling, HWND ownership, DirectComposition, WebView2 CompositionController setup, the split controller-parent/visual-target arrangement, lifecycle generations, restart recovery, retry/backoff, input ownership, or the native process architecture.

The existing bridge contract remains:

- native to habitat: `pointer`, `state`, `rate`, and `probe` JSON messages;
- habitat to native: `habitat-ready:three-webgl2`, failure strings, and observational diagnostic strings.

If implementation requires a new native responsibility or a change to this contract, work stops for review. No native change is planned.

## Architectural invariants

1. **Simulation state is authoritative. Rendering is a one-way projection of simulation state.** Fish position, velocity, preferred movement, depth preference, behavior weights, personality seed, and response state live in plain simulation data. Three.js meshes and instance matrices never become the source of truth and are never read back by behavior code.
2. The behavior module does not import Three.js or access DOM, WebView2, HWND, Explorer, or browser event objects.
3. Replacing fish geometry, materials, or render strategy must not require rewriting fish behavior.
4. Production and browser preview execute the same engine, simulation, renderer, configuration, and habitat composition. Only the input/host adapter differs.
5. Diagnostics are observational only. They may read counters and elapsed wall time but must not change random-number consumption, steering decisions, simulation steps, or pause/rate semantics beyond unavoidable measurement overhead.
6. Pause stops simulation scheduling and rendering. Resume resets frame timing before continuing so no paused duration enters the simulation delta.
7. All runtime assets and dependencies remain local. No telemetry, analytics, fetch to external origins, CDN, account, or cloud behavior is introduced.

## Module structure

```text
habitat/
  index.html
  habitat.js
  core/
    engine.js
    behavior.js
    fish.js
    environment.js
  habitats/
    planted-tank/
      config.js
      scene.js
  shaders/
    water-background.js
  vendor/
    three/
```

Empty abstractions are avoided. Each module exists because it owns a distinct responsibility.

### `habitat.js`

This is the thin entry point. It detects the existing WebView2 bridge or selects the browser-preview adapter, creates Planted Tank, and starts the engine. WebView2 messages and browser pointer events are normalized into the same plain input state. Preview-only keyboard controls toggle pause and diagnostics without creating a second runtime path.

### `core/engine.js`

The engine owns the Three.js renderer, stable camera, animation scheduling, fixed-step accumulator, viewport changes, pause/rate state, input adapter, readiness notification, and diagnostics collection.

The simulation uses a 60 Hz fixed step. Render cadence follows the bridge rate hint up to 60 FPS. A frame may run several bounded simulation steps to catch up, but the accumulator and per-frame delta are capped so stalls cannot create a spiral or teleport fish. Pause or rate zero cancels the pending animation frame. Resume clears accumulated time and establishes a fresh timestamp before scheduling again.

The engine calls the habitat in one direction:

1. update plain input state;
2. advance authoritative simulation state by fixed steps;
3. ask renderers to project the latest simulation state;
4. render the scene;
5. sample observational diagnostics.

### `core/behavior.js`

This module contains the deterministic simulation model and no rendering code. It exposes configuration validation, seeded pseudo-random variation, school creation, and one bounded simulation step.

Each fish state includes:

- position and velocity in three dimensions;
- preferred and maximum speed;
- turn responsiveness and maximum steering acceleration;
- visual scale and preferred depth;
- cohesion, alignment, and separation weights;
- neighbor and separation radii;
- cursor notice, curiosity, and threat radii plus response strength;
- boundary margin and recovery strength;
- personality seed, phase offsets, and subtle schooling/curious/cautious tendencies;
- transient cursor awareness/recovery state.

At the configured maximum of 12 fish, a direct bounded pair loop performs at most 132 directed neighbor comparisons per step. This is clearer and cheaper than introducing a spatial index for the MVP population. Reusable scratch vectors and result fields prevent per-frame object churn.

Steering combines:

- alignment toward nearby average velocity;
- cohesion toward the local neighbor center;
- strong short-range separation;
- low-frequency seeded wander;
- soft X/Y/depth boundary steering;
- return toward preferred depth;
- personality-weighted cursor awareness, curiosity, and close-range avoidance.

The sum is acceleration-clamped, velocity is smoothly steered and speed-clamped, and small damping prevents accumulated instability. Boundaries apply anticipatory forces rather than hard bounces except as a final safety clamp. This avoids synchronized splines, twitching, continuous collision, and unpredictable disappearance.

Personality is continuous rather than a game-visible class. Schooling tendency increases alignment/cohesion, curiosity allows a mild approach from outside the threat radius, and caution expands notice/threat distance and strengthens avoidance. Seeded values remain reproducible for tests and debugging.

### `core/fish.js`

This module owns procedural fish visualization only. It creates shared geometry and a small set of `THREE.InstancedMesh` objects for body, tail, eyes, and fins. Per-instance colors provide restrained variation without material proliferation.

On each render projection it reads simulation position, velocity, scale, and seed-derived visual phase. It writes instance matrices that express heading, pitch/depth, mild banking, body motion, and independent tail oscillation. Visual animation may derive phase from simulation time and speed but must not mutate simulation state.

The initial target is approximately four fish draw calls, independent of population count. Future geometry or materials can replace this renderer while retaining the same simulation state contract.

### `core/environment.js`

Environment helpers construct visual-only procedural elements: a restrained gradient water background, substrate suggestion, a bounded particle field, instanced plant silhouettes, and soft hemisphere/directional lighting. A small local shader may add slow, low-contrast light movement. Particle and plant counts are fixed by configuration and allocate nothing during steady-state rendering.

### `habitats/planted-tank/config.js`

The habitat configuration is the single source for population count, seed, world bounds, depth range, fish behavior ranges, colors, plants, particles, lighting, and diagnostic defaults. The initial population is 10 and validation enforces the sprint range of 8–12.

### `habitats/planted-tank/scene.js`

This composition module creates the scene, stable perspective camera, environment, authoritative school state, and fish renderer. It converts normalized pointer coordinates to one stable world interaction plane before passing plain coordinates to behavior. It advances behavior, then projects state into fish instances and environment visuals. It exposes lifecycle methods used by the engine but contains no Windows-specific knowledge.

## Cursor behavior

Pointer presence is explicit; pointer-out immediately ends new cursor influence and existing awareness decays naturally.

- Distant pointer: ignored.
- Notice range: personality and facing influence whether an individual becomes aware.
- Curious range outside the threat radius: curious fish may turn mildly toward the pointer without locking onto it.
- Threat range: fish steer and accelerate away, with response strength increasing smoothly as distance closes.
- Recovery: awareness and extra speed decay over time, returning fish to schooling rather than snapping back.

Seeded thresholds and response delays prevent the entire school from reacting on one frame. Cursor motion never directly sets velocity or position, so it cannot act like a game controller.

## Camera and depth

Planted Tank uses a fixed, low-distortion perspective camera. Fish remain within a narrow configured Z interval and have preferred depths. Perspective, fog, lighting, modest scale variation, overlap, and particle layers establish depth without a movable camera. Safety clamps keep fish visible. Cursor interaction uses a stable plane near the school center so screen-to-world mapping remains predictable.

## Diagnostics

The engine maintains small counters for rendered FPS, average frame time, fish count, pointer messages, and pause state. After a render it reads `renderer.info.render.calls` and `renderer.info.render.triangles`. Production reports a compact message through the existing WebView2 channel at a low interval. Browser preview can show the same snapshot in a small overlay when `?diagnostics=1` is present or a preview key toggles it.

Diagnostics do not consume simulation randomness, alter accumulator state, insert simulation steps, or change steering. They are disabled visually by default and never leave the machine.

## Browser preview

From `habitat/`, a developer may run:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

Opening `http://127.0.0.1:8000/` loads the same `index.html`, entry point, engine, Planted Tank modules, bundled Three.js files, and shaders as production. Browser pointer move/leave supplies normalized pointer input. Space toggles pause/resume; `D` toggles diagnostics. The preview performs no external request and Python serves static files only.

## Testing

Pure modules are tested with Node 24's built-in test runner and assertion library; no package installation or package manager is introduced. Tests cover:

- deterministic seeded school/personality creation;
- population/configuration validation;
- speed and steering acceleration bounds;
- close-range separation;
- cohesion/alignment influence;
- curious versus cautious cursor response and pointer-out recovery;
- soft boundary/depth recovery;
- pause/resume clock reset and bounded catch-up through exported timing policy helpers.

Rendering receives structural smoke coverage through the ordinary browser preview and the actual WebView2 host. Tests do not assert pixels.

Existing native fish logic, host policy, and WebView2 runtime probes continue to build with `/W4 /WX` and pass unchanged.

## Performance discipline

The runtime uses shared geometries/materials, instanced fish and plants, one bounded particle system, inexpensive shaders, fixed population limits, reusable scratch data, and no steady-state per-fish allocation. The first target is to keep draw calls near the feasibility scene rather than multiplying them by fish count.

Final measurements use the same Windows machine and record habitat FPS, frame time, calls, triangles, fish count, process-tree working set/private bytes, normalized CPU, attributed GPU samples, TCP connections, and continuous duration. The feasibility observations—38–43 FPS, 9 calls, about 504 MB working set, 5.5% normalized CPU, and 26–44% GPU—are comparison data, not promises. A material sustained regression is investigated and explained before the branch is considered ready.

## Validation and evidence

Local validation proceeds from pure tests to browser preview to the actual Windows host. The final Windows smoke verifies desktop composition, Explorer icon and blank-area ownership, visible non-synchronized schooling, believable cursor reaction/recovery, true pause/resume, Win+D, one Explorer restart, clean orphan-free quit, and absence of Aquarium-owned TCP connections.

Evidence consists of focused screenshots and a diagnostic run log without replacing historical feasibility evidence. Results distinguish observed behavior from architectural inference.

## Non-goals

This sprint does not add additional habitats, koi, imported/downloaded models or textures, feeding, sound, settings or tray redesign, habitat selection, installer/signing/update/autostart, multi-monitor behavior, power/session policies, accounts, cloud services, analytics, achievements, currency, or other product systems. It does not merge to `main` or alter `feasibility-v1` or historical spike branches.
