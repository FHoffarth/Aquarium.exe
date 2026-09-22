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

test('art mode defaults to the reviewed slice and accepts the procedural A/B baseline', () => {
  assert.equal(DEFAULT_ART_MODE, 'slice-a');
  assert.equal(readArtMode({ search: '' }), 'slice-a');
  assert.equal(readArtMode({ search: '?art=slice-a' }), 'slice-a');
  assert.equal(readArtMode({ search: '?art=procedural' }), 'procedural');
  assert.equal(readArtMode({ search: '?art=../../etc' }), 'slice-a');
  assert.equal(readArtMode(undefined), 'slice-a');
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
