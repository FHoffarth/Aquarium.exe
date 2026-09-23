import * as THREE from '../vendor/three/three.module.js';
import {
  waterBackgroundFragmentShader,
  waterBackgroundVertexShader,
} from '../shaders/water-background.js';
import { applyMaterialEffects, createEffectUniforms } from '../shaders/material-effects.js';

const CAUSTIC_COLOR = [0.62, 0.86, 0.8];

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
  if (!mesh) throw new Error(`slice-a geometry is missing mesh "${name}"`);
  return mesh;
}

function requireTexture(textures, name) {
  const texture = textures[name];
  if (!texture) throw new Error(`slice-a is missing texture "${name}"`);
  return texture;
}

function renameAttribute(geometry, from, to) {
  const attribute = geometry.getAttribute(from);
  if (!attribute) return;
  geometry.setAttribute(to, attribute);
  geometry.deleteAttribute(from);
}

// Hand-authored Slice A planted corner. Geometry and placement come from
// art/tools/build_slice_a.py; this module only assigns materials, lighting
// and water atmosphere. Rendering is purely visual and reads no simulation.
export function createSliceAEnvironment(scene, config, assets) {
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

  const width = bounds.maxX - bounds.minX;
  const height = bounds.maxY - bounds.minY;
  const backgroundMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uTop: { value: new THREE.Color(environment.backgroundTop) },
      uBottom: { value: new THREE.Color(environment.backgroundBottom) },
      uShafts: { value: 1 },
    },
    vertexShader: waterBackgroundVertexShader,
    fragmentShader: waterBackgroundFragmentShader,
    depthWrite: false,
  });
  materials.push(backgroundMaterial);
  const background = add(new THREE.Mesh(
    new THREE.PlaneGeometry(width * 2.4, height * 2.6),
    backgroundMaterial,
  ));
  background.name = 'water-background';
  // Behind the substrate's rear edge (z -1.8) so the floor fades into haze.
  background.position.set(0, 0.2, -2.6);
  background.renderOrder = -10;

  // Backdrop value where the substrate's rear edge meets it: the backdrop
  // plane (z -2.6, spanning y -3.57..3.97) is hit there at vUv.y ~ 0.30.
  // Same gradient as water-background.js, in its raw output space.
  const horizonV = 0.297;
  const horizonT = horizonV * horizonV * (3 - 2 * horizonV);
  const haze = new THREE.Color(environment.backgroundBottom)
    .lerp(new THREE.Color(environment.backgroundTop), horizonT);
  shared.uHazeColor.value = [haze.r, haze.g, haze.b];

  const hardscapeCaustics = { strength: 0.4, scale: 1.25, color: CAUSTIC_COLOR };

  const substrate = requireMesh(meshes, 'slice-a-substrate');
  substrate.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'substrate_albedo'),
    normalMap: requireTexture(textures, 'substrate_normal'),
    normalScale: new THREE.Vector2(0.9, 0.9),
    roughness: 0.96,
    metalness: 0,
  }), shared, { haze: true, caustics: { ...hardscapeCaustics, strength: 0.28 } });

  const rockOrm = requireTexture(textures, 'rock_orm');
  const rocks = requireMesh(meshes, 'slice-a-rocks');
  rocks.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'rock_albedo'),
    normalMap: requireTexture(textures, 'rock_normal'),
    roughnessMap: rockOrm,
    roughness: 1,
    metalness: 0,
    vertexColors: rocks.geometry.hasAttribute('color'),
  }), shared, { haze: true, caustics: hardscapeCaustics });

  const woodOrm = requireTexture(textures, 'wood_orm');
  const wood = requireMesh(meshes, 'slice-a-wood');
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

  const moss = requireMesh(meshes, 'slice-a-moss');
  renameAttribute(moss.geometry, '_sway', 'sway');
  moss.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'moss_albedo'),
    normalMap: requireTexture(textures, 'moss_normal'),
    roughness: 0.82,
    metalness: 0,
    alphaTest: 0.5,
    alphaToCoverage: true,
    side: THREE.DoubleSide,
  }), shared, {
    haze: true,
    caustics: { ...hardscapeCaustics, strength: 0.35 },
    sway: { amplitude: 0.012, frequency: 0.9 },
  });

  const plants = requireMesh(meshes, 'slice-a-plants');
  renameAttribute(plants.geometry, '_sway', 'sway');
  plants.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'plants_albedo'),
    normalMap: requireTexture(textures, 'plants_normal'),
    roughness: 0.62,
    metalness: 0,
    alphaTest: 0.5,
    alphaToCoverage: true,
    side: THREE.DoubleSide,
  }), shared, {
    haze: true,
    caustics: { ...hardscapeCaustics, strength: 0.25 },
    sway: { amplitude: 0.035, frequency: 0.55 },
  });

  const cards = requireMesh(meshes, 'slice-a-cards');
  renameAttribute(cards.geometry, '_sway', 'sway');
  cards.material = applyMaterialEffects(material({
    map: requireTexture(textures, 'cards_albedo'),
    roughness: 0.7,
    metalness: 0,
    alphaTest: 0.5,
    alphaToCoverage: true,
    side: THREE.DoubleSide,
  }), shared, {
    haze: true,
    caustics: { ...hardscapeCaustics, strength: 0.2 },
    sway: { amplitude: 0.03, frequency: 0.5 },
  });

  const sceneMeshes = [substrate, rocks, wood, moss, plants, cards];
  for (const mesh of sceneMeshes) {
    mesh.removeFromParent();
    mesh.frustumCulled = true;
    add(mesh);
  }

  const particlePositions = [];
  for (let index = 0; index < environment.particleCount; index += 1) {
    particlePositions.push(
      bounds.minX + seededUnit(config.seed, index, 40) * width,
      bounds.minY + seededUnit(config.seed, index, 41) * height,
      bounds.minZ + seededUnit(config.seed, index, 42) * (bounds.maxZ - bounds.minZ),
    );
  }
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute('position', new THREE.Float32BufferAttribute(particlePositions, 3));
  const particleMaterial = new THREE.PointsMaterial({
    color: 0xa9d6cf,
    size: 0.008,
    transparent: true,
    opacity: 0.24,
    depthWrite: false,
  });
  materials.push(particleMaterial);
  const particles = add(new THREE.Points(particleGeometry, particleMaterial));
  particles.name = 'water-particles';

  add(new THREE.AmbientLight(0xd6f0ea, 0.35)).name = 'water-ambient-light';
  add(new THREE.HemisphereLight(0xbfe6dc, 0x1c2a22, 1.6)).name = 'water-fill-light';
  const topLight = add(new THREE.DirectionalLight(0xfff0d2, 3.3));
  topLight.name = 'aquarium-top-light';
  topLight.position.set(-1.2, 4.0, 2.4);
  const rimLight = add(new THREE.DirectionalLight(0x86e0cf, 0.9));
  rimLight.name = 'water-rim-light';
  rimLight.position.set(2.8, 0.8, -1.5);
  scene.fog = new THREE.Fog(environment.fogColor, 5.4, 10.5);

  return {
    drawCallBudget: 8,
    artMode: 'slice-a',
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
      scene.fog = null;
    },
  };
}
