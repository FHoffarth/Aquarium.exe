# Hero Fish Visual Pass 1 (reference-informed)

Branch `claude/hero-fish`, based on `c15957e` (North-Star Slice A). This branch is not merged to `main`.
Recommendation: **READY FOR WINDOWS VISUAL REVIEW**.

## What changed

The production fish is five stretched primitives: a sphere body, a flattened
sphere "accent band", 3-sided cone fins and tail, and sphere eyes. That is why
it reads as a sausage or a USB stick. This pass adds one hero-quality small
tetra/rasbora-type fish behind a review switch, built so the same renderer can
later draw a whole school.

The production path is untouched. The hero only appears with `?heroFish=1`.

| URL parameter | Effect |
|---|---|
| `heroFish=1` | Renders one simulated fish (school index 2) with the hero renderer. The whole school still simulates. |
| `heroVariant=production` | Draws the same single fish with the production renderer (A/B). |
| `heroScale=0.25..4` | Scale multiplier (default 1.8; `1` is true production size). |
| `heroStudio=1` | Review-only stand-in with a fixed position (`heroAt=x,y,z`), heading (`heroYaw=deg`) and gait (`heroGait=cruise\|hover\|turn\|escape\|auto`). The simulated fish is only copied, never written to. |

## Architecture

```
simulation (behavior.js, authoritative, unchanged)
   └─ fish state (read only)
        └─ createSwimAnimator(): render-side state per fish
             smoothed yaw/pitch, integrated swim phase, amplitude,
             turn curvature (from yaw rate), brake (from deceleration),
             hover effort (from low speed), escape (from cursorBoost)
             └─ per-instance attributes
                  aSwim vec4 = (phase, amplitude, curvature, brake)
                  aFin  vec2 = (fin phase, hover effort)
                  instanceMatrix = position, upright orientation, scale
                  └─ GPU vertex deformation (onBeforeCompile)
```

- Two `InstancedMesh` objects share the same per-instance buffers:
  - bodies: body plus eyes, one `MeshPhysicalMaterial`;
  - membranes: all fins, one transparent double-sided `MeshStandardMaterial`.
- The capacity is a constructor argument. The hero uses 1. A school uses N with the same draw calls.
- Orientation is built from an upright basis (forward, world-up, side), plus a small bank.
- This fixes a production bug (not changed on this branch): `rotation.set(bank, pitch, atan2(vy, vx))` rolls every left-swimming fish upside down.
- Reversals turn through facing the viewer, and yaw rate is limited, so turns are visible instead of flipping instantly.

## Geometry (`habitat/core/hero-fish.js`)

- **Body**
  - Stations along the standard length. Each station has 5 channels: dorsal depth, ventral depth, half-width, and separate dorsal and ventral superellipse fullness. The stations are Catmull-Rom interpolated.
  - Ring density is concentrated at the snout, operculum and caudal peduncle (inverse-CDF sampling). Columns are concentrated at the dorsal and ventral silhouette.
  - 57 rings × 28 segments, with welded normals at the belly seam.
- **Head anatomy is shaped into the mesh:**
  - a slightly upturned terminal mouth with a cleft groove;
  - an orbit socket;
  - a subtle operculum lip bowed along the gill-cover edge.
- **Profile:** a deep trunk just behind the head, a thin peduncle (below 35% of the trunk depth), then a flare into the caudal base.
- **Eyes:** a flattened spherical cap seated in the socket. Its UVs map to the head skin, so the rim blends into the head.
- **Fins are ray fans between an insertion line on the body and a free edge.** There are 8 membranes:
  - forked caudal;
  - dorsal (swept back);
  - adipose;
  - long anal;
  - paired pelvics;
  - paired pectorals.
- **Per-vertex attributes:** `aPart` (part id), `aProgress` (0 at insertion to 1 at the edge), `aSurface` (dorsal-ventral position, or eye radius).
- **Size:** body+eyes 1,993 vertices and 3,712 triangles; fins 369 vertices and 542 triangles.

## Shader

- **Spine bending (vertex):**
  - The lateral spine angle is `θ(s) = wave + turn + recoil`.
  - The wave is a travelling wave `A·env(s)·sin(phase − 5.3 s)`. Its envelope is near zero at the head and grows to the tail.
  - The turn term is a C-bend: curvature × (s − pivot), damped ahead of the pivot.
  - The recoil term is a small head counter-motion.
  - The spine position is integrated from the pivot (6 steps), so the body bends without stretching.
  - The cross-section is placed perpendicular to the bent spine, and normals are rotated to match.
- **Fin motion:**
  - The caudal membrane lags the body wave.
  - The pectorals beat with the fin phase, scaled by hover effort. During braking they flare outward and forward.
  - The pelvics flutter lightly.
  - The dorsal and anal fins ripple passively.
- **Skin:**
  - `MeshPhysicalMaterial` with a small fish-only prefiltered environment (lamp above, teal water, dark substrate; 64 px PMREM). This gives real wet speculars without touching the scene lights.
  - Clearcoat and restrained iridescence (IOR 1.33, 240–520 nm), driven by a mask texture.
  - Mask-driven roughness and metalness: guanine silvering on the flank, less on the back.
- **Colour** (procedural `DataTexture`, sRGB, mipmapped so micro detail fades with distance):
  - silver/pearl flank;
  - dark olive dorsum;
  - warm pale belly;
  - a restrained teal band;
  - faint operculum tone;
  - a warm blush at the peduncle;
  - an irregular scale reticulation;
  - a mouth line.
- **Thin-tissue backlight:** an albedo-scaled rim plus warm transmission at the thin peduncle and belly edge. It is not emissive.
- **Fins:**
  - warm red-orange at the base and leading rays, clearing toward a transparent edge;
  - ray striations;
  - albedo-scaled translucency glow;
  - no depth write, drawn after the body.
- **Eye:**
  - dark pupil;
  - bronze iris with metallic (silvered) reflectance;
  - clearcoat cornea for a wet corneal highlight.
- **Caustics and depth haze:** reused from the Slice A shared effect uniforms. To allow that, `material-effects.js` now exports `injectMaterialEffects`; existing materials behave the same.

## Reference study and licensing

Reference: `chaseleantj/desktop-habitats` at `66e80ea1b6bafd25324c84c72067e750c1a1f334`, files `scenes/riverscape/src/fish-anatomy.js` and `scenes/riverscape/src/fish.js`. License: MIT, © 2026 Chase Lean.

The files were downloaded to a scratch folder outside the repository for reading only.

1. **Concepts studied:**
   - anatomy from stations with separate dorsal, ventral, width and fullness channels;
   - mesh density concentrated at silhouette-critical regions;
   - head cues (orbit, opercle, mouth cleft);
   - fins as ray fans with insertion lines;
   - separate opaque body and membrane meshes;
   - an instanced per-fish swim vector (wave phase, amplitude, turn curvature, pectoral brake) plus a fin phase, with per-vertex part and fin-progress ids;
   - a spine angle combining a tail-weighted travelling wave and turning curvature, with the spine integrated rather than sheared;
   - caudal lag;
   - pectoral beat plus brake;
   - wet skin with thin-tissue scatter and scale detail.
2. **Concepts independently reimplemented here:** all of the above, written from scratch in Aquarium.exe's own structure and conventions:
   - a different station table, channel set, density function and grid resolution;
   - a different spine formulation and constants (6-step integration from a pivot, with the C-bend damped ahead of the pivot);
   - a different attribute layout (`aSwim`, `aFin`, `aPart`, `aProgress`, `aSurface`);
   - different fin shapes;
   - a texture-based palette and masks instead of per-vertex skin colouring;
   - a physical material with a fish-only PMREM environment;
   - a render-side animator that derives curvature, brake and hover from Aquarium.exe's simulation.
3. **Was any code copied or adapted?** No.
4. **Files and attribution:** none required. No code or data from the reference is in this repository.
5. **Statement of independence:** the implementation in `habitat/core/hero-fish.js` and its tests were written independently. They use only the principles listed above. No source text, constants tables or shader code were copied or mechanically translated.

No third-party assets were added. All textures are generated procedurally at runtime.

## Evidence (`docs/evidence/hero-fish/`)

All images come from the local habitat served at 1920×1080 (Chromium/WebGL2, same Three.js build as the host). Studio poses use `heroStudio=1`; G uses the live simulation.

| View | File |
|---|---|
| A: side profile (hero / placeholder) | `a-side-profile.png`, `a-side-profile-placeholder.png` |
| B: 3/4 front | `b-three-quarter-front.png` |
| C: 3/4 rear | `c-three-quarter-rear.png` |
| D: turning C-bend (toward the viewer / quarter) | `d-turn-c-bend-toward.png`, `d-turn-c-bend-quarter.png` |
| E: dark open water | `e-dark-open-water.png` |
| F: crossing vegetation (hero / placeholder) | `f-crossing-vegetation.png`, `f-crossing-vegetation-placeholder.png` |
| G: normal desktop scale (heroScale=1, live simulation) | `g-desktop-scale-full.jpg`, `g-desktop-scale-crop.png` and `-placeholder` variants |
| H: close-up diagnostic | `h-close-up-diagnostic.png` |
| Motion states | `m-cruise-1/2.png`, `m-hover.png`, `m-escape-1/2.png`, turn = D |
| Before/after sheet | `comparison-placeholder-vs-hero.jpg` |

## Performance

**Renderer counters** (`?diagnostics=1`, fish-only audit mode, one fish):

| Variant | Draw calls | Triangles |
|---|---|---|
| Production, 10 fish | 5 | 6,400 |
| Production, 1 fish | 5 | 640 |
| Hero, 1 fish | 3 (body, membrane back and front passes) | 4,796 |

**Full Slice A scene:**

| Variant | Draw calls | Triangles |
|---|---|---|
| Baseline, 10 production fish | 13 | 69,582 |
| Hero mode, 1 hero fish | 11 | 67,978 |

**Real Windows host** (bin copy patched to hero mode, browser pane closed, 1920×1080, 32 s runs, mean of the last three metric windows):

| Variant | FPS |
|---|---|
| 1 hero fish | 58.8 |
| 1 production fish | 58.9 |
| Baseline, 10 production fish | 56.7 (one 51.7 window; noise) |

No measurable FPS impact.

**GPU:**
- There is no per-pass GPU timer in this build, so GPU impact is inferred.
- The vertex stage runs a 6-step spine loop for about 2.4k vertices.
- Fragment cost is one physical material with clearcoat and iridescence, over a screen area smaller than a production fish at the same scale.

**Memory (approximate):**
- textures: body 512×256 (~0.7 MB with mips), masks and fins 256×128 (~0.35 MB);
- fish environment: 64 px PMREM (~0.6 MB half-float);
- geometry: ~0.1 MB.

**Scaling note:** a full school of 10 hero fish would stay at 3 draw calls, but at ~48k triangles. Before replacing the production school, add a distance LOD, e.g. halve rings and segments for fish smaller than ~60 px.

## Tests

`tests/habitat/hero-fish.test.mjs` (9 tests) was added to `build.ps1`. It covers:
- anatomy proportions;
- finite, well-formed geometry attributes, part ids and triangle budget;
- instanced buffer capacity and shared per-instance attributes;
- no NaN in instance matrices or attributes;
- simulation state not mutated;
- production projection contract unchanged;
- the upright-orientation regression (the left-swimmer roll bug);
- C-bend, brake and hover derivation;
- shader injection anchors for body and membranes (including caustics/haze uniforms and eye optics);
- strict review config parsing with hero off by default;
- the studio stand-in not touching the simulated fish.

GPU shader compilation was verified in Chromium. There were no console errors in any review mode, in either `art=slice-a` or `art=procedural`. In procedural mode, ANGLE's D3D compiler logs a benign `X4122` constant-folding precision warning.

All habitat tests pass: `node --test tests/habitat/*.test.mjs` → 63/63.

## Known limitations

- **Review-only.** The production school still uses the placeholder renderer. Switching it over needs the LOD above and a Windows visual sign-off.
- **Side views hide the body wave.** The travelling wave is lateral, as in a real fish, so from a pure side view it shows mainly through the tail and fins. The C-bend reads best when a fish turns toward or away from the viewer.
- **Head-on the head reads rounded and pale** under the strong top light (`d-turn-c-bend-toward.png`).
- **Scale reticulation is visible as a regular net only at close-up review scale (4×).** At desktop scale it mips away.
- **Pectoral fins are subtle by design** (translucent) and barely visible at desktop scale.
- **Production orientation bug:** documented, not fixed here, per the brief (production renderer untouched).
- **FPS was measured on this machine's GPU (Intel UHD) only.**
