import test from 'node:test';
import assert from 'node:assert/strict';

import {
  deriveAuditScenePlan,
  readAuditConfig,
} from '../../habitat/audit-config.js';
import { createPerformanceRecorder } from '../../habitat/core/performance.js';

test('audit defaults preserve the product runtime', () => {
  const config = readAuditConfig({ search: '' });
  assert.deepEqual(config, {
    enabled: false,
    mode: 'full',
    fishCount: 10,
    renderScale: 1,
    targetFps: null,
    pointerMode: 'normal',
  });
  assert.ok(Object.isFrozen(config));
});

test('audit parameters cannot alter product defaults unless audit mode is enabled', () => {
  assert.deepEqual(
    readAuditConfig({ search: '?mode=no-render&fish=50&scale=.5&fps=20&pointer=ignore' }),
    readAuditConfig({ search: '' }),
  );
});

test('query and native audit overrides are validated and normalized', () => {
  const query = readAuditConfig({
    search: '?audit=1&mode=fish-only&fish=25&scale=.75&fps=30&pointer=ignore',
  });
  assert.deepEqual(query, {
    enabled: true,
    mode: 'fish-only',
    fishCount: 25,
    renderScale: 0.75,
    targetFps: 30,
    pointerMode: 'ignore',
  });
  assert.throws(
    () => readAuditConfig({ search: '?audit=1&fish=51' }),
    RangeError,
  );
  assert.throws(
    () => readAuditConfig({ search: '?audit=1&mode=unknown' }),
    RangeError,
  );
});

test('scene plans isolate fish, environment, minimal rendering, and no-render work', () => {
  assert.deepEqual(deriveAuditScenePlan({ enabled: false, mode: 'full', fishCount: 10 }), {
    fishCount: 10,
    createFish: true,
    createEnvironment: true,
    render: true,
  });
  assert.deepEqual(deriveAuditScenePlan({ enabled: true, mode: 'fish-only', fishCount: 25 }), {
    fishCount: 25,
    createFish: true,
    createEnvironment: false,
    render: true,
  });
  assert.deepEqual(deriveAuditScenePlan({ enabled: true, mode: 'environment-only', fishCount: 50 }), {
    fishCount: 0,
    createFish: false,
    createEnvironment: true,
    render: true,
  });
  assert.deepEqual(deriveAuditScenePlan({ enabled: true, mode: 'minimal-render', fishCount: 50 }), {
    fishCount: 0,
    createFish: false,
    createEnvironment: false,
    render: true,
  });
  assert.deepEqual(deriveAuditScenePlan({ enabled: true, mode: 'no-render', fishCount: 50 }), {
    fishCount: 50,
    createFish: true,
    createEnvironment: true,
    render: false,
  });
});

test('disabled recorder performs no clock reads and returns null snapshots', () => {
  let reads = 0;
  const recorder = createPerformanceRecorder({
    enabled: false,
    now: () => { reads += 1; return 1; },
  });
  recorder.beginFrame(10);
  recorder.recordRender(10);
  recorder.add('simulationMs', 4);
  recorder.finishFrame(10);
  assert.equal(recorder.snapshot(), null);
  assert.equal(reads, 0);
});

test('recorder reports frame distribution, clusters, and component means', () => {
  const recorder = createPerformanceRecorder({ enabled: true });
  for (const timestamp of [0, 16.6, 33.3, 50.1, 83.3, 116.7]) {
    recorder.recordRender(timestamp);
  }
  recorder.add('simulationMs', 0.2);
  recorder.add('simulationMs', 0.4);
  recorder.add('fishProjectionMs', 0.5);
  recorder.add('environmentMs', 0.1);
  recorder.add('renderMs', 2);
  recorder.add('callbackMs', 2.8);

  const snapshot = recorder.snapshot();
  assert.equal(snapshot.renderedIntervals.count, 5);
  assert.equal(snapshot.renderedIntervals.median, 16.8);
  assert.equal(snapshot.renderedIntervals.min, 16.6);
  assert.equal(snapshot.renderedIntervals.max, 33.4);
  assert.deepEqual(snapshot.renderedIntervals.values, [16.6, 16.7, 16.8, 33.2, 33.4]);
  assert.deepEqual(snapshot.renderedIntervals.clusters, {
    '17': 3,
    '33': 2,
  });
  assert.equal(snapshot.components.simulationMs.mean, 0.3);
  assert.equal(snapshot.components.simulationMs.count, 2);
  assert.equal(snapshot.components.renderMs.mean, 2);
});

test('record measures a named component from an explicit start mark', () => {
  const reads = [10, 12.5];
  const recorder = createPerformanceRecorder({
    enabled: true,
    now: () => reads.shift(),
  });
  const start = recorder.mark();
  recorder.record('renderMs', start);
  assert.equal(recorder.snapshot().components.renderMs.mean, 2.5);
});

test('snapshot resets samples without changing configuration', () => {
  const recorder = createPerformanceRecorder({ enabled: true });
  recorder.recordRender(100);
  recorder.recordRender(116.7);
  assert.equal(recorder.snapshot().renderedIntervals.count, 1);
  assert.equal(recorder.snapshot().renderedIntervals.count, 0);
  recorder.recordRender(200);
  recorder.recordRender(233.4);
  assert.equal(recorder.snapshot().renderedIntervals.max, 33.4);
});
