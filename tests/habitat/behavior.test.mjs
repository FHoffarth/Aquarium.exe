import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createPointerState,
  createSchool,
  stepSchool,
} from '../../habitat/core/behavior.js';
import {
  createPlantedTankConfig,
  validatePlantedTankConfig,
} from '../../habitat/habitats/planted-tank/config.js';

function moveOtherFishAway(school, keep = 2) {
  for (let index = keep; index < school.fish.length; index += 1) {
    school.fish[index].position = { x: 2.4, y: 1.1, z: 0.5 };
    school.fish[index].velocity = { x: 0, y: 0, z: 0 };
  }
}

function quietFish(fish) {
  fish.velocity = { x: 0, y: 0, z: 0 };
  fish.wanderStrength = 0;
  fish.cohesionWeight = 0;
  fish.alignmentWeight = 0;
  fish.separationWeight = 0;
  fish.depthWeight = 0;
}

test('same seed creates the same school', () => {
  const config = createPlantedTankConfig({ seed: 20260921, fishCount: 10 });
  assert.deepEqual(createSchool(config), createSchool(config));
});

test('different seeds create different personality variation', () => {
  const first = createSchool(createPlantedTankConfig({ seed: 1 })).fish[0].personality;
  const second = createSchool(createPlantedTankConfig({ seed: 2 })).fish[0].personality;
  assert.notDeepEqual(first, second);
});

test('population and behavior ranges are validated', () => {
  assert.throws(() => createPlantedTankConfig({ fishCount: 7 }), RangeError);
  assert.throws(() => createPlantedTankConfig({ fishCount: 13 }), RangeError);
  const config = createPlantedTankConfig();
  const invalid = {
    ...config,
    fish: { ...config.fish, separationRadius: [1, 0.5] },
  };
  assert.throws(() => validatePlantedTankConfig(invalid), RangeError);
});

test('pointer state starts absent and counts updates', () => {
  assert.deepEqual(createPointerState(), {
    present: false,
    x: 0,
    y: 0,
    z: 0,
    eventsReceived: 0,
  });
});

test('steering remains finite and bounded at zero separation', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  school.fish[1].position = { ...school.fish[0].position };
  stepSchool(school, createPointerState(), 1 / 60, config.bounds);
  for (const fish of school.fish) {
    assert.ok(Object.values(fish.position).every(Number.isFinite));
    assert.ok(Object.values(fish.velocity).every(Number.isFinite));
    assert.ok(
      Math.hypot(fish.velocity.x, fish.velocity.y, fish.velocity.z)
        <= fish.maximumSpeed + 1e-9,
    );
  }
});

test('close neighbors receive opposing separation steering', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  moveOtherFishAway(school);
  const left = school.fish[0];
  const right = school.fish[1];
  quietFish(left);
  quietFish(right);
  left.separationWeight = 2;
  right.separationWeight = 2;
  left.position = { x: -0.02, y: 0, z: 0 };
  right.position = { x: 0.02, y: 0, z: 0 };
  left.separationRadius = right.separationRadius = 0.4;

  stepSchool(school, createPointerState(), 1 / 30, config.bounds);

  assert.ok(left.velocity.x < 0);
  assert.ok(right.velocity.x > 0);
});

test('an isolated fish receives cohesion toward nearby schoolmates', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  moveOtherFishAway(school);
  const subject = school.fish[0];
  const neighbor = school.fish[1];
  quietFish(subject);
  quietFish(neighbor);
  subject.cohesionWeight = 1.5;
  subject.neighborRadius = 2;
  subject.position = { x: -0.8, y: 0, z: 0 };
  neighbor.position = { x: 0.2, y: 0, z: 0 };

  stepSchool(school, createPointerState(), 1 / 30, config.bounds);

  assert.ok(subject.velocity.x > 0);
});

test('curious fish approach a noticed pointer more than cautious fish', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  moveOtherFishAway(school);
  const curious = school.fish[0];
  const cautious = school.fish[1];
  quietFish(curious);
  quietFish(cautious);
  // Isolate cursor steering from the normal minimum cruise-speed maintenance.
  curious.preferredSpeed = cautious.preferredSpeed = 0;
  curious.position = { x: 0, y: -0.2, z: 0 };
  cautious.position = { x: 0, y: 0.2, z: 0 };
  curious.personality = { schooling: 0.2, curiosity: 1, caution: 0 };
  cautious.personality = { schooling: 0.2, curiosity: 0, caution: 1 };
  curious.cursorNoticeRadius = cautious.cursorNoticeRadius = 1.4;
  curious.cursorThreatRadius = cautious.cursorThreatRadius = 0.25;
  const pointer = { present: true, x: 0.8, y: 0, z: 0, eventsReceived: 1 };

  for (let step = 0; step < 15; step += 1) {
    stepSchool(school, pointer, 1 / 60, config.bounds);
  }

  assert.ok(curious.velocity.x > cautious.velocity.x);
  assert.ok(curious.velocity.x > 0);
});

test('a close pointer causes smooth bounded avoidance', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  moveOtherFishAway(school, 1);
  const subject = school.fish[0];
  quietFish(subject);
  subject.position = { x: 0, y: 0, z: 0 };
  subject.cursorThreatRadius = 0.5;
  const pointer = { present: true, x: 0.05, y: 0, z: 0, eventsReceived: 1 };

  stepSchool(school, pointer, 1 / 60, config.bounds);

  assert.ok(subject.velocity.x < 0);
  assert.ok(Math.abs(subject.velocity.x) <= subject.maximumSpeed);
  assert.ok(subject.cursorAwareness > 0);
});

test('pointer-out decays awareness and temporary response speed', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  const subject = school.fish[0];
  subject.cursorAwareness = 1;
  subject.cursorBoost = 1;
  const absent = createPointerState();

  for (let step = 0; step < 120; step += 1) {
    stepSchool(school, absent, 1 / 60, config.bounds);
  }

  assert.ok(subject.cursorAwareness < 0.05);
  assert.ok(subject.cursorBoost < 0.05);
});

test('soft boundary and depth forces point toward the habitat', () => {
  const config = createPlantedTankConfig({ fishCount: 8 });
  const school = createSchool(config);
  moveOtherFishAway(school, 1);
  const subject = school.fish[0];
  quietFish(subject);
  subject.position = {
    x: config.bounds.maxX - 0.01,
    y: config.bounds.maxY - 0.01,
    z: config.bounds.maxZ - 0.01,
  };
  subject.velocity = { x: 0.1, y: 0.1, z: 0.1 };
  subject.depthPreference = config.bounds.minZ;

  stepSchool(school, createPointerState(), 0.1, config.bounds);

  assert.ok(subject.velocity.x < 0.1);
  assert.ok(subject.velocity.y < 0.1);
  assert.ok(subject.velocity.z < 0.1);
});

test('identical input sequences remain deterministic', () => {
  const config = createPlantedTankConfig({ seed: 8675309, fishCount: 10 });
  const first = createSchool(config);
  const second = createSchool(config);
  for (let step = 0; step < 180; step += 1) {
    const pointer = step < 60
      ? { present: true, x: 0.4, y: -0.1, z: 0, eventsReceived: step + 1 }
      : createPointerState();
    stepSchool(first, pointer, 1 / 60, config.bounds);
    stepSchool(second, pointer, 1 / 60, config.bounds);
  }
  assert.deepEqual(first, second);
});
