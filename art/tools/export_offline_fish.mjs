// Read-only export of the production Hero Fish for the offline art review.
import fs from 'node:fs';
import * as THREE from '../../habitat/vendor/three/three.module.js';
import { createHeroFishRenderer } from '../../habitat/core/hero-fish.js';
const out = new URL('../work/lush-reference/', import.meta.url);
fs.mkdirSync(out, { recursive: true });
const hero = createHeroFishRenderer(new THREE.Scene(), { capacity: 1 });
const data = {};
for (const [name, mesh] of Object.entries(hero.meshes)) {
  const g = mesh.geometry;
  data[name] = {
    position: [...g.attributes.position.array], uv: [...g.attributes.uv.array],
    part: [...g.attributes.aPart.array], surface: [...g.attributes.aSurface.array],
    index: [...g.index.array],
    texture: { width: mesh.material.map.image.width, height: mesh.material.map.image.height,
      pixels: [...mesh.material.map.image.data] },
  };
}
fs.writeFileSync(new URL('hero-fish.json', out), JSON.stringify(data));
hero.dispose();
