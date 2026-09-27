# Center substrate and freshwater atmosphere review

Baseline: `0b531e1`, `geometry-dusk-1920.png` (preserved).
Candidate: `geometry-water-atmosphere-1920.png`, 1920 × 1080.
Comparison: `geometry-water-before-after.png` (baseline left, candidate right).

## Changes

- Three broad, shallow terrain changes in the open foreground; they fade out before the wood. Existing planting bases retain their buried root margin.
- Existing gravel is redistributed deterministically into quieter fine areas and slightly denser patches. The substrate mesh and stone counts stay constant. Slight tonal variation remains within the existing beige/brown palette.
- Camera-distance attenuation reduces contrast slightly on distant surfaces. Foreground leaves and fish remain clear. Lamp positions, powers, colors and exposure are unchanged.
- 22 tiny suspended particles, with slow offline position keys; very weak broad material light modulation has a slow time driver. No volume simulation, bloom, waterline or beams.

## Visual assessment

The central swimming space is preserved. The foreground clearing has less uniform grain distribution, without an obvious path, hard boundary or decorative stone pattern. Rear foliage is mildly integrated into the water color. Individual particles and light variation remain secondary at desktop size; fish colors are readable.

These are restrained changes to the accepted scene. The still demonstrates spatial appearance only: particle drift and light modulation have not been visually validated in motion. Human visual approval remains pending.

## Verification

Blender 5.2.2 / Cycles completed the full 1920 × 1080 render successfully. Python compilation and `git diff --check` passed. A saved-scene audit compared the baseline and final locked mesh coordinates, transforms, camera, lamps and exposure with zero differences; see `water-pass-checks.json`.

The substrate keeps its existing geometry count; particles add 440 triangles. No runtime integration or performance claims were made.

## Source files

- `art/tools/render_lush_reference.py`: opt-in offline pass and separate output filename.
- `art/tools/lush_water_pass.py`: deterministic substrate treatment and inexpensive water material/particle treatment.
- `art/tools/audit_lush_locked_scene.py`: saved-scene comparison manifest for locked geometry, transforms, camera, lights and exposure.

## Reproduce

From the repository root, with the existing fish export in `art/work/lush-reference/hero-fish.json`:

```powershell
$env:LUSH_DUSK='1'
$env:LUSH_GEOMETRY_PASS='1'
$env:LUSH_WATER_PASS='1'
Remove-Item Env:LUSH_PREVIEW -ErrorAction SilentlyContinue
& 'C:\dev\tools\blender-5.2.2-windows-x64\blender.exe' -b --factory-startup -P art/tools/render_lush_reference.py
python art/tools/compare_lush_dusk.py --left geometry-dusk-1920.png --right geometry-water-atmosphere-1920.png --left-label 'APPROVED GEOMETRY BASELINE' --right-label 'NATURALIZED GROUND + WATER' --out geometry-water-before-after.png
```

Stop here for visual review. No merge and no runtime integration.
