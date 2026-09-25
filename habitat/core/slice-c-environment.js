import * as THREE from '../vendor/three/three.module.js';
import {
  waterBackgroundSliceBFragmentShader,
  waterBackgroundVertexShader,
} from '../shaders/water-background.js';
import { applyMaterialEffects, createEffectUniforms } from '../shaders/material-effects.js';

// Slice C: the approved Natural Environment vocabulary in the runtime.
// Scanned rock family, the Composition B root with willow bark, LeafSet022
// broad-leaf clusters, and open dark water as intentional negative space (no
// moss, no background plant wall, no carpet). Geometry comes from
// art/tools/build_slice_c.py; this module assigns materials, light and water
// atmosphere. Purely visual: it reads no simulation state.
//
// Floor and horizon: the substrate falls away behind the hardscape (baked
// into the terrain) and its colour converges to the haze before that crest,
// the haze colour equals the backdrop at the projected crest, and the camera
// looks slightly upward so the floor takes less of the frame.

const CAUSTIC_COLOR = [0.62, 0.86, 0.8];
const BACKDROP = {
  top: 0x2a7880,
  bottom: 0x0b333b,
  glow: [0.1, 0.075, 0.045],
  // Plane at z -7.5 spanning y -5.7..6.3: the floor crest behind the
  // hardscape (z ~ -2.4, y ~ -1.2) projects onto it at v ~ 0.31.
  z: -7.5,
  centerY: 0.3,
  width: 26,
  height: 12,
  horizon: 0.31,
  calm: 0.5,
};
// Must match slice_c_layout.CAMERA_TARGET_Y.
export const SLICE_C_CAMERA_TARGET = Object.freeze([0, 0.24, 0]);
// One matte roughness for all stone: rock_07's source roughness is a uniform
// ~0.30, which glinted as white flecks under the key light.
const STONE_ROUGHNESS = 0.86;

function seededUnit(seed, index, channel) {
  let value = (seed ^ Math.imul(index + 1, 0x9e3779b1) ^ Math.imul(channel + 1, 0x85ebca77)) >>> 0;
  value ^= value >>> 16;
  value = Math.imul(value, 0x7feb352d);
  value ^= value >>> 15;
  value = Math.imul(value, 0x846ca68b);
  value ^= value >>> 16;
  return (value >>> 0) / 0x100000000;
}

function requireMesh(meshes, name) {
  const mesh = meshes[name];
  if (!mesh) throw new Error(`slice-c geometry is missing mesh "${name}"`);
  return mesh;
}

function requireTexture(textures, name) {
  const texture = textures[name];
  if (!texture) throw new Error(`slice-c is missing texture "${name}"`);
  return texture;
}

function renameAttribute(geometry, from, to) {
  const attribute = geometry.getAttribute(from);
  if (!attribute) return;
  geometry.setAttribute(to, attribute);
  geometry.deleteAttribute(from);
}

export function createSliceCEnvironment(scene, config, assets) {
  if (!scene?.isScene) throw new TypeError('scene must be a Three.js Scene');
  const { bounds, environment } = config;
  const { meshes, textures } = assets;
  const owned = [];
  const materials = [];
  const shared = createEffectUniforms();
  const add = object => {
    scene.add(object);
    owned.push(object);
    return object;
  };
  const material = parameters => {
    const created = new THREE.MeshStandardMaterial(parameters);
    materials.push(created);
    return created;
  };

  const top = new THREE.Color(BACKDROP.top);
  const bottom = new THREE.Color(BACKDROP.bottom);
  const backgroundMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uTop: { value: top },
      uBottom: { value: bottom },
      uGlow: { value: new THREE.Vector3(...BACKDROP.glow) },
      uHorizon: { value: BACKDROP.horizon },
      uCalm: { value: BACKDROP.calm },
    },
    vertexShader: waterBackgroundVertexShader,
    fragmentShader: waterBackgroundSliceBFragmentShader,
    depthWrite: false,
  });
  materials.push(backgroundMaterial);
  const background = add(new THREE.Mesh(new THREE.PlaneGeometry(BACKDROP.width, BACKDROP.height), backgroundMaterial));
  background.name = 'water-background';
  background.position.set(0, BACKDROP.centerY, BACKDROP.z);
  background.renderOrder = -10;

  // The haze converges on the backdrop's raw value at the projected floor
  // crest, so the substrate dissolves into water with no edge. The fish
  // volume (z >= -0.65) stays clear; the rear hardscape takes a little.
  const horizonT = BACKDROP.horizon * BACKDROP.horizon * (3 - 2 * BACKDROP.horizon);
  const haze = bottom.clone().lerp(top, horizonT);
  shared.uHazeColor.value = [haze.r, haze.g, haze.b];
  shared.uHazeRange.value = [-0.35, -2.7];

  const hardscapeCaustics = { strength: 0.3, scale: 1.25, color: CAUSTIC_COLOR };

  const substrate = requireMesh(meshes, 'slice-c-substrate');
  substrate.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'substrate_albedo'),
    normalMap: requireTexture(textures, 'substrate_normal'),
    normalScale: new THREE.Vector2(0.75, 0.75),
    roughness: 0.95,
    metalness: 0,
  }), shared, { haze: true, caustics: { ...hardscapeCaustics, strength: 0.2 } });

  const stone = (meshName, textureName) => {
    const mesh = requireMesh(meshes, meshName);
    mesh.material = applyMaterialEffects(material({
      map: requireTexture(textures, `${textureName}_albedo`),
      normalMap: requireTexture(textures, `${textureName}_normal`),
      roughness: STONE_ROUGHNESS,
      metalness: 0,
      vertexColors: mesh.geometry.hasAttribute('color'),
    }), shared, { haze: true, caustics: hardscapeCaustics });
    return mesh;
  };
  const rocks = [
    stone('slice-c-rock-07', 'rock07'),
    stone('slice-c-boulder', 'boulder'),
    stone('slice-c-rock-09', 'rock09'),
    stone('slice-c-stones', 'stones'),
  ];

  const wood = requireMesh(meshes, 'slice-c-wood');
  wood.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'wood_albedo'),
    normalMap: requireTexture(textures, 'wood_normal'),
    normalScale: new THREE.Vector2(1.6, 1.6),
    roughness: 0.82,
    metalness: 0,
    vertexColors: wood.geometry.hasAttribute('color'),
  }), shared, { haze: true, caustics: hardscapeCaustics });

  // Photographed leaves as tight outline strips: alpha only at the rim,
  // alpha test (no blending). Matte, no clearcoat: no pale sheen.
  const leaves = requireMesh(meshes, 'slice-c-leaves');
  renameAttribute(leaves.geometry, '_sway', 'sway');
  leaves.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'leaves_albedo'),
    normalMap: requireTexture(textures, 'leaves_normal'),
    normalScale: new THREE.Vector2(0.6, 0.6),
    roughness: 0.74,
    metalness: 0,
    alphaTest: 0.5,
    side: THREE.DoubleSide,
    vertexColors: leaves.geometry.hasAttribute('color'),
  }), shared, {
    haze: true,
    caustics: { ...hardscapeCaustics, strength: 0.05 },
    sway: { amplitude: 0.03, frequency: 0.5 },
  });

  const sceneMeshes = [substrate, ...rocks, wood, leaves];
  for (const mesh of sceneMeshes) {
    mesh.removeFromParent();
    mesh.frustumCulled = true;
    add(mesh);
  }

  const width = bounds.maxX - bounds.minX;
  const height = bounds.maxY - bounds.minY;
  const particlePositions = [];
  const particleCount = Math.round(environment.particleCount * 0.7);
  for (let index = 0; index < particleCount; index += 1) {
    particlePositions.push(
      bounds.minX + seededUnit(config.seed, index, 40) * width,
      bounds.minY + seededUnit(config.seed, index, 41) * height,
      bounds.minZ + seededUnit(config.seed, index, 42) * (bounds.maxZ - bounds.minZ),
    );
  }
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute('position', new THREE.Float32BufferAttribute(particlePositions, 3));
  const particleMaterial = new THREE.PointsMaterial({
    color: 0x9cc8c0,
    size: 0.007,
    transparent: true,
    opacity: 0.18,
    depthWrite: false,
  });
  materials.push(particleMaterial);
  const particles = add(new THREE.Points(particleGeometry, particleMaterial));
  particles.name = 'water-particles';

  // Restrained warm focus on the left hardscape; cooler, weaker light
  // everywhere else; the open water to the right stays deep and dark.
  add(new THREE.AmbientLight(0xa9d4cf, 0.2)).name = 'water-ambient-light';
  add(new THREE.HemisphereLight(0x9fd0c7, 0x0c1a16, 0.85)).name = 'water-fill-light';
  const topLight = add(new THREE.DirectionalLight(0xd4eaf0, 1.15));
  topLight.name = 'aquarium-top-light';
  topLight.position.set(-0.8, 4.0, 2.0);
  const key = add(new THREE.SpotLight(0xffcf98, 80, 0, 0.42, 1.0, 1.6));
  key.name = 'hardscape-key-light';
  key.position.set(-3.9, 3.9, 2.2);
  key.target.position.set(-1.9, -0.7, -1.0);
  add(key.target);
  const rimLight = add(new THREE.DirectionalLight(0x6fc7bb, 0.45));
  rimLight.name = 'water-rim-light';
  rimLight.position.set(2.8, 0.8, -1.5);

  return {
    drawCallBudget: 9,
    artMode: 'slice-c',
    effectUniforms: shared,
    cameraTarget: SLICE_C_CAMERA_TARGET,
    updateVisuals(simulationTime) {
      shared.uEffectTime.value = simulationTime;
      backgroundMaterial.uniforms.uTime.value = simulationTime;
      particles.rotation.z = Math.sin(simulationTime * 0.04) * 0.004;
    },
    dispose() {
      for (const object of owned) scene.remove(object);
      for (const created of materials) created.dispose();
      for (const texture of Object.values(textures)) {
        texture.image?.close?.();
        texture.dispose();
      }
      for (const mesh of sceneMeshes) mesh.geometry.dispose();
      particleGeometry.dispose();
      background.geometry.dispose();
    },
  };
}
