import * as THREE from '../vendor/three/three.module.js';
import {
  waterBackgroundSliceBFragmentShader,
  waterBackgroundVertexShader,
} from '../shaders/water-background.js';
import { applyMaterialEffects, createEffectUniforms } from '../shaders/material-effects.js';

// Slice B: the approved Aquascape Hero Frame (Pass 2, composition B)
// translated for the runtime. Geometry and placement come from
// art/tools/build_slice_b.py; this module assigns materials, lighting and
// water atmosphere. Purely visual: it reads no simulation state.
//
// Light hierarchy, economically: one warm spot light (no shadows) keys the
// left hardscape; cooler, weaker top and fill light everywhere else; the
// backdrop and depth haze carry the deep, calm open water to the right.

const CAUSTIC_COLOR = [0.62, 0.86, 0.8];
const BACKDROP = {
  top: 0x2c7b82,
  bottom: 0x0e3c44,
  glow: [0.11, 0.085, 0.05],
  // Plane at z -7.5 spanning y -5.7..6.3: the hazed rear floor (z -6,
  // y -0.7) projects onto it at v ~ 0.41.
  z: -7.5,
  centerY: 0.3,
  width: 24,
  height: 12,
  horizon: 0.41,
};

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
  if (!mesh) throw new Error(`slice-b geometry is missing mesh "${name}"`);
  return mesh;
}

function requireTexture(textures, name) {
  const texture = textures[name];
  if (!texture) throw new Error(`slice-b is missing texture "${name}"`);
  return texture;
}

function renameAttribute(geometry, from, to) {
  const attribute = geometry.getAttribute(from);
  if (!attribute) return;
  geometry.setAttribute(to, attribute);
  geometry.deleteAttribute(from);
}

export function createSliceBEnvironment(scene, config, assets) {
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
      uCalm: { value: 0.35 },
      uSurfaceStrength: { value: 0 },
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

  // Depth haze meets the backdrop's raw value at the floor horizon, so the
  // rear floor dissolves into water with no visible edge.
  const horizonT = BACKDROP.horizon * BACKDROP.horizon * (3 - 2 * BACKDROP.horizon);
  const haze = bottom.clone().lerp(top, horizonT);
  shared.uHazeColor.value = [haze.r, haze.g, haze.b];
  // Background plant masses (z -1.7..-3.4) stay readable but softened;
  // everything beyond z ~ -4.5 is water.
  shared.uHazeRange.value = [-1.0, -4.8];

  const hardscapeCaustics = { strength: 0.3, scale: 1.25, color: CAUSTIC_COLOR };

  const substrate = requireMesh(meshes, 'slice-b-substrate');
  substrate.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'substrate_albedo'),
    normalMap: requireTexture(textures, 'substrate_normal'),
    normalScale: new THREE.Vector2(0.8, 0.8),
    roughness: 0.95,
    metalness: 0,
  }), shared, { haze: true, caustics: { ...hardscapeCaustics, strength: 0.22 } });

  const rocks = requireMesh(meshes, 'slice-b-rocks');
  rocks.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'rock_albedo'),
    normalMap: requireTexture(textures, 'rock_normal'),
    roughnessMap: requireTexture(textures, 'rock_orm'),
    roughness: 1,
    metalness: 0,
    vertexColors: rocks.geometry.hasAttribute('color'),
  }), shared, { haze: true, caustics: hardscapeCaustics });

  const woodOrm = requireTexture(textures, 'wood_orm');
  const wood = requireMesh(meshes, 'slice-b-wood');
  wood.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'wood_albedo'),
    normalMap: requireTexture(textures, 'wood_normal'),
    roughnessMap: woodOrm,
    aoMap: woodOrm,
    aoMapIntensity: 0.8,
    roughness: 1,
    metalness: 0,
    vertexColors: wood.geometry.hasAttribute('color'),
  }), shared, { haze: true, caustics: hardscapeCaustics });

  const moss = requireMesh(meshes, 'slice-b-moss');
  renameAttribute(moss.geometry, '_sway', 'sway');
  moss.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'moss_albedo'),
    normalMap: requireTexture(textures, 'moss_normal'),
    roughness: 0.82,
    metalness: 0,
    alphaTest: 0.5,
    side: THREE.DoubleSide,
  }), shared, {
    haze: true,
    caustics: { ...hardscapeCaustics, strength: 0.3 },
    sway: { amplitude: 0.01, frequency: 0.9 },
  });

  // Solid leaf geometry (vertex colour): no alpha, no overdraw.
  const plants = requireMesh(meshes, 'slice-b-plants');
  renameAttribute(plants.geometry, '_sway', 'sway');
  plants.material = applyMaterialEffects(material({
    vertexColors: true,
    roughness: 0.55,
    metalness: 0,
    side: THREE.DoubleSide,
  }), shared, {
    haze: true,
    caustics: { ...hardscapeCaustics, strength: 0.08 },
    sway: { amplitude: 0.05, frequency: 0.5 },
  });

  // Camera-facing cards: background stem masses and carpet relief. Alpha
  // test only (no blending, no MSAA) to keep overdraw cheap.
  const cards = requireMesh(meshes, 'slice-b-cards');
  renameAttribute(cards.geometry, '_sway', 'sway');
  cards.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'cards_albedo'),
    roughness: 0.7,
    metalness: 0,
    alphaTest: 0.5,
    side: THREE.DoubleSide,
    vertexColors: cards.geometry.hasAttribute('color'),
  }), shared, {
    haze: true,
    sway: { amplitude: 0.03, frequency: 0.45 },
  });

  const sceneMeshes = [substrate, rocks, wood, moss, plants, cards];
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

  add(new THREE.AmbientLight(0xb8dcd6, 0.22)).name = 'water-ambient-light';
  add(new THREE.HemisphereLight(0xa8d6cc, 0x10201a, 0.95)).name = 'water-fill-light';
  const topLight = add(new THREE.DirectionalLight(0xd8ecf0, 1.35));
  topLight.name = 'aquarium-top-light';
  topLight.position.set(-0.8, 4.0, 2.0);
  // Hero key: warm and soft, from the upper left onto the hardscape; falls
  // off through the centre before the open water.
  const key = add(new THREE.SpotLight(0xffcf98, 95, 0, 0.42, 1.0, 1.6));
  key.name = 'hardscape-key-light';
  key.position.set(-3.9, 3.9, 2.2);
  key.target.position.set(-1.8, -0.6, -1.0);
  add(key.target);
  const rimLight = add(new THREE.DirectionalLight(0x6fc7bb, 0.5));
  rimLight.name = 'water-rim-light';
  rimLight.position.set(2.8, 0.8, -1.5);

  return {
    drawCallBudget: 8,
    artMode: 'slice-b',
    effectUniforms: shared,
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
