import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../../habitat/vendor/three/three.module.js';
import {
  DEFAULT_WATER_MODE,
  applyWater,
  createWaterVolume,
  injectWater,
  readWaterMode,
  transmittance,
  waterPathLength,
} from '../../habitat/shaders/water-volume.js';
import { LUSH_LIVE_WATER, createLushLiveEnvironment } from '../../habitat/core/lush-live.js';
import { createHeroFishRenderer } from '../../habitat/core/hero-fish.js';

const CAMERA = { x: 0, y: 6.6, z: 15.3 };
const GLASS = 5;
const params = mode => ({ ...LUSH_LIVE_WATER, mode });

function libShader(name) {
  const lib = THREE.ShaderLib[name];
  return {
    uniforms: THREE.UniformsUtils.clone(lib.uniforms),
    vertexShader: lib.vertexShader,
    fragmentShader: lib.fragmentShader,
  };
}

test('only the glass-to-fragment segment counts as water', () => {
  // A point on the glass: no water at all; in front of the glass: air.
  assert.equal(waterPathLength(CAMERA, { x: 0, y: 3, z: GLASS }, GLASS), 0);
  assert.equal(waterPathLength(CAMERA, { x: 0, y: 3, z: GLASS + 1 }, GLASS), 0);
  // Just behind the glass: a tiny path, not the camera distance.
  const near = waterPathLength(CAMERA, { x: 0, y: 3, z: GLASS - 0.01 }, GLASS);
  assert.ok(near > 0 && near < 0.02, `near ${near}`);
  // Straight-on ray: exactly the depth behind the glass.
  assert.ok(Math.abs(waterPathLength({ x: 0, y: 3, z: 15 }, { x: 0, y: 3, z: -4 }, GLASS) - 9) < 1e-9);
  // Camera underwater: the whole segment is water.
  assert.ok(Math.abs(waterPathLength({ x: 0, y: 0, z: 0 }, { x: 0, y: 0, z: -3 }, GLASS) - 3) < 1e-9);
});

test('water path grows monotonically with scene depth', () => {
  let previous = -1;
  for (let z = GLASS; z >= -4.8; z -= 0.4) {
    const d = waterPathLength(CAMERA, { x: 1.5, y: 1, z }, GLASS);
    assert.ok(d > previous, `z ${z}`);
    previous = d;
  }
});

test('transmittance is bounded, per channel, red lost first, never brightening', () => {
  const [r, g, b] = transmittance(LUSH_LIVE_WATER.sigma, 11, LUSH_LIVE_WATER.referenceDistance);
  assert.ok(r < g && g < b, 'red attenuates fastest, blue least');
  assert.ok(r > 0.3 && b < 1, 'rear is attenuated but not crushed');
  assert.deepEqual(transmittance(LUSH_LIVE_WATER.sigma, 1, LUSH_LIVE_WATER.referenceDistance), [1, 1, 1]);
  for (const bad of [[0.1, 0.1], [0.1, NaN, 0.1], [-0.1, 0.1, 0.1], [9, 0.1, 0.1]]) {
    assert.throws(() => createWaterVolume({ ...params('full'), sigma: bad }), RangeError);
  }
  assert.throws(() => createWaterVolume({ ...params('full'), scatterColor: [Infinity, 0, 0] }), RangeError);
  assert.throws(() => createWaterVolume({ ...params('full'), mode: 'fog' }), RangeError);
});

test('debug modes: off disables, extinction drops scattering, full keeps both', () => {
  assert.equal(DEFAULT_WATER_MODE, 'full');
  assert.equal(readWaterMode({ search: '' }), 'full');
  assert.equal(readWaterMode({ search: '?water=off' }), 'off');
  assert.equal(readWaterMode({ search: '?water=extinction' }), 'extinction');
  assert.equal(readWaterMode({ search: '?water=fog' }), 'full');
  assert.equal(createWaterVolume(params('off')).enabled, false);
  assert.deepEqual(createWaterVolume(params('extinction')).uniforms.uWaterScatter.value, [0, 0, 0]);
  assert.ok(createWaterVolume(params('full')).uniforms.uWaterScatter.value.every(v => v > 0));
});

test('injection targets the lit colour in the real three.js chunks, with instancing-aware world position', () => {
  const water = createWaterVolume(params('full'));
  for (const lib of ['standard', 'physical', 'basic']) {
    const shader = injectWater(libShader(lib), water);
    assert.match(shader.vertexShader, /instanceMatrix \* waterWorld/);
    assert.match(shader.vertexShader, /#include <project_vertex>\s+vec4 waterWorld[\s\S]*waterAt\(waterWorld\.xyz, vWaterT, vWaterIn\)/);
    assert.match(shader.fragmentShader, /outgoingLight = outgoingLight \* vWaterT \+ vWaterIn;\s+#include <opaque_fragment>/);
    assert.ok(shader.uniforms.uWaterSigma && shader.uniforms.uWaterGlassZ);
    const exact = injectWater(libShader(lib), water, { perFragment: true });
    assert.match(exact.fragmentShader, /waterAt\(vWaterWorld, waterT, waterIn\)[\s\S]*#include <opaque_fragment>/);
  }
  const untouched = libShader('standard');
  const original = untouched.fragmentShader;
  injectWater(untouched, createWaterVolume(params('off')));
  assert.equal(untouched.fragmentShader, original);
});

test('applyWater keeps alpha test, depth, sidedness and chains existing shader hooks', () => {
  const water = createWaterVolume(params('full'));
  const material = new THREE.MeshStandardMaterial({ alphaTest: 0.45, side: THREE.DoubleSide });
  let previousRan = false;
  material.onBeforeCompile = () => { previousRan = true; };
  material.customProgramCacheKey = () => 'leaf';
  applyWater(material, water);
  const shader = libShader('standard');
  material.onBeforeCompile(shader);
  assert.ok(previousRan);
  assert.match(shader.fragmentShader, /vWaterT/);
  assert.equal(material.alphaTest, 0.45);
  assert.equal(material.side, THREE.DoubleSide);
  assert.ok(material.depthTest && material.depthWrite && !material.transparent);
  assert.equal(material.customProgramCacheKey(), 'leaf|water:full');
});

test('live aquarium waters every environment material once and hands the same water to the fish', () => {
  const scene = new THREE.Scene();
  const root = new THREE.Group();
  root.add(new THREE.PerspectiveCamera(23.8, 16 / 9, 0.1, 1000));
  const shared = new THREE.MeshStandardMaterial({ alphaTest: 0.45, side: THREE.DoubleSide });
  for (let i = 0; i < 12; i += 1) root.add(new THREE.Mesh(new THREE.BoxGeometry(), shared));
  const environment = createLushLiveEnvironment(scene, { sceneGraphs: { 'lush-live/environment.glb': root } },
    { waterMode: 'full' });
  assert.equal(environment.water.mode, 'full');
  assert.equal(environment.fishPalette, 'freshwater-approved');
  assert.equal(shared.customProgramCacheKey().split('water:full').length - 1, 1, 'shared material wrapped once');
  assert.equal(shared.alphaTest, 0.45);
  const off = createLushLiveEnvironment(new THREE.Scene(), {
    sceneGraphs: { 'lush-live/environment.glb': root.clone() },
  }, { waterMode: 'off' });
  assert.equal(off.water.enabled, false);

  const fishScene = new THREE.Scene();
  const fish = createHeroFishRenderer(fishScene, {
    capacity: 3, palette: 'freshwater-approved', water: environment.water,
  });
  const materials = fishScene.children.filter(child => child.isInstancedMesh).map(mesh => mesh.material);
  assert.equal(materials.length, 2);
  for (const material of materials) {
    assert.match(material.customProgramCacheKey(), /freshwater-approved.*\|water:full$/);
  }
  const body = libShader('physical');
  materials[0].onBeforeCompile(body);
  assert.match(body.fragmentShader, /hfApprovedBand/);
  assert.match(body.vertexShader, /waterPath/);
  assert.match(body.vertexShader, /instanceMatrix \* waterWorld/);
  fish.dispose?.();
  environment.dispose();
  off.dispose();
});
