# Three.js vendoring note

- Package: `three`
- Version: `0.186.0`
- Source: official npm package (`https://registry.npmjs.org/three/-/three-0.186.0.tgz`)
- npm integrity: `sha512-cr/fIM2ddMSVbYVgkfD4jLJv7Fh/8ZTjvo+7gQeSVGUZHxpx9FDwoL5iC7hUz/LiRA8wMbqfnb90xKfm1/HHkQ==`
- Package SHA-256: `61EEFF9D7616005C9A481C796F52287D81FBBBC0D55EACA5565322924252C1AA`
- Included module SHA-256: `9052042D676CB0FDC1DDFEFE193053F34B7AC0513A616FDAC4535D49987812EA`
- Included core SHA-256: `9EDDE002B066A9A05676A6127F67735B62BAF399BDEA529F2F7E31657DA769E6`
- Included files: `build/three.module.js`, its required `build/three.core.js`, the package MIT license, and the three add-on files below

## Add-ons (glTF loading only)

Copied unmodified from `examples/jsm/` of the same verified tarball, keeping their
relative layout so their internal `../utils/` imports resolve. They import the bare
specifier `three`, which `index.html` maps to `./vendor/three/three.module.js`.

| Vendored path | Upstream path | SHA-256 |
|---|---|---|
| `addons/loaders/GLTFLoader.js` | `examples/jsm/loaders/GLTFLoader.js` | `131C0F78C01D19368AE495CAA65B3ADAA10487810A36A05BB5901B769A35AC16` |
| `addons/utils/BufferGeometryUtils.js` | `examples/jsm/utils/BufferGeometryUtils.js` | `9FB63427CE6641FA14FD0BAFF9CC4D1B5F9C3D85FD084BF2E90E803C44EC1797` |
| `addons/utils/SkeletonUtils.js` | `examples/jsm/utils/SkeletonUtils.js` | `B1632A703206C3D830DE9FCBE515696770D04B71A15EE6B50AFA6D2C3298C86F` |

No Draco, KTX2/Basis, or other WASM decoders are vendored.

Hashes are of the upstream (LF) bytes. A Windows checkout with `core.autocrlf=true`
shows CRLF working-copy files with different hashes; the committed blobs match upstream.

The module is loaded exclusively from the local habitat directory. No Three.js code or assets were copied from `desktop-habitats` or Lively.
