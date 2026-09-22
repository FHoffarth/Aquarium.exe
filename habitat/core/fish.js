import * as THREE from '../vendor/three/three.module.js';

const ARCHETYPES = Object.freeze({
  copper: Object.freeze({
    bodyScale: Object.freeze([0.29, 0.112, 0.082]),
    tailScale: Object.freeze([0.105, 0.165, 0.07]),
    bodyColor: 0xe8955f,
    accentColor: 0xf7ce84,
    finColor: 0xb3623f,
  }),
  silver: Object.freeze({
    bodyScale: Object.freeze([0.335, 0.078, 0.063]),
    tailScale: Object.freeze([0.105, 0.14, 0.06]),
    bodyColor: 0xa9dcd6,
    accentColor: 0xe6f5f0,
    finColor: 0x64a196,
  }),
  shadow: Object.freeze({
    bodyScale: Object.freeze([0.255, 0.122, 0.086]),
    tailScale: Object.freeze([0.11, 0.16, 0.075]),
    bodyColor: 0x86ac7c,
    accentColor: 0xd2a165,
    finColor: 0x527d61,
  }),
});

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

export function deriveFishVisualState(fish, simulationTime) {
  const archetype = ARCHETYPES[fish.archetype] ?? ARCHETYPES.silver;
  const horizontalSpeed = Math.hypot(fish.velocity.x, fish.velocity.y);
  const speed = Math.hypot(horizontalSpeed, fish.velocity.z);
  const speedRatio = clamp(speed / Math.max(0.001, fish.maximumSpeed), 0, 1);
  const phase = simulationTime * (3.7 + speedRatio * 4.9) + fish.visualPhase;
  return {
    heading: Math.atan2(fish.velocity.y, fish.velocity.x),
    pitch: -Math.atan2(fish.velocity.z, Math.max(0.001, horizontalSpeed)),
    bank: clamp(-fish.velocity.y * 0.95 + Math.sin(phase * 0.37) * 0.02, -0.34, 0.34),
    tailAngle: Math.sin(phase) * (0.17 + speedRatio * 0.18),
    finAngle: Math.sin(phase * 0.53) * 0.08,
    bodyScale: [...archetype.bodyScale],
    tailScale: [...archetype.tailScale],
    bodyColor: archetype.bodyColor,
    accentColor: archetype.accentColor,
    finColor: archetype.finColor,
  };
}

function withNeutralVertexColor(geometry) {
  const count = geometry.attributes.position.count;
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(count * 3).fill(1), 3));
  return geometry;
}

function createPart(scene, name, geometry, material, maximumInstances) {
  const mesh = new THREE.InstancedMesh(geometry, material, maximumInstances);
  mesh.name = `fish-${name}`;
  mesh.userData.aquariumFishPart = name;
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  mesh.frustumCulled = false;
  scene.add(mesh);
  return mesh;
}

export function createFishRenderer(scene, maximumFish) {
  if (!scene?.isScene) throw new TypeError('scene must be a Three.js Scene');
  if (!Number.isInteger(maximumFish) || maximumFish < 1) {
    throw new RangeError('maximumFish must be a positive integer');
  }

  const meshes = {
    body: createPart(
      scene,
      'body',
      withNeutralVertexColor(new THREE.SphereGeometry(1, 16, 10)),
      new THREE.MeshStandardMaterial({
        roughness: 0.4,
        metalness: 0.05,
        vertexColors: true,
        emissive: 0x060a09,
        emissiveIntensity: 0.35,
      }),
      maximumFish,
    ),
    accent: createPart(
      scene,
      'accent',
      withNeutralVertexColor(new THREE.SphereGeometry(1, 12, 8)),
      new THREE.MeshStandardMaterial({
        roughness: 0.3,
        metalness: 0.1,
        vertexColors: true,
        emissive: 0x0a0e0b,
        emissiveIntensity: 0.3,
      }),
      maximumFish,
    ),
    tail: createPart(
      scene,
      'tail',
      withNeutralVertexColor(new THREE.ConeGeometry(1, 1, 3)),
      new THREE.MeshStandardMaterial({
        roughness: 0.5,
        metalness: 0.02,
        vertexColors: true,
        emissive: 0x0a0705,
        emissiveIntensity: 0.3,
      }),
      maximumFish * 2,
    ),
    eye: createPart(
      scene,
      'eye',
      new THREE.SphereGeometry(1, 8, 6),
      new THREE.MeshStandardMaterial({
        color: 0x123240,
        roughness: 0.1,
        metalness: 0.25,
        emissive: 0x0a1a22,
        emissiveIntensity: 0.5,
      }),
      maximumFish * 3,
    ),
    fin: createPart(
      scene,
      'fin',
      withNeutralVertexColor(new THREE.ConeGeometry(1, 1, 3)),
      new THREE.MeshStandardMaterial({
        roughness: 0.45,
        metalness: 0.02,
        vertexColors: true,
        emissive: 0x080b09,
        emissiveIntensity: 0.3,
      }),
      maximumFish,
    ),
  };

  const root = new THREE.Object3D();
  const part = new THREE.Object3D();
  const matrix = new THREE.Matrix4();
  const color = new THREE.Color();

  function writePart(mesh, index, position, rotation, scale) {
    part.position.set(position[0], position[1], position[2]);
    part.rotation.set(rotation[0], rotation[1], rotation[2]);
    part.scale.set(scale[0], scale[1], scale[2]);
    part.updateMatrix();
    matrix.multiplyMatrices(root.matrix, part.matrix);
    mesh.setMatrixAt(index, matrix);
  }

  function setPartColor(mesh, index, value, lightnessVariation = 0) {
    color.setHex(value);
    if (lightnessVariation) color.offsetHSL(0, 0, lightnessVariation);
    mesh.setColorAt(index, color);
  }

  return {
    drawCallBudget: 5,
    project(school, simulationTime) {
      if (school.fish.length > maximumFish) {
        throw new RangeError(`school exceeds renderer capacity ${maximumFish}`);
      }
      for (let index = 0; index < school.fish.length; index += 1) {
        const fish = school.fish[index];
        const visual = deriveFishVisualState(fish, simulationTime);
        const scale = fish.scale;
        root.position.set(fish.position.x, fish.position.y, fish.position.z);
        root.rotation.set(visual.bank, visual.pitch, visual.heading);
        root.scale.set(scale, scale, scale);
        root.updateMatrix();

        writePart(meshes.body, index, [0, 0, 0], [0, 0, 0], visual.bodyScale);
        writePart(
          meshes.accent,
          index,
          [visual.bodyScale[0] * 0.24, 0, 0],
          [0, 0, 0],
          [0.055, visual.bodyScale[1] * 1.025, visual.bodyScale[2] * 1.025],
        );
        writePart(
          meshes.tail,
          index,
          [-visual.bodyScale[0] * 1.12, 0, 0],
          [0, 0, -Math.PI / 2 + visual.tailAngle],
          visual.tailScale,
        );
        const eyeX = visual.bodyScale[0] * 0.64;
        const eyeY = visual.bodyScale[1] * 0.26;
        const eyeZ = visual.bodyScale[2] * 0.88;
        writePart(meshes.eye, index * 2, [eyeX, eyeY, eyeZ], [0, 0, 0], [0.019, 0.019, 0.013]);
        writePart(meshes.eye, index * 2 + 1, [eyeX, eyeY, -eyeZ], [0, 0, 0], [0.019, 0.019, 0.013]);
        writePart(
          meshes.fin,
          index * 3,
          [-0.015, visual.bodyScale[1] * 0.78, 0],
          [0, 0, visual.finAngle],
          [0.045, 0.09, 0.018],
        );
        writePart(
          meshes.fin,
          index * 3 + 1,
          [0.005, -visual.bodyScale[1] * 0.78, 0],
          [0, 0, Math.PI - visual.finAngle],
          [0.038, 0.072, 0.016],
        );
        writePart(
          meshes.fin,
          index * 3 + 2,
          [0.055, -0.015, visual.bodyScale[2] * 0.92],
          [Math.PI / 2, 0, -0.35 + visual.finAngle],
          [0.032, 0.062, 0.014],
        );
        const variation = ((fish.seed >>> 12) % 17 - 8) / 220;
        setPartColor(meshes.body, index, visual.bodyColor, variation);
        setPartColor(meshes.accent, index, visual.accentColor, variation * 0.5);
        setPartColor(meshes.tail, index, visual.finColor, variation);
        for (let fin = 0; fin < 3; fin += 1) {
          setPartColor(meshes.fin, index * 3 + fin, visual.finColor, variation);
        }
      }

      for (const mesh of Object.values(meshes)) {
        mesh.count = school.fish.length * (
          mesh === meshes.eye ? 2 : mesh === meshes.fin ? 3 : 1
        );
        mesh.instanceMatrix.needsUpdate = true;
      }
      for (const mesh of [meshes.body, meshes.accent, meshes.tail, meshes.fin]) {
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      }
    },
    dispose() {
      for (const mesh of Object.values(meshes)) {
        scene.remove(mesh);
        mesh.geometry.dispose();
        mesh.material.dispose();
        mesh.dispose();
      }
    },
  };
}
