import * as THREE from '../vendor/three/three.module.js';

const TAU = Math.PI * 2;

function createPart(scene, name, geometry, material, maximumFish) {
  const mesh = new THREE.InstancedMesh(geometry, material, maximumFish);
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
      new THREE.SphereGeometry(1, 16, 10),
      new THREE.MeshStandardMaterial({
        roughness: 0.62,
        metalness: 0,
        vertexColors: true,
        emissive: 0x1b0b03,
        emissiveIntensity: 0.42,
      }),
      maximumFish,
    ),
    tail: createPart(
      scene,
      'tail',
      new THREE.ConeGeometry(1, 1, 3),
      new THREE.MeshStandardMaterial({
        roughness: 0.68,
        metalness: 0,
        vertexColors: true,
        emissive: 0x160702,
        emissiveIntensity: 0.36,
      }),
      maximumFish,
    ),
    eye: createPart(
      scene,
      'eye',
      new THREE.SphereGeometry(1, 8, 6),
      new THREE.MeshBasicMaterial({ color: 0x07161d }),
      maximumFish,
    ),
    fin: createPart(
      scene,
      'fin',
      new THREE.ConeGeometry(1, 1, 3),
      new THREE.MeshStandardMaterial({
        roughness: 0.72,
        metalness: 0,
        vertexColors: true,
        emissive: 0x130702,
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

  function setFishColor(index, fish) {
    const hue = 0.045 + ((fish.seed >>> 8) % 1000) / 1000 * 0.12;
    const saturation = 0.66 + ((fish.seed >>> 18) % 100) / 600;
    const lightness = 0.58 + ((fish.seed >>> 25) % 50) / 600;
    color.setHSL(hue, saturation, lightness);
    meshes.body.setColorAt(index, color);
    color.offsetHSL(0.015, -0.05, -0.06);
    meshes.tail.setColorAt(index, color);
    meshes.fin.setColorAt(index, color);
  }

  return {
    drawCallBudget: 4,
    project(school, simulationTime) {
      if (school.fish.length > maximumFish) {
        throw new RangeError(`school exceeds renderer capacity ${maximumFish}`);
      }
      for (let index = 0; index < school.fish.length; index += 1) {
        const fish = school.fish[index];
        const horizontalSpeed = Math.hypot(fish.velocity.x, fish.velocity.y);
        const heading = Math.atan2(fish.velocity.y, fish.velocity.x);
        const pitch = -Math.atan2(fish.velocity.z, Math.max(0.001, horizontalSpeed));
        const bank = Math.max(-0.16, Math.min(0.16, fish.velocity.y * 0.42));
        const scale = fish.scale;
        root.position.set(fish.position.x, fish.position.y, fish.position.z);
        root.rotation.set(pitch, bank, heading);
        root.scale.set(scale, scale, scale);
        root.updateMatrix();

        const tailPhase = simulationTime * (4.8 + horizontalSpeed * 4)
          + (fish.seed % 4096) / 4096 * TAU;
        writePart(meshes.body, index, [0, 0, 0], [0, 0, 0], [0.24, 0.095, 0.075]);
        writePart(
          meshes.tail,
          index,
          [-0.27, 0, 0],
          [0, 0, -Math.PI / 2 + Math.sin(tailPhase) * 0.32],
          [0.095, 0.14, 0.075],
        );
        writePart(meshes.eye, index, [0.17, 0.035, 0.066], [0, 0, 0], [0.018, 0.018, 0.014]);
        writePart(
          meshes.fin,
          index,
          [-0.015, -0.095, 0],
          [0, 0, Math.PI],
          [0.045, 0.085, 0.018],
        );
        setFishColor(index, fish);
      }

      for (const mesh of Object.values(meshes)) {
        mesh.count = school.fish.length;
        mesh.instanceMatrix.needsUpdate = true;
      }
      for (const mesh of [meshes.body, meshes.tail, meshes.fin]) {
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
