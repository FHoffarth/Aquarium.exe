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
- Included files: `build/three.module.js`, required `build/three.core.js`, and license
- License: MIT; see `habitat/vendor/three/LICENSE.txt`
- Vendoring details: `habitat/vendor/three/README.md`

No Three.js code beyond the unmodified vendored distribution, and no shader, model, texture, fish, or other asset was copied from `desktop-habitats` or Lively. The Habitat Runtime, deterministic behavior, procedural fish geometry, water shader, and Planted Tank environment in this repository are original Aquarium.exe code.
