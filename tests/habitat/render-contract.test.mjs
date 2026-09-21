import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import * as THREE from '../../habitat/vendor/three/three.module.js';
import { createSchool } from '../../habitat/core/behavior.js';
import { createFishRenderer } from '../../habitat/core/fish.js';
import { createEnvironment } from '../../habitat/core/environment.js';
import { createPlantedTankConfig } from '../../habitat/habitats/planted-tank/config.js';

test('fish projection is a one-way read of authoritative simulation state', () => {
  const config = createPlantedTankConfig();
  const school = createSchool(config);
  const before = structuredClone(school);
  const scene = new THREE.Scene();
  const fishRenderer = createFishRenderer(scene, 12);

  fishRenderer.project(school, 4.25);

  assert.deepEqual(school, before);
  const fishMeshes = scene.children.filter(child => child.userData.aquariumFishPart);
  assert.equal(fishMeshes.length, 4);
  assert.ok(fishMeshes.every(mesh => mesh.isInstancedMesh));
  assert.ok(fishMeshes.every(mesh => mesh.count === school.fish.length));
  assert.equal(fishRenderer.drawCallBudget, 4);
  fishRenderer.dispose();
});

test('projection updates instance transforms without creating per-fish scene objects', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  const scene = new THREE.Scene();
  const fishRenderer = createFishRenderer(scene, 12);
  const matrix = new THREE.Matrix4();

  fishRenderer.project(school, 0);
  const body = scene.children.find(child => child.userData.aquariumFishPart === 'body');
  body.getMatrixAt(0, matrix);
  const firstMatrix = matrix.toArray();
  school.fish[0].position.x += 1;
  fishRenderer.project(school, 1);
  body.getMatrixAt(0, matrix);

  assert.notDeepEqual(matrix.toArray(), firstMatrix);
  assert.equal(scene.children.filter(child => child.isGroup).length, 0);
  fishRenderer.dispose();
});

test('environment is deterministic, bounded, and visual-only', () => {
  const config = createPlantedTankConfig();
  const firstScene = new THREE.Scene();
  const secondScene = new THREE.Scene();
  const first = createEnvironment(firstScene, config);
  const second = createEnvironment(secondScene, config);

  assert.deepEqual(first.debugLayout, second.debugLayout);
  assert.equal(first.debugLayout.particles.length, config.environment.particleCount * 3);
  assert.equal(first.debugLayout.plants.length, config.environment.plantCount * 4);
  assert.doesNotThrow(() => first.updateVisuals(12.5));
  assert.equal(first.drawCallBudget, 4);
  first.dispose();
  second.dispose();
});

test('behavior core has no renderer or DOM dependency', async () => {
  const source = await readFile(
    new URL('../../habitat/core/behavior.js', import.meta.url),
    'utf8',
  );
  assert.doesNotMatch(source, /\bTHREE\b|document\.|window\.|HTMLElement|WebGL/);
  assert.doesNotMatch(source, /^\s*import\s/m);
});
