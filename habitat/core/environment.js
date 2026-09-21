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

export function createEnvironment(scene, config) {
  if (!scene?.isScene) throw new TypeError('scene must be a Three.js Scene');
  const owned = [];
  const { bounds, environment } = config;
  const width = bounds.maxX - bounds.minX;
  const height = bounds.maxY - bounds.minY;

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
  const background = new THREE.Mesh(
    new THREE.PlaneGeometry(width * 1.8, height * 2.0),
    backgroundMaterial,
  );
  background.name = 'water-background';
  background.position.set(0, 0, bounds.minZ - 0.22);
  background.renderOrder = -10;
  scene.add(background);
  owned.push(background);

  const substrate = new THREE.Mesh(
    new THREE.PlaneGeometry(width * 1.12, 1.25),
    new THREE.MeshStandardMaterial({
      color: environment.substrateColor,
      roughness: 1,
      metalness: 0,
    }),
  );
  substrate.name = 'substrate';
  substrate.position.set(0, bounds.minY - 0.03, 0.02);
  substrate.rotation.x = -Math.PI / 2.35;
  scene.add(substrate);
  owned.push(substrate);

  const particlePositions = [];
  for (let index = 0; index < environment.particleCount; index += 1) {
    particlePositions.push(
      bounds.minX + seededUnit(config.seed, index, 40) * width,
      bounds.minY + seededUnit(config.seed, index, 41) * height,
      bounds.minZ + seededUnit(config.seed, index, 42) * (bounds.maxZ - bounds.minZ),
    );
  }
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(particlePositions, 3),
  );
  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({
      color: 0x8bc8c7,
      size: 0.011,
      transparent: true,
      opacity: 0.34,
      depthWrite: false,
    }),
  );
  particles.name = 'water-particles';
  scene.add(particles);
  owned.push(particles);

  const plantShape = new THREE.Shape();
  plantShape.moveTo(-0.12, 0);
  plantShape.bezierCurveTo(-0.28, 0.32, -0.13, 0.82, 0, 1);
  plantShape.bezierCurveTo(0.15, 0.75, 0.24, 0.28, 0.12, 0);
  plantShape.closePath();
  const plantGeometry = new THREE.ShapeGeometry(plantShape, 3);
  const plantMaterial = new THREE.MeshStandardMaterial({
    color: 0x315f49,
    roughness: 0.88,
    metalness: 0,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.78,
  });
  const plants = new THREE.InstancedMesh(
    plantGeometry,
    plantMaterial,
    environment.plantCount,
  );
  plants.name = 'plant-silhouettes';
  plants.instanceMatrix.setUsage(THREE.StaticDrawUsage);
  const plantLayout = [];
  const plantTransform = new THREE.Object3D();
  for (let index = 0; index < environment.plantCount; index += 1) {
    const x = bounds.minX + seededUnit(config.seed, index, 50) * width;
    const y = bounds.minY - 0.03;
    const z = bounds.minZ + seededUnit(config.seed, index, 51)
      * (bounds.maxZ - bounds.minZ) * 0.8;
    const scale = 0.35 + seededUnit(config.seed, index, 52) * 0.78;
    plantLayout.push(x, y, z, scale);
    plantTransform.position.set(x, y, z);
    plantTransform.rotation.set(0, (seededUnit(config.seed, index, 53) - 0.5) * 0.7, 0);
    plantTransform.scale.set(0.12 + scale * 0.08, scale, 1);
    plantTransform.updateMatrix();
    plants.setMatrixAt(index, plantTransform.matrix);
  }
  plants.instanceMatrix.needsUpdate = true;
  scene.add(plants);
  owned.push(plants);

  const hemisphere = new THREE.HemisphereLight(0xd8fff7, 0x102426, 2.15);
  const directional = new THREE.DirectionalLight(0xfff5dc, 2.35);
  directional.position.set(-2.2, 2.8, 3.4);
  scene.add(hemisphere, directional);
  owned.push(hemisphere, directional);

  scene.fog = new THREE.Fog(environment.fogColor, 6.1, 9.8);

  return {
    drawCallBudget: 4,
    debugLayout: {
      particles: particlePositions,
      plants: plantLayout,
    },
    updateVisuals(simulationTime) {
      backgroundMaterial.uniforms.uTime.value = simulationTime;
      particles.rotation.z = Math.sin(simulationTime * 0.04) * 0.004;
    },
    dispose() {
      for (const object of owned) {
        scene.remove(object);
        object.geometry?.dispose();
        if (Array.isArray(object.material)) {
          for (const material of object.material) material.dispose();
        } else {
          object.material?.dispose();
        }
        object.dispose?.();
      }
      scene.fog = null;
    },
  };
}
