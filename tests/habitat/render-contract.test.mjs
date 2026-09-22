import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import * as THREE from '../../habitat/vendor/three/three.module.js';
import { createSchool } from '../../habitat/core/behavior.js';
import {
  createFishRenderer,
  deriveFishVisualState,
} from '../../habitat/core/fish.js';
import { createEnvironment } from '../../habitat/core/environment.js';
import { createPlantedTankConfig } from '../../habitat/habitats/planted-tank/config.js';

test('fish renderer exposes a pure visual-state projection helper', async () => {
  const fishModule = await import('../../habitat/core/fish.js');
  assert.equal(typeof fishModule.deriveFishVisualState, 'function');
});

test('visual projection deterministically differentiates silhouette, palette, and motion phase', () => {
  const school = createSchool(createPlantedTankConfig({ fishCount: 10 }));
  const before = structuredClone(school.fish);
  const byArchetype = Object.fromEntries(
    ['copper', 'silver', 'shadow'].map(archetype => {
      const fish = school.fish.find(candidate => candidate.archetype === archetype);
      return [archetype, deriveFishVisualState(fish, 2.75)];
    }),
  );

  assert.deepEqual(
    deriveFishVisualState(school.fish[0], 2.75),
    deriveFishVisualState(school.fish[0], 2.75),
  );
  assert.equal(new Set(Object.values(byArchetype).map(state => state.bodyColor)).size, 3);
  assert.ok(
    byArchetype.silver.bodyScale[0] / byArchetype.silver.bodyScale[1]
      > byArchetype.shadow.bodyScale[0] / byArchetype.shadow.bodyScale[1],
  );
  assert.ok(byArchetype.copper.tailScale[1] > byArchetype.silver.tailScale[1]);
  assert.notEqual(
    deriveFishVisualState(school.fish[0], 2.75).tailAngle,
    deriveFishVisualState(school.fish[1], 2.75).tailAngle,
  );
  assert.ok(Object.values(byArchetype).every(state => [
    state.heading,
    state.pitch,
    state.bank,
    state.tailAngle,
  ].every(Number.isFinite)));
  assert.deepEqual(school.fish, before);
});

test('fish projection is a one-way read of authoritative simulation state', () => {
  const config = createPlantedTankConfig();
  const school = createSchool(config);
  const before = structuredClone(school);
  const scene = new THREE.Scene();
  const fishRenderer = createFishRenderer(scene, 12);

  fishRenderer.project(school, 4.25);

  assert.deepEqual(school, before);
  const fishMeshes = scene.children.filter(child => child.userData.aquariumFishPart);
  assert.equal(fishMeshes.length, 5);
  assert.ok(fishMeshes.every(mesh => mesh.isInstancedMesh));
  assert.equal(
    fishMeshes.find(mesh => mesh.userData.aquariumFishPart === 'eye').count,
    school.fish.length * 2,
  );
  assert.equal(
    fishMeshes.find(mesh => mesh.userData.aquariumFishPart === 'fin').count,
    school.fish.length * 3,
  );
  assert.equal(fishRenderer.drawCallBudget, 5);
  fishRenderer.dispose();
});

test('every fish part has instance capacity for the full configured population', () => {
  const config = createPlantedTankConfig({ fishCount: 12 });
  const school = createSchool(config);
  const scene = new THREE.Scene();
  const fishRenderer = createFishRenderer(scene, config.fishCount);

  fishRenderer.project(school, 1);

  for (const mesh of scene.children.filter(child => child.userData.aquariumFishPart)) {
    const capacity = mesh.instanceMatrix.count;
    assert.ok(
      mesh.count <= capacity,
      `${mesh.userData.aquariumFishPart} writes ${mesh.count} instances into capacity ${capacity}`,
    );
  }
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
  assert.equal(first.debugLayout.foregroundPlants.length, config.environment.foregroundPlantCount * 4);
  assert.equal(first.debugLayout.midPlants.length, config.environment.midPlantCount * 4);
  assert.equal(first.debugLayout.stems.length, config.environment.stemCount * 4);
  assert.equal(first.debugLayout.rocks.length, config.environment.rockCount * 4);
  assert.equal(first.debugLayout.driftwood.length, config.environment.driftwoodCount * 6);
  assert.doesNotThrow(() => first.updateVisuals(12.5));
  assert.equal(first.drawCallBudget, 8);
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
