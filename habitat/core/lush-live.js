import * as THREE from '../vendor/three/three.module.js';
import { applyWater, createWaterVolume, DEFAULT_WATER_MODE } from '../shaders/water-volume.js';
import { LUSH_LIVE_LIGHTS, createLushLiveLights, createRearMaterial, recoverMaterials } from './lush-live-look.js';

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
  scatterColor: [0.08, 0.215, 0.31],
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
      // Real rear geometry with its own unlit freshwater-depth material.
      replaced.push(object.material);
      object.material = createRearMaterial(object.geometry);
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
  // Material recovery toward the approved source intent (per-family
  // instances; lush-live-look.js), before the water model wraps them.
  const leafLight = { direction: { value: new THREE.Vector3() }, color: { value: new THREE.Color() } };
  const recovered = recoverMaterials(root, { leafLight });
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
  const { key: lamp, lights } = createLushLiveLights();
  scene.add(...lights);
  // Leaf transmission follows the key lamp: its direction and its irradiance
  // at the middle of the planting (inverse square), in three's Lambert units.
  const plantCentre = new THREE.Vector3(0, 2.2, -0.8);
  leafLight.direction.value.copy(lamp.position).sub(plantCentre).normalize();
  leafLight.color.value.copy(lamp.color)
    .multiplyScalar(lamp.intensity / lamp.position.distanceToSquared(plantCentre) / Math.PI);

  return {
    referenceCamera,
    mapFish: mapLushLiveFish,
    fishPalette: 'freshwater-approved',
    water,
    // Output transform after the approved source (AgX), see lush-live-look.js.
    toneMapping: LUSH_LIVE_LIGHTS.toneMapping,
    exposure: LUSH_LIVE_LIGHTS.exposure,
    fishScale: LUSH_LIVE_FISH_SCALE,
    updateVisuals() {},
    dispose() {
      scene.remove(root, ...lights);
      const geometries = new Set();
      const materials = new Set([...replaced, ...recovered]);
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
