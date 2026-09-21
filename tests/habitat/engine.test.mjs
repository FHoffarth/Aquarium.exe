import test from 'node:test';
import assert from 'node:assert/strict';

import {
  FrameClock,
  createHabitatEngine,
} from '../../habitat/core/engine.js';

function createScheduler() {
  let nextId = 1;
  const callbacks = new Map();
  return {
    request(callback) {
      const id = nextId;
      nextId += 1;
      callbacks.set(id, callback);
      return id;
    },
    cancel(id) {
      callbacks.delete(id);
    },
    fire(nowMs) {
      const entries = [...callbacks.entries()];
      callbacks.clear();
      for (const [, callback] of entries) callback(nowMs);
    },
    get pending() {
      return callbacks.size;
    },
  };
}

function createFakeHabitat() {
  return {
    steps: [],
    projects: [],
    pointerSnapshots: [],
    resizeCalls: [],
    disposed: false,
    step(deltaSeconds, pointer) {
      this.steps.push(deltaSeconds);
      this.pointerSnapshots.push({ ...pointer });
    },
    project(simulationTime) {
      this.projects.push(simulationTime);
    },
    resize(width, height) {
      this.resizeCalls.push([width, height]);
    },
    getFishCount() {
      return 10;
    },
    getRenderInfo() {
      return { calls: 4, triangles: 7200 };
    },
    getReactionCount() {
      return 3;
    },
    dispose() {
      this.disposed = true;
    },
  };
}

test('resume after pause discards paused wall time', () => {
  const clock = new FrameClock();
  clock.resume(1000);
  clock.tick(1017);
  clock.pause();
  clock.resume(100000);
  clock.tick(100017);
  assert.ok(clock.stepCount <= 2);
  assert.ok(clock.frameDeltaMs <= 17.1);
});

test('catch-up is capped after a long frame', () => {
  const clock = new FrameClock({ maxSteps: 4 });
  clock.resume(0);
  clock.tick(10000);
  assert.equal(clock.stepCount, 4);
});

test('target frame rate gates projection without changing fixed-step timing', () => {
  const clock = new FrameClock({ targetFps: 30 });
  clock.resume(0);
  clock.tick(16.7);
  assert.equal(clock.shouldRender, true);
  clock.tick(25);
  assert.equal(clock.shouldRender, false);
  clock.tick(50.1);
  assert.equal(clock.shouldRender, true);
});

test('engine keeps one callback outstanding and pause cancels it', () => {
  const scheduler = createScheduler();
  const habitat = createFakeHabitat();
  const engine = createHabitatEngine({
    habitat,
    requestFrame: callback => scheduler.request(callback),
    cancelFrame: id => scheduler.cancel(id),
    now: () => 100,
  });

  engine.start();
  engine.start();
  assert.equal(scheduler.pending, 1);
  scheduler.fire(117);
  assert.equal(scheduler.pending, 1);
  assert.equal(habitat.projects.length, 1);

  engine.setPaused(true);
  assert.equal(scheduler.pending, 0);
  const stepsAtPause = habitat.steps.length;
  scheduler.fire(10000);
  assert.equal(habitat.steps.length, stepsAtPause);
  assert.equal(habitat.projects.length, 1);
});

test('resume resets timing and zero target rate uses the idle state', () => {
  const scheduler = createScheduler();
  const habitat = createFakeHabitat();
  let currentTime = 0;
  const engine = createHabitatEngine({
    habitat,
    requestFrame: callback => scheduler.request(callback),
    cancelFrame: id => scheduler.cancel(id),
    now: () => currentTime,
  });

  engine.start();
  scheduler.fire(17);
  engine.setPaused(true);
  currentTime = 100000;
  engine.setPaused(false);
  assert.equal(scheduler.pending, 1);
  scheduler.fire(100017);
  assert.ok(habitat.steps.length <= 2);

  engine.setTargetFps(0);
  assert.equal(scheduler.pending, 0);
  const stepsAtIdle = habitat.steps.length;
  scheduler.fire(200000);
  assert.equal(habitat.steps.length, stepsAtIdle);
  engine.setTargetFps(30);
  assert.equal(scheduler.pending, 1);
});

test('pointer input is copied and probe snapshots contain observational metrics', () => {
  const scheduler = createScheduler();
  const habitat = createFakeHabitat();
  const reports = [];
  const engine = createHabitatEngine({
    habitat,
    requestFrame: callback => scheduler.request(callback),
    cancelFrame: id => scheduler.cancel(id),
    now: () => 0,
    onDiagnostics: report => reports.push(report),
  });
  const pointer = { present: true, x: 0.25, y: -0.5, z: 0, eventsReceived: 7 };

  engine.setPointer(pointer);
  pointer.x = 99;
  engine.start();
  scheduler.fire(17);
  const probe = engine.requestProbe();

  assert.equal(habitat.pointerSnapshots[0].x, 0.25);
  assert.deepEqual(probe, {
    fps: 0,
    frameTimeMs: 0,
    fishCount: 10,
    calls: 4,
    triangles: 7200,
    pointerCount: 7,
    reactions: 3,
    paused: false,
    targetFps: 60,
  });
  assert.deepEqual(reports.at(-1), probe);
});

test('diagnostics collection does not change simulation steps or timing', () => {
  const run = onDiagnostics => {
    const scheduler = createScheduler();
    const habitat = createFakeHabitat();
    const engine = createHabitatEngine({
      habitat,
      requestFrame: callback => scheduler.request(callback),
      cancelFrame: id => scheduler.cancel(id),
      now: () => 0,
      diagnosticsIntervalMs: 20,
      onDiagnostics,
    });
    engine.start();
    for (const nowMs of [17, 34, 51, 68, 85]) scheduler.fire(nowMs);
    return { steps: habitat.steps, projects: habitat.projects };
  };

  assert.deepEqual(run(undefined), run(() => {}));
});

test('dispose cancels scheduling and disposes the habitat once', () => {
  const scheduler = createScheduler();
  const habitat = createFakeHabitat();
  const engine = createHabitatEngine({
    habitat,
    requestFrame: callback => scheduler.request(callback),
    cancelFrame: id => scheduler.cancel(id),
    now: () => 0,
  });
  engine.start();
  engine.resize(1920, 1080);
  engine.dispose();
  engine.dispose();
  assert.equal(scheduler.pending, 0);
  assert.deepEqual(habitat.resizeCalls, [[1920, 1080]]);
  assert.equal(habitat.disposed, true);
});

test('performance recorder observes callbacks and actual projections only', () => {
  const scheduler = createScheduler();
  const habitat = createFakeHabitat();
  const events = [];
  const performanceRecorder = {
    enabled: true,
    mark() { events.push('mark'); return 5; },
    recordRender(timestamp) { events.push(['render', timestamp]); },
    finishFrame(start) { events.push(['finish', start]); },
  };
  const engine = createHabitatEngine({
    habitat,
    requestFrame: callback => scheduler.request(callback),
    cancelFrame: id => scheduler.cancel(id),
    now: () => 0,
    targetFps: 30,
    performanceRecorder,
  });

  engine.start();
  scheduler.fire(16.7);
  scheduler.fire(25);
  scheduler.fire(50.1);

  assert.deepEqual(events.filter(event => Array.isArray(event)), [
    ['render', 16.7],
    ['finish', 5],
    ['finish', 5],
    ['render', 50.1],
    ['finish', 5],
  ]);
});
