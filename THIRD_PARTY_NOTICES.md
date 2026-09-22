# Third-party notices

## Microsoft WebView2 SDK

- Package: `Microsoft.Web.WebView2`
- Version: `1.0.3405.78`
- Source: official NuGet package
- Package SHA-256: `D035807B2AABA871E8C014759626F566E96934E6CE6F0587056EE81D5228C373`
- Included files: native C++ headers, x64 loader import library/DLL, license, and notice
- License: BSD-style Microsoft license; see `third_party/webview2/LICENSE.txt`
- Additional notices: `third_party/webview2/NOTICE.txt`

No WebView2 source was copied from Lively. Lively's pinned package version was used only as compatibility evidence for the installed runtime and native Windows environment.

## Three.js

- Package: `three`
- Version: `0.186.0`
- Source: official npm package
- Package SHA-256: `61EEFF9D7616005C9A481C796F52287D81FBBBC0D55EACA5565322924252C1AA`
- Included files: `build/three.module.js`, required `build/three.core.js`, the unmodified glTF loading add-ons `examples/jsm/loaders/GLTFLoader.js`, `examples/jsm/utils/BufferGeometryUtils.js` and `examples/jsm/utils/SkeletonUtils.js`, and license
- License: MIT; see `habitat/vendor/three/LICENSE.txt`
- Vendoring details and per-file SHA-256: `habitat/vendor/three/README.md`

No Three.js code beyond the unmodified vendored distribution, and no shader, model, texture, fish, or other asset was copied from `desktop-habitats` or Lively. The Habitat Runtime, deterministic behavior, procedural fish geometry, water shader, and Planted Tank environment in this repository are original Aquarium.exe code.

## Planted Tank art assets (Slice A)

Every shipped file under `habitat/assets/` is derived from the CC0 sources below and
modified by Aquarium.exe's own pipeline (`art/tools/`). CC0 requires no attribution;
it is recorded here for provenance and gratitude. The per-file manifest with SHA-256
hashes, modifications, and original filenames is `habitat/assets/manifest.json`;
acquisition records are in `art/provenance/polyhaven/`; archived license evidence is
in `art/licenses/`.

- Source: Poly Haven (<https://polyhaven.com>), license CC0 1.0 (<https://polyhaven.com/license>)

| Source asset | Creators | Source page | Used for |
|---|---|---|---|
| Dry Branches Medium 01 | Rico Cilliers | <https://polyhaven.com/a/dry_branches_medium_01> | driftwood (re-posed, thickened, re-graded) |
| Rock Moss Set 02 | Kless Gyzen | <https://polyhaven.com/a/rock_moss_set_02> | rocks and pebbles |
| Moss 01 | Rob Tuytel | <https://polyhaven.com/a/moss_01> | moss sprigs on hardscape |
| Anthurium Botany 01 | Rob Tuytel (scanning), Rico Cilliers (modeling) | <https://polyhaven.com/a/anthurium_botany_01> | broad-leaf aquarium vegetation (visually transformed) |
| Fern 02 | Rob Tuytel (scanning), Rico Cilliers (modeling) | <https://polyhaven.com/a/fern_02> | fern vegetation (visually transformed) |
| Shrub Sorrel 01 | Rico Cilliers | <https://polyhaven.com/a/shrub_sorrel_01> | carpet vegetation cards (flowers removed) |
| Nettle Plant | Rob Tuytel (photography), Rico Cilliers (modeling) | <https://polyhaven.com/a/nettle_plant> | background stem vegetation cards |
| Gravelly Sand | Dario Barresi | <https://polyhaven.com/a/gravelly_sand> | substrate (blended, baked) |
| Coast Sand 03 | Rob Tuytel | <https://polyhaven.com/a/coast_sand_03> | substrate coarse grit (blended, baked) |

Source asset names above are provenance only. Aquarium.exe vegetation is visually
transformed source material and makes no claim to depict any particular real species.
