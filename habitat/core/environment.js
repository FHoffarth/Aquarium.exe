import * as THREE from '../vendor/three/three.module.js';
import {
  waterBackgroundFragmentShader,
  waterBackgroundVertexShader,
} from '../shaders/water-background.js';

function mix32(value) {
  let result = value >>> 0;
  result ^= result >>> 16;
  result = Math.imul(result, 0x7feb352d);
  result ^= result >>> 15;
  result = Math.imul(result, 0x846ca68b);
  result ^= result >>> 16;
  return result >>> 0;
}

function seededUnit(seed, index, channel) {
  return mix32(seed ^ Math.imul(index + 1, 0x9e3779b1)
    ^ Math.imul(channel + 1, 0x85ebca77)) / 0x100000000;
}

// An asymmetric, gently curved blade rather than a symmetric spike: one
// side bulges more than the other and the tip leans, closer to a real
// plant leaf than a repeated procedural lens shape.
function createLeafGeometry(width = 0.18, lean = 0.32) {
  const shape = new THREE.Shape();
  shape.moveTo(0, 0);
  shape.bezierCurveTo(
    -width * 0.55, 0.24,
    -width * 0.68 - lean * 0.2, 0.58,
    -width * 0.22 - lean * 0.32, 0.88,
  );
  shape.quadraticCurveTo(-width * 0.06 - lean * 0.1, 0.97, 0, 1.0);
  shape.quadraticCurveTo(width * 0.46, 0.8, width * 0.5, 0.46);
  shape.quadraticCurveTo(width * 0.38, 0.16, 0, 0);
  return new THREE.ShapeGeometry(shape, 6);
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function pickCluster(clusters, seed, index, channel) {
  const roll = seededUnit(seed, index, channel);
  let cumulative = 0;
  for (const cluster of clusters) {
    cumulative += cluster.weight;
    if (roll < cumulative) return cluster;
  }
  return clusters[clusters.length - 1];
}

function disposeObject(object) {
  object.geometry?.dispose();
  if (Array.isArray(object.material)) {
    for (const material of object.material) material.dispose();
  } else {
    object.material?.dispose();
  }
  object.dispose?.();
}

export function createEnvironment(scene, config) {
  if (!scene?.isScene) throw new TypeError('scene must be a Three.js Scene');
  const owned = [];
  const { bounds, environment } = config;
  const width = bounds.maxX - bounds.minX;
  const height = bounds.maxY - bounds.minY;
  const add = object => {
    scene.add(object);
    owned.push(object);
    return object;
  };

  const backgroundMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uTop: { value: new THREE.Color(environment.backgroundTop) },
      uBottom: { value: new THREE.Color(environment.backgroundBottom) },
    },
    vertexShader: waterBackgroundVertexShader,
    fragmentShader: waterBackgroundFragmentShader,
    depthWrite: false,
  });
  const background = add(new THREE.Mesh(
    new THREE.PlaneGeometry(width * 1.8, height * 2.05),
    backgroundMaterial,
  ));
  background.name = 'water-background';
  background.position.set(0, 0.05, bounds.minZ - 0.28);
  background.renderOrder = -10;

  const substrateGeometry = new THREE.PlaneGeometry(width * 1.18, 1.35, 32, 6);
  const substratePositions = substrateGeometry.attributes.position;
  const baseColor = new THREE.Color(environment.substrateColor);
  const shadeColor = baseColor.clone().multiplyScalar(0.6);
  const substrateColors = new Float32Array(substratePositions.count * 3);
  const hardscapeCenters = [-2.05, -1.6, 1.85, 2.1];
  for (let index = 0; index < substratePositions.count; index += 1) {
    const x = substratePositions.getX(index);
    const y = substratePositions.getY(index);
    const contour = Math.sin(x * 1.32) * 0.045 + Math.sin(x * 2.7 + 0.8) * 0.018
      + Math.sin(x * 5.4 - 1.3) * 0.008;
    substratePositions.setY(index, y + contour);
    let nearest = Infinity;
    for (const center of hardscapeCenters) nearest = Math.min(nearest, Math.abs(x - center));
    const blend = clamp(1 - nearest / 0.85, 0, 1);
    const mixed = baseColor.clone().lerp(shadeColor, blend * 0.5);
    substrateColors[index * 3] = mixed.r;
    substrateColors[index * 3 + 1] = mixed.g;
    substrateColors[index * 3 + 2] = mixed.b;
  }
  substratePositions.needsUpdate = true;
  substrateGeometry.setAttribute('color', new THREE.BufferAttribute(substrateColors, 3));
  substrateGeometry.computeVertexNormals();
  const substrate = add(new THREE.Mesh(
    substrateGeometry,
    new THREE.MeshStandardMaterial({
      color: 0xffffff,
      vertexColors: true,
      roughness: 0.98,
      metalness: 0,
    }),
  ));
  substrate.name = 'contoured-substrate';
  substrate.position.set(0, bounds.minY - 0.02, 0.04);
  substrate.rotation.x = -Math.PI / 2.32;

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
  const particles = add(new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({
      color: 0x9ac9c4,
      size: 0.009,
      transparent: true,
      opacity: 0.27,
      depthWrite: false,
    }),
  ));
  particles.name = 'water-particles';

  const transform = new THREE.Object3D();
  const foregroundPlants = new THREE.InstancedMesh(
    createLeafGeometry(0.09),
    new THREE.MeshStandardMaterial({ color: 0x214b38, roughness: 0.9, side: THREE.DoubleSide }),
    environment.foregroundPlantCount,
  );
  foregroundPlants.name = 'foreground-plants';
  foregroundPlants.instanceMatrix.setUsage(THREE.StaticDrawUsage);
  const foregroundClusters = [
    { x: bounds.minX + width * 0.1, weight: 0.34, spread: width * 0.09, scaleBias: 1.2 },
    { x: bounds.minX + width * 0.3, weight: 0.18, spread: width * 0.07, scaleBias: 0.8 },
    { x: bounds.minX + width * 0.62, weight: 0.14, spread: width * 0.1, scaleBias: 0.65 },
    { x: bounds.minX + width * 0.86, weight: 0.34, spread: width * 0.1, scaleBias: 1.05 },
  ];
  const foregroundLayout = [];
  for (let index = 0; index < environment.foregroundPlantCount; index += 1) {
    const cluster = pickCluster(foregroundClusters, config.seed, index, 55);
    const x = clamp(
      cluster.x + (seededUnit(config.seed, index, 50) - 0.5) * 2 * cluster.spread,
      bounds.minX,
      bounds.maxX,
    );
    const z = 0.16 + seededUnit(config.seed, index, 51) * 0.4;
    const scale = (0.17 + seededUnit(config.seed, index, 52) * 0.22) * cluster.scaleBias;
    foregroundLayout.push(x, bounds.minY, z, scale);
    transform.position.set(x, bounds.minY + 0.01, z);
    transform.rotation.set(0, (seededUnit(config.seed, index, 53) - 0.5) * 0.7, 0);
    transform.scale.set(0.75 + seededUnit(config.seed, index, 54) * 0.35, scale, 1);
    transform.updateMatrix();
    foregroundPlants.setMatrixAt(index, transform.matrix);
  }
  foregroundPlants.instanceMatrix.needsUpdate = true;
  add(foregroundPlants);

  const midPlants = new THREE.InstancedMesh(
    createLeafGeometry(0.17),
    new THREE.MeshStandardMaterial({ color: 0x2e6248, roughness: 0.84, side: THREE.DoubleSide }),
    environment.midPlantCount,
  );
  midPlants.name = 'midground-plants';
  midPlants.instanceMatrix.setUsage(THREE.StaticDrawUsage);
  const midClusters = [
    { x: -2.05, weight: 0.42, spread: 0.55, scaleBias: 1.25 },
    { x: -0.95, weight: 0.16, spread: 0.35, scaleBias: 0.75 },
    { x: 2.2, weight: 0.42, spread: 0.5, scaleBias: 1.0 },
  ];
  const midLayout = [];
  for (let index = 0; index < environment.midPlantCount; index += 1) {
    const cluster = pickCluster(midClusters, config.seed, index, 65);
    const x = cluster.x + (seededUnit(config.seed, index, 60) - 0.5) * 2 * cluster.spread;
    const z = -0.2 + seededUnit(config.seed, index, 61) * 0.55;
    const scale = (0.46 + seededUnit(config.seed, index, 62) * 0.62) * cluster.scaleBias;
    midLayout.push(x, bounds.minY, z, scale);
    transform.position.set(x, bounds.minY + 0.015, z);
    transform.rotation.set(0, (seededUnit(config.seed, index, 63) - 0.5) * 0.9, 0);
    transform.scale.set(0.85 + seededUnit(config.seed, index, 64) * 0.35, scale, 1);
    transform.updateMatrix();
    midPlants.setMatrixAt(index, transform.matrix);
  }
  midPlants.instanceMatrix.needsUpdate = true;
  add(midPlants);

  const stems = new THREE.InstancedMesh(
    createLeafGeometry(0.075),
    new THREE.MeshStandardMaterial({ color: 0x3b7355, roughness: 0.82, side: THREE.DoubleSide }),
    environment.stemCount,
  );
  stems.name = 'background-stems';
  stems.instanceMatrix.setUsage(THREE.StaticDrawUsage);
  const stemLayout = [];
  for (let index = 0; index < environment.stemCount; index += 1) {
    const side = index % 2 === 0 ? -1 : 1;
    const x = side * (1.75 + seededUnit(config.seed, index, 70) * 1.05);
    const z = -0.48 + seededUnit(config.seed, index, 71) * 0.22;
    const scale = 1.02 + seededUnit(config.seed, index, 72) * 0.72;
    stemLayout.push(x, bounds.minY, z, scale);
    transform.position.set(x, bounds.minY, z);
    transform.rotation.set(0, 0, (seededUnit(config.seed, index, 73) - 0.5) * 0.16);
    transform.scale.set(0.9, scale, 1);
    transform.updateMatrix();
    stems.setMatrixAt(index, transform.matrix);
  }
  stems.instanceMatrix.needsUpdate = true;
  add(stems);

  const rocks = new THREE.InstancedMesh(
    new THREE.DodecahedronGeometry(1, 0),
    new THREE.MeshStandardMaterial({ color: 0x3c5750, roughness: 0.92, metalness: 0 }),
    environment.rockCount,
  );
  rocks.name = 'hardscape-rocks';
  rocks.instanceMatrix.setUsage(THREE.StaticDrawUsage);
  // Two connected piles rather than scattered isolated boulders: each
  // cluster has one larger anchor rock with smaller satellites offset just
  // far enough to overlap/touch it, and bigger rocks sink further into the
  // substrate (partially buried bases).
  const rockClusters = [
    { x: -2.15, z: -0.05, count: Math.max(1, environment.rockCount - 2), anchorScale: 0.34 },
    { x: 1.95, z: 0.08, count: Math.min(2, environment.rockCount), anchorScale: 0.21 },
  ];
  const rockLayout = [];
  let rockIndex = 0;
  for (const cluster of rockClusters) {
    for (let member = 0; member < cluster.count && rockIndex < environment.rockCount; member += 1) {
      const index = rockIndex;
      rockIndex += 1;
      const isAnchor = member === 0;
      const scale = isAnchor
        ? cluster.anchorScale + seededUnit(config.seed, index, 82) * 0.05
        : cluster.anchorScale * (0.38 + seededUnit(config.seed, index, 82) * 0.4);
      const spread = isAnchor ? 0 : cluster.anchorScale * (0.6 + seededUnit(config.seed, index, 88) * 0.55);
      const angle = seededUnit(config.seed, index, 89) * Math.PI * 2;
      const x = cluster.x + Math.cos(angle) * spread;
      const z = cluster.z + Math.sin(angle) * spread * 0.65;
      const buried = 0.06 + seededUnit(config.seed, index, 87) * 0.16;
      const stretchX = 0.95 + seededUnit(config.seed, index, 86) * 0.7;
      const stretchZ = 0.85 + seededUnit(config.seed, index, 87) * 0.55;
      rockLayout.push(x, bounds.minY + 0.05, z, scale);
      transform.position.set(x, bounds.minY + scale * (0.62 - buried), z);
      transform.rotation.set(
        seededUnit(config.seed, index, 83) * 0.4,
        seededUnit(config.seed, index, 84) * Math.PI,
        seededUnit(config.seed, index, 85) * 0.3,
      );
      transform.scale.set(scale * 1.25 * stretchX, scale * 0.72, scale * stretchZ);
      transform.updateMatrix();
      rocks.setMatrixAt(index, transform.matrix);
    }
  }
  rocks.instanceMatrix.needsUpdate = true;
  add(rocks);

  const driftwood = new THREE.InstancedMesh(
    new THREE.CylinderGeometry(0.055, 0.09, 1, 7),
    new THREE.MeshStandardMaterial({ color: 0x4a3528, roughness: 0.94, metalness: 0 }),
    environment.driftwoodCount,
  );
  driftwood.name = 'driftwood';
  driftwood.instanceMatrix.setUsage(THREE.StaticDrawUsage);
  // One coherent fallen branch sweeping through the composition, rather
  // than several sticks converging to a point: pieces follow a single
  // diagonal direction, thickening and leveling out toward the buried base.
  const driftwoodLayout = [];
  const driftwoodSteps = Math.max(1, environment.driftwoodCount - 1);
  for (let index = 0; index < environment.driftwoodCount; index += 1) {
    const t = index / driftwoodSteps;
    const x = 0.5 + t * 0.95 + (seededUnit(config.seed, index, 90) - 0.5) * 0.08;
    const y = bounds.minY + 0.08 + t * 0.3 + (seededUnit(config.seed, index, 94) - 0.5) * 0.03;
    const z = -0.4 + (seededUnit(config.seed, index, 91) - 0.5) * 0.16;
    const scale = 0.5 - t * 0.18 + seededUnit(config.seed, index, 92) * 0.1;
    const tilt = -0.6 - t * 0.32 + (seededUnit(config.seed, index, 93) - 0.5) * 0.18;
    const rotation = (seededUnit(config.seed, index, 95) - 0.5) * 0.2;
    driftwoodLayout.push(x, y, z, scale, tilt, rotation);
    transform.position.set(x, y, z);
    transform.rotation.set(rotation, 0, tilt);
    transform.scale.set(1, scale, 1);
    transform.updateMatrix();
    driftwood.setMatrixAt(index, transform.matrix);
  }
  driftwood.instanceMatrix.needsUpdate = true;
  add(driftwood);

  const ambient = add(new THREE.AmbientLight(0xffffff, 0.6));
  const hemisphere = add(new THREE.HemisphereLight(0xc8eee5, 0x15332c, 2.35));
  const topLight = add(new THREE.DirectionalLight(0xffefcd, 3.7));
  topLight.position.set(-1.6, 3.4, 3.2);
  const rimLight = add(new THREE.DirectionalLight(0x86e0cf, 1.15));
  rimLight.position.set(2.8, 0.8, -1.5);
  ambient.name = 'water-ambient-light';
  hemisphere.name = 'water-fill-light';
  topLight.name = 'aquarium-top-light';
  rimLight.name = 'water-rim-light';
  scene.fog = new THREE.Fog(environment.fogColor, 5.7, 9.4);

  return {
    drawCallBudget: 8,
    debugLayout: {
      particles: particlePositions,
      foregroundPlants: foregroundLayout,
      midPlants: midLayout,
      stems: stemLayout,
      rocks: rockLayout,
      driftwood: driftwoodLayout,
    },
    updateVisuals(simulationTime) {
      backgroundMaterial.uniforms.uTime.value = simulationTime;
      particles.rotation.z = Math.sin(simulationTime * 0.04) * 0.004;
      midPlants.rotation.z = Math.sin(simulationTime * 0.18) * 0.0025;
      stems.rotation.z = Math.sin(simulationTime * 0.12 + 1.2) * 0.002;
    },
    dispose() {
      for (const object of owned) {
        scene.remove(object);
        disposeObject(object);
      }
      scene.fog = null;
    },
  };
}
