// Evidence: water-path length and RGB transmittance for real objects of the
// live aquarium, computed from the shipped GLB (vendored GLTFLoader) with the
// runtime's own water model (habitat/shaders/water-volume.js).
//
//   node art/tools/water_depth_report.mjs [out.json]
import { readFile, writeFile } from 'node:fs/promises';
import { registerHooks } from 'node:module';
import * as THREE from '../../habitat/vendor/three/three.module.js';
import { LUSH_LIVE_WATER } from '../../habitat/core/lush-live.js';
import { transmittance, waterPathLength } from '../../habitat/shaders/water-volume.js';

// The vendored loader imports 'three'; resolve it to the vendored build (as
// validate_lush_live_slice.mjs does).
const threeUrl = new URL('../../habitat/vendor/three/three.module.js', import.meta.url).href;
registerHooks({
  resolve(specifier, context, nextResolve) {
    return nextResolve(specifier === 'three' ? threeUrl : specifier, context);
  },
});
const { GLTFLoader } = await import('../../habitat/vendor/three/addons/loaders/GLTFLoader.js');

globalThis.createImageBitmap ??= async () => ({ width: 1, height: 1, close() {} });
globalThis.self ??= globalThis;

const bytes = await readFile(new URL('../../habitat/assets/lush-live/environment.glb', import.meta.url));
const gltf = await new Promise((resolve, reject) => new GLTFLoader().parse(
  bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '', resolve, reject));
gltf.scene.updateMatrixWorld(true);
let camera = null;
gltf.scene.traverse(object => { if (object.isPerspectiveCamera) camera = object; });
const eye = camera.getWorldPosition(new THREE.Vector3());

// Representative objects, front to back (approved source object names).
const WANTED = [
  ['near / front', '07 low foreground plants'],
  ['near / front', 'scattered embedded foreground gravel'],
  ['middle', 'planted central wood.001'],
  ['middle', '05 irregular small leaf bushes'],
  ['middle', '01 flowing ribbon plants'],
  ['rear vegetation', '03 fine feather plants'],
  ['rear boundary', 'blue water background'],
];
const rows = [];
for (const [layer, name] of WANTED) {
  // Exported copies keep their approved source name in glTF extras.
  let object = null;
  gltf.scene.traverse(candidate => {
    if (!object && candidate.userData?.approved_source_object === name) object = candidate;
  });
  if (!object) throw new Error(`object missing: ${name}`);
  const box = new THREE.Box3().setFromObject(object);
  const zs = [];
  // Median depth of the object's vertices (not the box centre).
  object.traverse(child => {
    if (!child.isMesh) return;
    const position = child.geometry.getAttribute('position');
    const v = new THREE.Vector3();
    for (let i = 0; i < position.count; i += Math.max(1, Math.floor(position.count / 4000))) {
      zs.push(v.fromBufferAttribute(position, i).applyMatrix4(child.matrixWorld).clone());
    }
  });
  zs.sort((a, b) => a.z - b.z);
  const median = zs[Math.floor(zs.length / 2)];
  const d = waterPathLength(eye, median, LUSH_LIVE_WATER.glassZ);
  const t = transmittance(LUSH_LIVE_WATER.sigma, d, LUSH_LIVE_WATER.referenceDistance);
  rows.push({
    layer, object: name,
    zRange: [box.min.z, box.max.z].map(v => +v.toFixed(2)),
    medianPoint: median.toArray().map(v => +v.toFixed(2)),
    waterPath: +d.toFixed(2),
    transmittanceRGB: t.map(v => +v.toFixed(3)),
  });
}
const report = {
  camera: eye.toArray().map(v => +v.toFixed(3)),
  glassZ: LUSH_LIVE_WATER.glassZ,
  sigmaRGB: LUSH_LIVE_WATER.sigma,
  referenceDistance: LUSH_LIVE_WATER.referenceDistance,
  scatterColorLinear: LUSH_LIVE_WATER.scatterColor,
  rows,
};
const out = process.argv[2];
if (out) await writeFile(out, `${JSON.stringify(report, null, 2)}\n`);
for (const row of rows) {
  console.log(`${row.layer.padEnd(16)} ${row.object.padEnd(38)} z ${String(row.zRange).padEnd(14)} path ${String(row.waterPath).padStart(5)}  T ${row.transmittanceRGB.join(' / ')}`);
}
