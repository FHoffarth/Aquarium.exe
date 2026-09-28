import * as THREE from '../vendor/three/three.module.js';
import { applyWater, createWaterVolume, DEFAULT_WATER_MODE } from '../shaders/water-volume.js';

// Full-frame live 3D composition proof (?art=lush-live).
//
// The complete approved Blender aquarium (6dfd62d, SHA-pinned .blend) as real
// geometry at the approved camera: every plant group, the full gravel floor,
// all wood and stones, and the real rear boundary. Fish swim inside it and are
// occluded by the GPU depth buffer.
//
// Water: a finite water volume seen from outside the front glass
// (shaders/water-volume.js). Every environment material, the rear boundary
// and the fish get per-fragment RGB extinction over the glass-to-fragment
// water path plus restrained in-scattering. No fog, particles, caustics,
// shafts, bloom or post-processing. ?water=off|extinction|full compares.

const ASSET = 'lush-live/environment.glb';
const REAR_MATERIAL = 'clear blue depth';
// Rear boundary: restrained, desaturated freshwater blue-green (sRGB), a
// little lighter near the water surface, darker toward the floor.
const REAR_TOP = new THREE.Color('#4a7a7e');
const REAR_BOTTOM = new THREE.Color('#21454a');
// Hero Fish at a size matching the approved offline tank (~0.65 units long
// here; the school simulation keeps its own units).
export const LUSH_LIVE_FISH_SCALE = 1.25;

// Render-side calibration only: the simulation stays authoritative in its
// [-3,3] x [-1.45,1.45] x [-0.65,0.65] volume. The tank floor is at y ~0.1,
// foreground plants at Three z ~ +0.1..+2.7, the middle bushes ~ -2.3..+0.6
// and the rear feather plants ~ -4.2..-2.3. The mapping spreads the school
// over x +-4.7, y ~0.8..4.3 and z ~ -2.8..+1.8, so fish swim in front of,
// between and behind real plant layers.
// Clear planted freshwater (per scene unit of water path). Red is lost
// fastest, blue least. Viewed relative to the near planting (white balance
// at 3.5 units of water, just in front of the foreground plants, see
// water-volume.js): the foreground stays ~0.9, the middle bushes ~0.7-0.87,
// the rear feather plants ~0.5-0.75 and the rear boundary ~0.37-0.64; lost
// light is replaced by the water column's own in-scattered colour.
// Measured per object by art/tools/water_depth_report.mjs.
export const LUSH_LIVE_WATER = Object.freeze({
  glassZ: 5,                           // front glass plane, Three Z (export metadata)
  sigma: [0.13, 0.08, 0.058],
  referenceDistance: 3.5,
  // Linear radiance of the lit water column (before tone mapping), at the
  // scene's own brightness level: restrained blue-green, weaker toward the floor.
  scatterColor: [0.058, 0.112, 0.118],
  scatterStrength: 1,
  surfaceY: 7.2,
  floorY: 0.1,
  depthLight: 0.5,
});

export function mapLushLiveFish(fish) {
  return {
    ...fish,
    position: {
      x: fish.position.x * 1.55,
      y: 2.55 + fish.position.y * 1.2,
      z: -0.5 + fish.position.z * 3.6,
    },
    velocity: {
      x: fish.velocity.x * 1.55,
      y: fish.velocity.y * 1.2,
      z: fish.velocity.z * 3.6,
    },
  };
}

export function createLushLiveEnvironment(scene, assets, { waterMode = DEFAULT_WATER_MODE } = {}) {
  const water = createWaterVolume({ ...LUSH_LIVE_WATER, mode: waterMode });
  // Shared materials are wrapped once each.
  const watered = new Set();
  if (!scene?.isScene) throw new TypeError('scene must be a Three.js Scene');
  const root = assets.sceneGraphs?.[ASSET];
  if (!root) throw new Error(`${ASSET}: GLB scene graph missing`);

  let referenceCamera = null;
  let meshCount = 0;
  const replaced = [];
  root.traverse(object => {
    if (object.isPerspectiveCamera) referenceCamera = object;
    if (!object.isMesh) return;
    meshCount += 1;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    if (materials.some(material => material.name === REAR_MATERIAL)) {
      // Real rear geometry with its own restrained, unlit gradient material.
      const geometry = object.geometry;
      const position = geometry.getAttribute('position');
      geometry.computeBoundingBox();
      const { min, max } = geometry.boundingBox;
      const colors = new Float32Array(position.count * 3);
      const color = new THREE.Color();
      for (let index = 0; index < position.count; index += 1) {
        const t = (position.getY(index) - min.y) / Math.max(1e-6, max.y - min.y);
        color.copy(REAR_BOTTOM).lerp(REAR_TOP, t * t);
        color.toArray(colors, index * 3);
      }
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      replaced.push(object.material);
      object.material = new THREE.MeshBasicMaterial({ vertexColors: true });
      // Twelve large triangles: exact per-fragment water path.
      applyWater(object.material, water, { perFragment: true });
      watered.add(object.material);
      return;
    }
    for (const material of materials) {
      if (material.transparent || !material.depthTest || !material.depthWrite) {
        throw new Error(`${object.name}: live aquarium requires depth-tested, depth-writing material`);
      }
    }
  });
  if (!referenceCamera || meshCount < 10) {
    throw new Error(`${ASSET}: approved camera or spatial geometry missing`);
  }
  root.traverse(object => {
    if (!object.isMesh) return;
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      if (watered.has(material)) continue;
      watered.add(material);
      applyWater(material, water);
    }
  });
  scene.add(root);

  // Spatial light hierarchy (no shadows): the aquarium lamp above the front
  // half of the tank falls off toward the rear and the sides, so foreground
  // and middle carry more weight than the background; a modest cool fill
  // keeps shadows readable; a weak warm lamp from the upper right as in the
  // approved offline lighting.
  // The lamp sits above the front glass with inverse-square falloff: the
  // rear plants (about 1.4x farther away) receive roughly half the light of
  // the foreground. A light ground colour keeps leaf back faces from going
  // black (the offline render had leaf transmission).
  const hemisphere = new THREE.HemisphereLight(0xdcece6, 0x66755e, 1.15);
  const ambient = new THREE.AmbientLight(0xbfd3d2, 0.08);
  const lamp = new THREE.SpotLight(0xfff4e4, 300, 0, 1.0, 0.9, 2.0);
  lamp.position.set(-0.6, 9.5, 5.5);
  lamp.target.position.set(0.3, 0, -1.2);
  const side = new THREE.DirectionalLight(0xffe6c4, 0.3);
  side.position.set(6, 9, 4);
  const lights = [hemisphere, ambient, lamp, lamp.target, side];
  scene.add(...lights);

  return {
    referenceCamera,
    mapFish: mapLushLiveFish,
    fishPalette: 'freshwater-approved',
    water,
    // Neutral exposure for this proof (the global 1.42 was tuned for the
    // earlier dark slices).
    exposure: 1.4,
    fishScale: LUSH_LIVE_FISH_SCALE,
    updateVisuals() {},
    dispose() {
      scene.remove(root, ...lights);
      const geometries = new Set();
      const materials = new Set(replaced);
      const textures = new Set();
      root.traverse(object => {
        if (!object.isMesh) return;
        geometries.add(object.geometry);
        for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
          materials.add(material);
          if (material.map) textures.add(material.map);
        }
      });
      for (const geometry of geometries) geometry.dispose();
      for (const material of materials) material.dispose();
      for (const texture of textures) texture.dispose();
    },
  };
}
