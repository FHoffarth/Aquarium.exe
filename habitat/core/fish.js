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

// Revolves a length-wise radius profile around the local X axis (+X = head,
// -X = tail) so the body reads as an organic taper rather than a squashed
// sphere: rounded nose, a shoulder swell, and a narrow caudal peduncle
// before the tail attaches. Radial cross-section stays circular here;
// per-archetype non-uniform scale (bodyScale) flattens it into the final
// silhouette, same as the sphere it replaces.
function createBodyGeometry(radialSegments = 10) {
  const profile = [
    [-1.0, 0.026],
    [-0.84, 0.075],
    [-0.6, 0.175],
    [-0.28, 0.29],
    [0.02, 0.31],
    [0.32, 0.235],
    [0.6, 0.145],
    [0.83, 0.072],
    [1.0, 0.02],
  ];
  const positions = [];
  const uvs = [];
  for (let ring = 0; ring < profile.length; ring += 1) {
    const [x, r] = profile[ring];
    for (let segment = 0; segment <= radialSegments; segment += 1) {
      const theta = (segment / radialSegments) * Math.PI * 2;
      positions.push(x, Math.cos(theta) * r, Math.sin(theta) * r);
      uvs.push(segment / radialSegments, ring / (profile.length - 1));
    }
  }
  const indices = [];
  for (let ring = 0; ring < profile.length - 1; ring += 1) {
    for (let segment = 0; segment < radialSegments; segment += 1) {
      const a = ring * (radialSegments + 1) + segment;
      const b = a + radialSegments + 1;
      indices.push(a, b, a + 1, a + 1, b, b + 1);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();

  // Bake a dorsal(darker)/ventral(lighter) gradient into the neutral vertex
  // color channel so fish read as lit from above without touching the
  // instance archetype color: final color = instanceColor * this gradient.
  const position = geometry.attributes.position;
  const colors = new Float32Array(position.count * 3);
  for (let index = 0; index < position.count; index += 1) {
    const y = position.getY(index);
    const ring = Math.floor(index / (radialSegments + 1));
    const radius = profile[Math.min(ring, profile.length - 1)][1];
    const verticalRatio = radius > 1e-6 ? clamp(y / radius, -1, 1) : 0;
    const shade = 0.82 + (1 - verticalRatio) * 0.5 * 0.22;
    colors[index * 3] = shade;
    colors[index * 3 + 1] = shade;
    colors[index * 3 + 2] = shade;
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return geometry;
}

// A flat, forked caudal fin: root at the peduncle attachment, two lobes
// swept outward around a shallow notch, instead of a solid triangular cone.
// Root sits exactly at the shape's local origin so any Z-axis rotation
// (tailAngle animation, or the base -90-degree orientation) leaves the
// attachment point undisturbed — only the fork tips swing.
function createTailGeometry() {
  const shape = new THREE.Shape();
  shape.moveTo(0, 0);
  shape.lineTo(0.52, 0.92);
  shape.quadraticCurveTo(0.24, 0.7, 0.1, 0.6);
  shape.quadraticCurveTo(0, 0.52, -0.1, 0.6);
  shape.quadraticCurveTo(-0.24, 0.7, -0.52, 0.92);
  shape.lineTo(0, 0);
  return new THREE.ShapeGeometry(shape, 6);
}

// A single swept fin blade shared by dorsal/pectoral/ventral placements,
// distinguished only by their instance transform (position/rotation/scale).
// Root at the local origin for the same flush-attachment reason as the tail.
function createFinGeometry() {
  const shape = new THREE.Shape();
  shape.moveTo(-0.12, 0);
  shape.lineTo(0.3, 0.82);
  shape.quadraticCurveTo(0.08, 0.6, -0.08, 0.42);
  shape.lineTo(-0.12, 0);
  return new THREE.ShapeGeometry(shape, 5);
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

  const FINS_PER_FISH = 4;

  const meshes = {
    body: createPart(
      scene,
      'body',
      createBodyGeometry(),
      new THREE.MeshStandardMaterial({
        roughness: 0.45,
        metalness: 0.04,
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
        roughness: 0.28,
        metalness: 0.06,
        vertexColors: true,
        emissive: 0x0a0e0b,
        emissiveIntensity: 0.3,
      }),
      maximumFish,
    ),
    tail: createPart(
      scene,
      'tail',
      withNeutralVertexColor(createTailGeometry()),
      new THREE.MeshStandardMaterial({
        roughness: 0.5,
        metalness: 0.02,
        vertexColors: true,
        emissive: 0x0a0705,
        emissiveIntensity: 0.3,
        transparent: true,
        opacity: 0.86,
        side: THREE.DoubleSide,
      }),
      maximumFish,
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
      withNeutralVertexColor(createFinGeometry()),
      new THREE.MeshStandardMaterial({
        roughness: 0.45,
        metalness: 0.02,
        vertexColors: true,
        emissive: 0x080b09,
        emissiveIntensity: 0.3,
        transparent: true,
        opacity: 0.8,
        side: THREE.DoubleSide,
      }),
      maximumFish * FINS_PER_FISH,
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
        // Belly highlight: a flattened lighter patch on the underside,
        // rather than a stripe, to read as ventral lightening.
        writePart(
          meshes.accent,
          index,
          [visual.bodyScale[0] * 0.02, -visual.bodyScale[1] * 0.32, 0],
          [0, 0, 0],
          [visual.bodyScale[0] * 0.62, visual.bodyScale[1] * 0.46, visual.bodyScale[2] * 1.03],
        );
        writePart(
          meshes.tail,
          index,
          [-visual.bodyScale[0] * 0.94, 0, 0],
          [0, 0, -Math.PI / 2 + visual.tailAngle],
          visual.tailScale,
        );
        const eyeX = visual.bodyScale[0] * 0.7;
        const eyeY = visual.bodyScale[1] * 0.22;
        const eyeZ = visual.bodyScale[2] * 0.86;
        writePart(meshes.eye, index * 2, [eyeX, eyeY, eyeZ], [0, 0, 0], [0.019, 0.019, 0.013]);
        writePart(meshes.eye, index * 2 + 1, [eyeX, eyeY, -eyeZ], [0, 0, 0], [0.019, 0.019, 0.013]);
        // Dorsal fin: single blade along the spine.
        writePart(
          meshes.fin,
          index * FINS_PER_FISH,
          [-visual.bodyScale[0] * 0.05, visual.bodyScale[1] * 0.75, 0],
          [0, 0, visual.finAngle],
          [0.05, 0.1, 0.02],
        );
        // Ventral fin: smaller blade, underside, subtler than the dorsal.
        writePart(
          meshes.fin,
          index * FINS_PER_FISH + 1,
          [visual.bodyScale[0] * 0.1, -visual.bodyScale[1] * 0.7, 0],
          [0, 0, Math.PI - visual.finAngle * 0.7],
          [0.03, 0.055, 0.014],
        );
        // Pectoral pair: near the head, one per side, swept back slightly.
        writePart(
          meshes.fin,
          index * FINS_PER_FISH + 2,
          [visual.bodyScale[0] * 0.34, -visual.bodyScale[1] * 0.12, visual.bodyScale[2] * 0.55],
          [Math.PI / 2.6, 0, -0.4 + visual.finAngle * 0.6],
          [0.024, 0.05, 0.012],
        );
        writePart(
          meshes.fin,
          index * FINS_PER_FISH + 3,
          [visual.bodyScale[0] * 0.34, -visual.bodyScale[1] * 0.12, -visual.bodyScale[2] * 0.55],
          [-Math.PI / 2.6, 0, -0.4 + visual.finAngle * 0.6],
          [0.024, 0.05, 0.012],
        );
        const variation = ((fish.seed >>> 12) % 17 - 8) / 220;
        setPartColor(meshes.body, index, visual.bodyColor, variation);
        setPartColor(meshes.accent, index, visual.accentColor, variation * 0.5);
        setPartColor(meshes.tail, index, visual.finColor, variation);
        for (let fin = 0; fin < FINS_PER_FISH; fin += 1) {
          setPartColor(meshes.fin, index * FINS_PER_FISH + fin, visual.finColor, variation);
        }
      }

      for (const mesh of Object.values(meshes)) {
        mesh.count = school.fish.length * (
          mesh === meshes.eye ? 2 : mesh === meshes.fin ? FINS_PER_FISH : 1
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
