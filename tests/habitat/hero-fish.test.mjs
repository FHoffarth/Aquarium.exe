import test from 'node:test';
import assert from 'node:assert/strict';

import * as THREE from '../../habitat/vendor/three/three.module.js';
import { createSchool } from '../../habitat/core/behavior.js';
import { deriveFishVisualState } from '../../habitat/core/fish.js';
import {
  PART,
  buildHeroFishGeometry,
  createHeroFishRenderer,
  createHeroStudio,
  createSwimAnimator,
  orientationBasis,
  readHeroFishConfig,
  station,
} from '../../habitat/core/hero-fish.js';
import { createEffectUniforms } from '../../habitat/shaders/material-effects.js';
import { createPlantedTankConfig } from '../../habitat/habitats/planted-tank/config.js';

function allFinite(array) {
  return Array.prototype.every.call(array, Number.isFinite);
}

test('hero anatomy is slender, peaks over the forward trunk and tapers into a thin peduncle', () => {
  const depth = s => station(s).top + station(s).bottom;
  const peak = [0.1, 0.2, 0.3, 0.37, 0.45, 0.55, 0.7].reduce((best, s) => (depth(s) > depth(best) ? s : best));
  assert.ok(depth(peak) > 0.17 && depth(peak) < 0.23, `slender body depth ${depth(peak)}`);
  assert.ok(peak >= 0.3 && peak <= 0.45, `greatest depth over the forward trunk (${peak})`);
  assert.ok(depth(0.1) < depth(peak) * 0.6, 'small head');
  assert.ok(station(0.37).bottom < station(0.37).top, 'shallow belly line');
  assert.ok(depth(0.9) < depth(0.4) * 0.35, 'thin peduncle');
  assert.ok(depth(1) > depth(0.9), 'caudal base flares from the peduncle');
  assert.ok(station(0.9).width < station(0.4).width * 0.35, 'peduncle is laterally thin');
});

test('hero geometry carries finite, well-formed shared attributes', () => {
  const { body, fins } = buildHeroFishGeometry();
  for (const geometry of [body, fins]) {
    for (const name of ['position', 'normal', 'uv', 'aPart', 'aProgress', 'aSurface']) {
      assert.ok(geometry.attributes[name], `${name} present`);
      assert.ok(allFinite(geometry.attributes[name].array), `${name} finite`);
    }
    const count = geometry.attributes.position.count;
    assert.ok(Array.prototype.every.call(geometry.index.array, i => i >= 0 && i < count));
    const progress = geometry.attributes.aProgress.array;
    assert.ok(Array.prototype.every.call(progress, p => p >= 0 && p <= 1));
  }
  const bodyParts = new Set(body.attributes.aPart.array);
  const finParts = new Set(fins.attributes.aPart.array);
  assert.deepEqual([...bodyParts].sort(), [PART.body, PART.eye]);
  for (const part of ['caudal', 'dorsal', 'adipose', 'anal', 'pelvicL', 'pelvicR', 'pectoralL', 'pectoralR']) {
    assert.ok(finParts.has(PART[part]), `${part} fin present`);
  }
  // A small-fish budget: well under 5k triangles for body, eyes and fins.
  assert.ok(body.index.count / 3 + fins.index.count / 3 < 5000);
});

test('instanced hero renderer respects capacity and writes finite per-fish attributes', () => {
  const scene = new THREE.Scene();
  const school = createSchool(createPlantedTankConfig({ fishCount: 8 }));
  const hero = createHeroFishRenderer(scene, { capacity: 3, effectUniforms: createEffectUniforms() });
  const { bodies, membranes } = hero.meshes;
  assert.equal(bodies.isInstancedMesh, true);
  assert.equal(membranes.isInstancedMesh, true);
  assert.equal(bodies.geometry.attributes.aSwim.array.length, 3 * 4);
  assert.equal(bodies.geometry.attributes.aFin.array.length, 3 * 2);
  assert.equal(bodies.geometry.attributes.aSwim, membranes.geometry.attributes.aSwim);

  for (let frame = 0; frame < 30; frame += 1) hero.project(school.fish, frame / 60);
  assert.equal(bodies.count, 3);
  assert.equal(membranes.count, 3);
  assert.ok(allFinite(bodies.instanceMatrix.array));
  assert.ok(allFinite(bodies.geometry.attributes.aSwim.array));
  assert.ok(allFinite(bodies.geometry.attributes.aFin.array));
  hero.dispose();
  assert.equal(scene.children.length, 0);
});

test('hero projection never mutates simulation state', () => {
  const scene = new THREE.Scene();
  const school = createSchool(createPlantedTankConfig({ fishCount: 8 }));
  const before = structuredClone(school);
  const hero = createHeroFishRenderer(scene, { capacity: 4 });
  for (let frame = 0; frame < 10; frame += 1) hero.project(school.fish, frame / 30);
  assert.deepEqual(school, before);
  // The production projection contract is unchanged by the hero renderer.
  assert.ok(!('swimPhase' in deriveFishVisualState(school.fish[0], 1)));
  hero.dispose();
});

test('swim animator stays finite and upright for degenerate and reversing motion', () => {
  const animate = createSwimAnimator();
  const fish = { position: { x: 0, y: 0, z: 0 }, velocity: { x: 0, y: 0, z: 0 }, maximumSpeed: 0.4, visualPhase: 1 };
  const cases = [
    [0, 0, 0], [0, 0.3, 0], [0, -0.3, 0], [-0.3, 0, 0], [0.3, 0, 0], [-0.3, 0.1, 0], [1e-9, 0, -1e-9],
  ];
  let time = 0;
  const basis = new THREE.Matrix4();
  const up = new THREE.Vector3();
  for (const [x, y, z] of cases) {
    fish.velocity = { x, y, z };
    for (let frame = 0; frame < 90; frame += 1) {
      time += 1 / 60;
      const state = animate(0, fish, time);
      assert.ok(Object.values(state).every(Number.isFinite), JSON.stringify(state));
      orientationBasis(state.yaw, state.pitch, basis);
      basis.extractBasis(new THREE.Vector3(), up, new THREE.Vector3());
      assert.ok(up.y > 0.8, 'dorsal side stays up (production rolls left-swimmers upside down)');
    }
  }
  // Large simulation gaps are clamped rather than exploding the phase.
  const state = animate(0, fish, time + 1000);
  assert.ok(Object.values(state).every(Number.isFinite));
});

test('turning produces a C-bend and braking engages the pectorals', () => {
  const animate = createSwimAnimator();
  const fish = { position: { x: 0, y: 0, z: 0 }, velocity: { x: 0.3, y: 0, z: 0 }, maximumSpeed: 0.4 };
  let time = 0;
  let state;
  for (let frame = 0; frame < 60; frame += 1) {
    time += 1 / 60;
    const yaw = frame * 0.03;
    fish.velocity = { x: Math.cos(yaw) * 0.3, y: 0, z: Math.sin(yaw) * 0.3 };
    state = animate(0, fish, time);
  }
  assert.ok(state.curvature > 0.5, `turning curvature ${state.curvature}`);
  for (let frame = 0; frame < 30; frame += 1) {
    time += 1 / 60;
    fish.velocity = { x: fish.velocity.x * 0.9, y: 0, z: fish.velocity.z * 0.9 };
    state = animate(0, fish, time);
  }
  assert.ok(state.brake > 0.1, `brake ${state.brake}`);
  assert.ok(state.hover > 0.5, 'slow fish hovers');
});

test('hero shader injection reaches every anchor for body and membranes', () => {
  const scene = new THREE.Scene();
  const hero = createHeroFishRenderer(scene, { effectUniforms: createEffectUniforms() });
  for (const [mesh, lib] of [[hero.meshes.bodies, THREE.ShaderLib.physical],
    [hero.meshes.membranes, THREE.ShaderLib.standard]]) {
    const shader = {
      uniforms: THREE.UniformsUtils.clone(lib.uniforms),
      vertexShader: lib.vertexShader,
      fragmentShader: lib.fragmentShader,
    };
    mesh.material.onBeforeCompile(shader);
    assert.match(shader.vertexShader, /hfBend\(hfFinMotion\(position/);
    assert.match(shader.vertexShader, /attribute vec4 aSwim/);
    assert.doesNotMatch(shader.vertexShader, /#include <begin_vertex>/);
    assert.match(shader.fragmentShader, /varying float vFishPart/);
    assert.match(shader.fragmentShader, /outgoingLight \+=/);
    assert.ok(shader.uniforms.uEffectTime, 'caustics/haze shared uniforms bound');
    if (mesh === hero.meshes.bodies) {
      assert.match(shader.fragmentShader, /metalnessFactor = 0\.75 \* irisMetal/);
      assert.match(shader.fragmentShader, /material\.clearcoat = smoothstep/);
    }
  }
  hero.dispose();
});

test('hero review config is off by default and strictly parsed', () => {
  assert.equal(readHeroFishConfig({ search: '' }).enabled, false);
  assert.equal(readHeroFishConfig(undefined).enabled, false);
  const config = readHeroFishConfig({ search: '?heroFish=1&heroScale=99&heroGait=warp&heroAt=1,2' });
  assert.equal(config.enabled, true);
  assert.equal(config.variant, 'hero');
  assert.equal(config.scale, 4);
  assert.equal(config.gait, 'auto');
  assert.deepEqual(config.at, [0.4, 0.15, 0.25]);
  assert.equal(readHeroFishConfig({ search: '?heroFish=1&heroVariant=production' }).variant, 'production');
  assert.equal(readHeroFishConfig({ search: '?heroFish=1&heroGait=turn&heroYaw=90' }).yaw, Math.PI / 2);
});

test('review studio stand-in is a copy and leaves the simulated fish untouched', () => {
  const school = createSchool(createPlantedTankConfig({ fishCount: 8 }));
  const before = structuredClone(school.fish[2]);
  const studio = createHeroStudio(school.fish[2], readHeroFishConfig({ search: '?heroFish=1&heroStudio=1' }));
  for (let t = 0; t < 20; t += 0.25) {
    const fish = studio.update(t);
    assert.ok([fish.position.x, fish.position.y, fish.position.z, fish.velocity.x].every(Number.isFinite));
  }
  assert.deepEqual(school.fish[2], before);
});
