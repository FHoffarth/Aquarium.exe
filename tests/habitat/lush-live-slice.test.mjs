import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../../habitat/vendor/three/three.module.js';
import {
  createLushLiveSliceEnvironment,
  mapLushLiveSliceFish,
} from '../../habitat/core/lush-live-slice.js';

test('live-slice fish mapping preserves simulation state and spans plant depth', () => {
  const fish = {
    position: { x: 2, y: -0.5, z: 0.5 },
    velocity: { x: 0.2, y: 0.1, z: -0.05 },
    visualPhase: 1.2,
  };
  const mapped = mapLushLiveSliceFish(fish);
  for (const [axis, expected] of Object.entries({ x: 1.8, y: 2.6, z: 0.7 })) {
    assert.ok(Math.abs(mapped.position[axis] - expected) < 1e-9);
  }
  for (const [axis, expected] of Object.entries({ x: 0.18, y: 0.1, z: -0.16 })) {
    assert.ok(Math.abs(mapped.velocity[axis] - expected) < 1e-9);
  }
  assert.deepEqual(fish.position, { x: 2, y: -0.5, z: 0.5 });
  assert.deepEqual(fish.velocity, { x: 0.2, y: 0.1, z: -0.05 });
  assert.ok(mapLushLiveSliceFish({ ...fish, position: { ...fish.position, z: -0.65 } }).position.z < -2.9);
  assert.ok(mapLushLiveSliceFish({ ...fish, position: { ...fish.position, z: 0.65 } }).position.z > 1.1);
});

test('live-slice environment mounts real depth geometry and approved camera', () => {
  const scene = new THREE.Scene();
  const root = new THREE.Group();
  const camera = new THREE.PerspectiveCamera(23.8224, 16 / 9, 0.1, 1000);
  camera.position.set(0, 6.6, 15.3);
  root.add(camera);
  for (let i = 0; i < 3; i += 1) {
    const material = new THREE.MeshStandardMaterial({
      alphaTest: i === 0 ? 0.45 : 0,
      side: THREE.DoubleSide,
    });
    material.name = i === 0 ? 'photographed broad leaf surfaces.001' : `leaf-${i}`;
    root.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), material));
  }
  const environment = createLushLiveSliceEnvironment(scene, {
    sceneGraphs: { 'lush-slice/environment.glb': root },
  });
  assert.equal(environment.referenceCamera, camera);
  assert.equal(root.parent, scene);
  assert.ok(scene.children.some(object => object.isDirectionalLight));
  environment.dispose();
  assert.equal(root.parent, null);
});
