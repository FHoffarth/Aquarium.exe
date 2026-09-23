# Aquascape Hero Frame Pass 2: premium finish

Branch `claude/aquascape-hero-frame`, following Pass 1 (`169d702`). Composition B is kept unchanged in layout. Offline art pass only: no runtime integration, no scene/host/simulation changes, and the Hero Fish is untouched (Pass 1B, frozen). Not merged.

**AQUASCAPE HERO FRAME PASS 2: READY FOR VISUAL REVIEW**

## Evidence (`docs/evidence/aquascape-hero-frame-pass-2/`)

| | File |
|---|---|
| **Pass 2 hero frame, 1920×1080, no fish** | `hero-frame-pass-2-1920x1080.png` |
| Pass 1 vs Pass 2, directly comparable (same camera and size) | `comparison-pass-1-vs-pass-2.jpg` (top/bottom), plus `hero-frame-pass-1-1920x1080.png` |
| Optional: Pass 2 with the approved Hero Fish 1B at realistic desktop scale | `hero-frame-pass-2-with-hero-fish.png` |
| Pass 2 iteration history (half resolution) | `iterations-pass-2.jpg` |

## What changed, by review point

### 1. Planting: composed masses instead of distributions

The planting zones are unchanged and no plant types were added. Their internal composition was rebuilt.

- **Background stems:**
  - 11 intentional masses, each made of sub-clumps. Each sub-clump uses one plant character and has similar heights inside it, so clumps read as individual plants.
  - A strong height hierarchy follows the composition: tallest (≈2.9) behind the hardscape, falling through 2.1 and 1.35 toward the centre, with a deliberate low gap centre-right and a medium mass at the back right.
  - Leaves are slightly larger, so masses read as bushes rather than reed beds.
- **Ribbons:** the single isolated clump is now six clumps at different depths and heights (1.1–3.2), woven into the right-hand stem mass, plus two small clumps behind the hardscape.
- **Carpet:**
  - three-octave noise coverage for irregular edges, islands and tongues;
  - low-frequency mounding, so the cushion has height variation;
  - densest around the hardscape base, thinning to the right.
- **Hairgrass:** 12 composed clusters (peaked tufts), along the clearing edges and as a midground layer.
- **Small rosettes:** reduced to a few groups that break the clearing edges; the dark spiky singles are gone.

### 2. Hardscape: integrated, not replaced

- **Wood:** the diagonal gesture is kept. It now has three primary gestures: the hero sweep (thicker), the steep rise, and the low back-left arm. The fifth thin limb was removed.
  - Spines have a second, higher-frequency kink component, so limbs change direction like real wood instead of arcing like horns.
  - Deeper gnarl and grooves.
  - Tip forks only on the two main gestures; no needle tips (every tip keeps a minimum radius, so ends read as weathered, not as antlers).
  - Side growth is either short broken stubs or 1–2 real secondary branches.
- **Rocks:**
  - primaries are sunk deeper (36–38%);
  - seven secondary stones cluster around the primaries' bases, so the big rocks read as one outcrop rather than individual boulders.
- **Transitions:**
  - five extra broad-leaf masses sit exactly where wood meets stone and where stones meet the ground, hiding the contact lines;
  - moss stays concentrated on joints and the rock/wood contact.

### 3. Floor: less dominance

- The clearing is narrower, broken by noise into gaps where carpet tongues cross, and fades out before the back, so it no longer reads as a path through the image.
- Midground hairgrass and rosette clusters layer the floor, so the viewer looks across planting rather than across a floor.
- Open substrate remains as breathing room.

### 4. Lighting: the hero moment

- **New warm soft key** from the upper left (spot, 42°, fully blended edge, soft shadows), aimed at the wood/rock junction. It catches the wood, the rock tops and selected leaves, then falls off through the centre.
- **The overall top light is weaker and cooler** (energy 6.0 → 2.4, neutral-cool), so the frame is no longer evenly lit. The fill is reduced.
- **Shafts:** only three faint ones remain, all on the left in the key's direction.
- **Deeper right:** the grade adds a gentle darkening toward the right and the top. Global saturation is unchanged.

### 5. Back wall / horizon

- The Pass 1 back-glass line is gone. The substrate now continues far back and widens (x ±13, back to z −9.5), inside a long denser haze volume.
- Floor and water converge to the same teal before any edge is reached: no strip, and no place where the scene visibly ends.
- The dark background film sits behind the haze, at z −10.2.

**Tried and rejected on the way:** curving the substrate up into the back haze. It raised the horizon and enlarged the floor.

## Hero Fish scale frame

The fish geometry and its procedural textures were exported unchanged from the Pass 1B runtime module (`claude/hero-fish` `67d8814`, `buildHeroFishGeometry`, `shadeBody`, `shadeFin`) as a static pose. They are placed at desktop scale (`heroScale 0.75`), three fish in the open water heading toward the hardscape.

- **Offline materials only:** textured, semi-metallic body with a clearcoat, dark glossy eye, textured alpha fins.
- **No fish code or shader was modified.** The fish frame is judged after the environment frame, for scale only.

## Unchanged

The runtime, loaders, asset pipeline, host, simulation and Hero Fish code are all unchanged. The only files touched are `art/tools/compose_hero_frame.py`, `art/tools/grade_hero_frame.py`, this document and its evidence.

## Remaining weaknesses

- **Plants still carry a CG signature up close**, especially the stem-plant leaves and the carpet discs at 100% crop. At desktop viewing distance they read as masses.
- **The procedural wood's bark is less detailed than a scan.** The warm key makes this more visible on the hero sweep.
- **The far-left floor edge is quiet, empty gravel.** This is deliberate for the icon column, but it is the least designed area of the frame.
- **The runtime camera gives the substrate ~35% of the frame height.** Pass 2 reduces its visual dominance through planting and light, not through the camera.
