import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../../habitat/vendor/three/three.module.js';
import {
  FOLIAGE_FAMILIES,
  LUSH_LIVE_LIGHTS,
  REAR_WATER,
  SAND_FACTOR,
  createLushLiveLights,
  createRearMaterial,
  rearColorAt,
  recoverMaterials,
} from '../../habitat/core/lush-live-look.js';
import { LUSH_LIVE_WATER } from '../../habitat/core/lush-live.js';

function family(name, material) {
  const group = new THREE.Group();
  group.userData.approved_source_object = name;
  group.add(new THREE.Mesh(new THREE.BoxGeometry(), material));
  return group;
}

const leafLight = () => ({ direction: { value: new THREE.Vector3(0, 1, 0) }, color: { value: new THREE.Color(1, 1, 1) } });

test('water extinction constants stay protected in this pass', () => {
  assert.deepEqual(LUSH_LIVE_WATER.sigma, [0.13, 0.08, 0.058]);
  assert.equal(LUSH_LIVE_WATER.glassZ, 5);
  assert.equal(LUSH_LIVE_WATER.referenceDistance, 3.5);
});

test('material recovery: per-family clones, pale sand, foliage two-sided with transmission', () => {
  const root = new THREE.Group();
  const leaf = new THREE.MeshStandardMaterial({ color: new THREE.Color(0.05, 0.2, 0.02), alphaTest: 0.45 });
  leaf.name = 'leaf-0-1.001';
  const gravel = new THREE.MeshStandardMaterial({ color: new THREE.Color(0.18, 0.17, 0.14) });
  gravel.name = 'gravel 1.001';
  root.add(family('07 low foreground plants', leaf), family('03 fine feather plants', leaf),
    family('fine gravel openings', gravel));
  const created = recoverMaterials(root, { leafLight: leafLight() });
  assert.equal(created.length, 3, 'the shared leaf material becomes one instance per family');
  const [front, feather, sand] = root.children.map(group => group.children[0].material);
  assert.notEqual(front, feather);
  assert.notEqual(front, leaf, 'source material untouched');
  assert.ok(Math.abs(leaf.color.g - 0.2) < 1e-6);
  for (const material of [front, feather]) {
    assert.equal(material.side, THREE.DoubleSide);
    assert.equal(material.alphaTest, 0.45);
    assert.ok(material.depthWrite && material.depthTest && !material.transparent);
    assert.ok(material.userData.leafTransmission > 0);
  }
  // Differentiation: the feather plants are lighter/yellower than the front plants.
  assert.ok(feather.color.r / feather.color.g > front.color.r / front.color.g);
  assert.ok(Math.abs(sand.color.r - 0.18 * SAND_FACTOR[0]) < 1e-6);
  const shader = {
    uniforms: {}, vertexShader: THREE.ShaderLib.standard.vertexShader, fragmentShader: THREE.ShaderLib.standard.fragmentShader,
  };
  front.onBeforeCompile(shader);
  assert.match(shader.fragmentShader, /leafBack[\s\S]*#include <opaque_fragment>/);
  assert.ok(shader.uniforms.uLeafTransmission.value > 0);
  for (const name of Object.keys(FOLIAGE_FAMILIES)) assert.ok(FOLIAGE_FAMILIES[name].transmission <= 0.6);
});

test('rear boundary: real geometry, lighter above, deeper below, bounded analytic variation', () => {
  const top = rearColorAt(1);
  const bottom = rearColorAt(0);
  assert.ok(top.r + top.g + top.b > 2 * (bottom.r + bottom.g + bottom.b));
  assert.ok(top.b > top.r && top.g > top.r, 'blue-green water, not grey');
  assert.ok(REAR_WATER.variation <= 0.05);
  const geometry = new THREE.PlaneGeometry(17, 8, 1, 1);
  const material = createRearMaterial(geometry);
  assert.ok(material.isMeshBasicMaterial && material.vertexColors);
  assert.ok(geometry.hasAttribute('color'));
  assert.equal(material.map, null, 'no texture');
});

test('lighting: overhead lamp key above the tank, one fill, no shadows, neutral tone mapping', () => {
  const { key, lights } = createLushLiveLights();
  assert.ok(key.isSpotLight && key.position.y > 8);
  assert.ok(lights.some(light => light.isHemisphereLight));
  assert.ok(lights.filter(light => light.isDirectionalLight).length <= 1, 'lights are a per-fragment cost');
  assert.ok(lights.every(light => !light.castShadow));
  assert.equal(LUSH_LIVE_LIGHTS.toneMapping, 'neutral');
  assert.ok(LUSH_LIVE_LIGHTS.exposure >= 1 && LUSH_LIVE_LIGHTS.exposure <= 1.6);
});
