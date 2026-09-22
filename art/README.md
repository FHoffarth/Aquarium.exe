# Aquarium.exe art pipeline

Source art never ships. Everything the runtime loads lives in `habitat/assets/`
(the only folder WebView2 maps to `https://aquarium.local/`) and is produced from
approved sources by the scripts here, reproducibly.

```
art/
  tools/          pipeline scripts (committed)
  provenance/     acquisition records + source info at acquisition time (committed)
  licenses/       archived license evidence (committed)
  source/         raw downloads (gitignored; re-fetch with fetch_sources.py)
  work/           intermediates: .blend, bakes, card renders (gitignored)
habitat/assets/
  manifest.json   every shipped file: SHA-256, GREEN status, sources, modifications
  slice-a/        environment.glb + WebP textures
```

## Tools

- Python 3 with Pillow and NumPy (dev tooling only; not a runtime dependency)
- Blender 5.2 LTS (dev tooling only), headless. Default path
  `C:\dev\tools\blender-5.2.2-windows-x64\blender.exe`; override with `BLENDER`.

## Rebuild Slice A

```
python art/tools/fetch_sources.py   # first time: downloads approved sources, verifies publisher MD5
python art/tools/build_all.py       # cards -> geometry + occlusion bakes -> textures -> manifest
node --test tests/habitat/*.mjs     # includes manifest integrity and asset budget tests
```

The build is deterministic: the same sources produce byte-identical `environment.glb`.

| Step | Script | Output |
|---|---|---|
| 1 | `render_cards.py` (Blender, Cycles) | carpet and stem card tiles rendered from the habitat camera angle; flower geometry removed |
| 2 | `build_slice_a.py` (Blender) | `environment.glb`: decimated rocks and pebbles, kitbashed driftwood, scattered moss, atlas-mapped plants, camera-facing cards, terrain; Cycles contact-occlusion bakes |
| 3 | `prepare_textures.py` | 1K PBR sets, 2K vegetation/card atlases, unique baked 2K substrate; WebP |
| 4 | `build_manifest.py` | `habitat/assets/manifest.json` |

The composition (rock, wood, plant and card placement) is hand-authored data at the top
of `build_slice_a.py`. The substrate grit mask in `prepare_textures.py` must track it.

## Asset policy

- GREEN only for shipping: our own work, CC0, or licenses explicitly permitting
  commercial use, modification and redistribution inside the app.
- REVIEW (explicit approval per asset): attribution licenses, marketplace licenses,
  commissioned work, generative-AI output.
- NO: ripped or unclear-provenance assets, "free download" without a real license,
  NC/ND licenses, anything from `desktop-habitats`, and the North-Star reference image.
- Nothing is downloaded before approval. Each shipped file must appear in the manifest
  with its SHA-256; the runtime verifies every file before use and falls back to the
  procedural habitat, reporting `habitat-asset-failure:`, if any check fails.
- Vegetation is visually transformed source material. Do not make species claims in
  product code, copy or metadata; source asset names are recorded only as provenance.

## Budgets (Slice A)

Enforced by `tests/habitat/asset-budget.test.mjs`: environment <= 90k triangles and
<= 8 primitives, rocks <= 20k, wood <= 8k, textures <= 2048 px per side, estimated GPU
texture memory <= 96 MiB (RGBA8 + mips).
