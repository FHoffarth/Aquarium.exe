# Three.js vendoring note

- Package: `three`
- Version: `0.186.0`
- Source: official npm package (`https://registry.npmjs.org/three/-/three-0.186.0.tgz`)
- npm integrity: `sha512-cr/fIM2ddMSVbYVgkfD4jLJv7Fh/8ZTjvo+7gQeSVGUZHxpx9FDwoL5iC7hUz/LiRA8wMbqfnb90xKfm1/HHkQ==`
- Package SHA-256: `61EEFF9D7616005C9A481C796F52287D81FBBBC0D55EACA5565322924252C1AA`
- Included module SHA-256: `9052042D676CB0FDC1DDFEFE193053F34B7AC0513A616FDAC4535D49987812EA`
- Included core SHA-256: `9EDDE002B066A9A05676A6127F67735B62BAF399BDEA529F2F7E31657DA769E6`
- Included files: `build/three.module.js`, its required `build/three.core.js`, and the package MIT license only

The module is loaded exclusively from the local habitat directory. No Three.js code or assets were copied from `desktop-habitats` or Lively.
