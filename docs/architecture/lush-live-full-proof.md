# Full-frame live 3D composition proof (`?art=lush-live`)

Recovery step after the narrow vertical slice (`d7c7320`) proved the pipeline but failed visually.

## Diagnosis

- **The slice exporter caused the visual failure.** It kept only plant pieces with |X| < 3.3 and floor faces inside that band. It also dropped the boulder, both rock-07 pieces and five of the eight wood pieces.
- **What that produced:** a cropped floor island, two isolated plant towers, an empty centre and single ribbon leaves dominating the frame.
- **Live 3D itself did not fail.**
- **Mis-labelled evidence:** the uncommitted runtime proof's evidence image (`docs/evidence/lush-live-slice-runtime/overall-desktop.png`) was a screenshot of the Codex app, not of the wallpaper. It was removed.

## Change

- **`art/tools/export_lush_live_full.py`:** exports the complete approved environment from the SHA-pinned `lush-water-reference.blend` (`a43f49fb…`, unchanged):
  - all seven plant groups and supporting stems;
  - the full gravel bed and embedded gravel;
  - all wood pieces with their bevel modifiers applied as in the offline render;
  - rock-07 ×2, the boulder and rock-09;
  - the real rear boundary and the approved camera.

  There is no X window, decimation or repositioning. Material mapping is reused from the slice exporter, with the rock-07 and boulder albedos added. Output: `habitat/assets/lush-live/environment.glb`.
- **`habitat/core/lush-live.js`:**
  - mounts the scene graph at the approved camera (48 mm, vertical FOV 23.82°, from the GLB);
  - gives the real rear geometry a restrained deep blue-green vertical gradient (unlit, no cyan);
  - adds a spatial light hierarchy: an aquarium lamp above the front glass with inverse-square falloff (the rear plants receive about half the foreground light), a hemisphere fill with a light ground colour so leaf back faces don't go black, and a weak warm side lamp;
  - sets a neutral exposure for this mode;
  - provides a render-side fish-to-tank transform and scale, so fish swim in front of, between and behind the plant layers.
- **No water treatment:** no fog, haze, extinction, particles, caustics, shafts, bloom or post-processing.
- **Runtime wiring:**
  - `scene.js` takes the camera, exposure, fish mapping and fish scale from the environment;
  - `assets.js` exposes glTF scene graphs (carried over from the uncommitted runtime proof);
  - art modes are unchanged: the default is still `lush`, and the proof is selected with `?art=lush-live`.

## Geometry

| | Slice (`d7c7320`) | **Full proof** |
|---|---:|---:|
| Source objects | 16 (cropped) | 24 (complete) |
| Triangles | 95,552 | **344,511** |
| Primitives / materials | 57 / 28 | **79 / 32** |
| GLB | 4.66 MB | 16.2 MB |
| Embedded textures (RGBA8 + mips) | ~12 MiB | 38.7 MiB (rock-07 2K albedo is the largest) |

## Real host (1920×1080, Intel UHD, `bin` copy patched to `lush-live`)

| | `lush-live` | `lush` plate (current default) |
|---|---|---|
| FPS, target 60 (10 × 5 s windows after 20 s warm-up) | 59.4 mean (58.8–60.0) | 60.0 |
| Steady state during the capture (after the brightness correction) | 60.0, frame time 16.67 ms | – |
| Draw calls | 82 | 5 |
| Rendered triangles | 392,471 | 47,962 |
| GPU (Aquarium processes, 5 × 1 s) | 72.9% | 57.8% |
| Asset load | 250 ms, 16.2 MB | 111 ms, 2.2 MB |

Nothing was optimised. The obvious later levers are material consolidation (79 primitives), vegetation LOD for `03 fine feather plants` (155k triangles) and alpha-cutout tuning.

## Evidence (`docs/evidence/lush-live-full/`)

- `real-desktop-31s.mp4`: the clean 31 s segment of a 45 s real-desktop recording. The removed part had the Claude window in front.
- `1-real-desktop-full-frame.png`
- `2-fish-in-front-of-plants-crop.png`
- `3-fish-behind-plants-crop.png`: genuine depth-buffer occlusion.
- `4-same-scene-headless-no-icons.png`
- `5-comparison-6dfd62d-vs-live.jpg`

## Assessment

- **Spatial gate: passes.** With every water effect off, the scene reads as a 3D planted aquarium:
  - a full floor to the frame edges and the wood anchor in the centre;
  - vegetation layered front, middle and back across the whole width;
  - a rear that recedes;
  - fish that swim in front of, between and behind plants.
- **Still wrong or weaker than 6dfd62d:**
  - The overall image is darker and greener than the approved bright tank. The sand is grey-beige instead of pale, and the rear is dark neutral rather than water.
  - Materials are simplified glTF PBR (no procedural leaf variation, bump or transmission), so large leaves look flat and a few back faces stay dark.
  - Fish are neutral silver rather than the approved red-accent school.
  - The GPU cost is about 15 points above the plate.

  These are lighting/material calibration and optimisation items. They are not composition problems.
