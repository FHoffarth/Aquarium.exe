import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../../habitat/vendor/three/three.module.js';
import {
  LUSH_LIVE_FISH_SCALE,
  createLushLiveEnvironment,
  mapLushLiveFish,
} from '../../habitat/core/lush-live.js';

test('live aquarium fish mapping is render-side only and spans the plant layers', () => {
  const fish = { position: { x: 3, y: 1.45, z: 0.65 }, velocity: { x: 0.2, y: 0.1, z: -0.05 }, visualPhase: 0.4 };
  const front = mapLushLiveFish(fish);
  const back = mapLushLiveFish({ ...fish, position: { x: -3, y: -1.45, z: -0.65 } });
  // Simulation state is never written.
  assert.deepEqual(fish.position, { x: 3, y: 1.45, z: 0.65 });
  assert.equal(front.visualPhase, 0.4);
  // Wide enough to reach the side plantings, above the floor, below the surface.
  assert.ok(front.position.x > 4.5 && back.position.x < -4.5);
  assert.ok(back.position.y > 0.6 && front.position.y < 4.5);
  // From among the foreground plants (Three z > +1.5) back to the rear plants (< -2.5).
  assert.ok(front.position.z > 1.5 && back.position.z < -2.5);
  assert.ok(LUSH_LIVE_FISH_SCALE > 0.75);
});

test('live aquarium mounts real geometry, keeps the rear as geometry and uses the approved camera', () => {
  const scene = new THREE.Scene();
  const root = new THREE.Group();
  const camera = new THREE.PerspectiveCamera(23.8224, 16 / 9, 0.1, 1000);
  camera.position.set(0, 6.6, 15.3);
  root.add(camera);
  const rear = new THREE.MeshStandardMaterial();
  rear.name = 'clear blue depth';
  const rearMesh = new THREE.Mesh(new THREE.PlaneGeometry(17, 8), rear);
  root.add(rearMesh);
  for (let i = 0; i < 12; i += 1) {
    const material = new THREE.MeshStandardMaterial({ side: THREE.DoubleSide });
    material.name = `leaf-0-${i}`;
    root.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), material));
  }
  const environment = createLushLiveEnvironment(scene, { sceneGraphs: { 'lush-live/environment.glb': root } });
  assert.equal(environment.referenceCamera, camera);
  assert.equal(root.parent, scene);
  assert.ok(rearMesh.material.isMeshBasicMaterial, 'rear boundary keeps its geometry with its own material');
  assert.ok(rearMesh.geometry.hasAttribute('color'));
  assert.equal(environment.mapFish, mapLushLiveFish);
  assert.ok(environment.exposure > 0);
  // No water treatment in the composition proof.
  assert.equal(scene.fog, null);
  assert.equal(environment.effectUniforms, undefined);
  environment.dispose();
  assert.equal(root.parent, null);
});

test('live aquarium refuses a transparent (non depth-writing) environment material', () => {
  const scene = new THREE.Scene();
  const root = new THREE.Group();
  root.add(new THREE.PerspectiveCamera());
  for (let i = 0; i < 12; i += 1) {
    root.add(new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial({ transparent: i === 5 })));
  }
  assert.throws(() => createLushLiveEnvironment(scene, { sceneGraphs: { 'lush-live/environment.glb': root } }),
    /depth-tested, depth-writing/);
});
