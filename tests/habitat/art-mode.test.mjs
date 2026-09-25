import test from 'node:test';
import assert from 'node:assert/strict';

import { DEFAULT_ART_MODE, readArtMode } from '../../habitat/core/art-mode.js';
import { AssetIntegrityError } from '../../habitat/core/asset-manifest.js';
import { createPlantedTankForArt } from '../../habitat/habitats/planted-tank/scene.js';

const stubRenderer = () => ({
  isWebGLRenderer: true,
  render() {},
  setSize() {},
  info: { render: { calls: 0, triangles: 0 } },
});

test('art mode defaults to the reviewed slice and keeps Slices B, A and procedural for comparison', () => {
  assert.equal(DEFAULT_ART_MODE, 'slice-c');
  assert.equal(readArtMode({ search: '' }), 'slice-c');
  assert.equal(readArtMode({ search: '?art=slice-c' }), 'slice-c');
  assert.equal(readArtMode({ search: '?art=slice-b' }), 'slice-b');
  assert.equal(readArtMode({ search: '?art=slice-a' }), 'slice-a');
  assert.equal(readArtMode({ search: '?art=procedural' }), 'procedural');
  assert.equal(readArtMode({ search: '?art=../../etc' }), 'slice-c');
  assert.equal(readArtMode(undefined), 'slice-c');
});

test('a Slice C asset failure falls back to the procedural habitat with classic fish', async () => {
  const failures = [];
  const { habitat, art } = await createPlantedTankForArt(stubRenderer(), {
    artMode: 'slice-c',
    loadArtGroup: async group => { throw new AssetIntegrityError(`${group}/environment.glb: SHA-256 mismatch`); },
    reportAssetFailure: error => failures.push(error),
  });
  assert.equal(failures.length, 1);
  assert.match(failures[0].message, /^slice-c\//);
  assert.equal(art.mode, 'procedural');
  assert.equal(habitat.getFishStyle(), 'classic');
  assert.doesNotThrow(() => habitat.project(1 / 60));
  habitat.dispose();
});

test('a Slice B asset failure also falls back to the procedural habitat with classic fish', async () => {
  const failures = [];
  const { habitat, art } = await createPlantedTankForArt(stubRenderer(), {
    artMode: 'slice-b',
    loadArtGroup: async group => { throw new AssetIntegrityError(`${group}/environment.glb: SHA-256 mismatch`); },
    reportAssetFailure: error => failures.push(error),
  });
  assert.equal(failures.length, 1);
  assert.match(failures[0].message, /^slice-b\//);
  assert.equal(art.mode, 'procedural');
  assert.equal(habitat.getFishStyle(), 'classic');
  assert.doesNotThrow(() => habitat.project(1 / 60));
  habitat.dispose();
});

test('asset failure is reported once and falls back to a working procedural habitat', async () => {
  const failures = [];
  const { habitat, art } = await createPlantedTankForArt(stubRenderer(), {
    artMode: 'slice-a',
    loadArtGroup: async () => { throw new AssetIntegrityError('slice-a/environment.glb: SHA-256 mismatch'); },
    reportAssetFailure: error => failures.push(error),
  });

  assert.equal(failures.length, 1);
  assert.match(failures[0].message, /SHA-256 mismatch/);
  assert.equal(art.mode, 'procedural');
  assert.doesNotThrow(() => habitat.step(1 / 60, { present: false, eventsReceived: 0 }));
  assert.doesNotThrow(() => habitat.project(1 / 60));
  assert.equal(habitat.getFishCount(), 10);
  habitat.dispose();
});

test('procedural art mode never touches the asset loader', async () => {
  let loads = 0;
  const { habitat, art } = await createPlantedTankForArt(stubRenderer(), {
    artMode: 'procedural',
    loadArtGroup: async () => { loads += 1; },
    reportAssetFailure: () => assert.fail('no failure expected'),
  });
  assert.equal(loads, 0);
  assert.equal(art.mode, 'procedural');
  habitat.dispose();
});
