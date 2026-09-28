// Inspect the exported proof with the same vendored GLTFLoader used by runtime.
// Node has no image decoder. The bitmap stub allows loader parsing; image
// formats and dimensions are checked independently from GLB buffer views.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { registerHooks } from 'node:module';
import * as THREE from '../../habitat/vendor/three/three.module.js';

const threeUrl = new URL('../../habitat/vendor/three/three.module.js', import.meta.url).href;
registerHooks({
  resolve(specifier, context, nextResolve) {
    return nextResolve(specifier === 'three' ? threeUrl : specifier, context);
  },
});
const { GLTFLoader } = await import('../../habitat/vendor/three/addons/loaders/GLTFLoader.js');

const asset = new URL('../../habitat/assets/lush-slice/environment.glb', import.meta.url);
const bytes = new Uint8Array(await readFile(asset));
const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
assert.equal(view.getUint32(0, true), 0x46546c67, 'GLB magic');
assert.equal(view.getUint32(4, true), 2, 'glTF version');
assert.equal(view.getUint32(8, true), bytes.length, 'GLB length');
const jsonLength = view.getUint32(12, true);
assert.equal(view.getUint32(16, true), 0x4e4f534a, 'JSON chunk');
const gltfJson = JSON.parse(new TextDecoder().decode(bytes.subarray(20, 20 + jsonLength)));
const binHeader = 20 + jsonLength;
assert.equal(view.getUint32(binHeader + 4, true), 0x004e4942, 'BIN chunk');
const binStart = binHeader + 8;

function webpSize(data) {
  assert.equal(new TextDecoder().decode(data.subarray(0, 4)), 'RIFF');
  assert.equal(new TextDecoder().decode(data.subarray(8, 12)), 'WEBP');
  const tag = new TextDecoder().decode(data.subarray(12, 16));
  if (tag === 'VP8X') return [1 + (data[24] | data[25] << 8 | data[26] << 16),
    1 + (data[27] | data[28] << 8 | data[29] << 16)];
  if (tag === 'VP8L') {
    const bits = data[21] | data[22] << 8 | data[23] << 16 | data[24] << 24;
    return [(bits & 0x3fff) + 1, ((bits >>> 14) & 0x3fff) + 1];
  }
  if (tag === 'VP8 ') return [data[26] | data[27] << 8, data[28] | data[29] << 8];
  throw new Error(`unsupported embedded WebP chunk: ${tag}`);
}

const images = (gltfJson.images ?? []).map(image => {
  const segment = gltfJson.bufferViews[image.bufferView];
  const data = bytes.subarray(binStart + (segment.byteOffset ?? 0),
    binStart + (segment.byteOffset ?? 0) + segment.byteLength);
  assert.equal(image.mimeType, 'image/webp');
  const [width, height] = webpSize(data);
  return { name: image.name, width, height, bytes: data.length, mimeType: image.mimeType };
});
assert.deepEqual(images.map(image => image.name).sort(),
  ['leaves_albedo', 'rock09_albedo', 'wood_albedo'], 'only reusable source textures are embedded');

// Three's ImageBitmapLoader can parse materials without a browser canvas.
globalThis.self = globalThis;
globalThis.createImageBitmap = async () => ({ width: 1, height: 1, close() {} });
const parsed = await new Promise((resolve, reject) => {
  new GLTFLoader().parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
    '', resolve, reject);
});
const renderMeshes = [];
parsed.scene.traverse(object => { if (object.isMesh) renderMeshes.push(object); });
const bounds = new THREE.Box3().setFromObject(parsed.scene);
assert.ok(bounds.min.x < bounds.max.x && bounds.min.y < bounds.max.y && bounds.min.z < bounds.max.z);

const metadata = parsed.scene.getObjectByName('lush-slice-metadata')?.userData;
assert.ok(metadata, 'metadata empty survives vendored loader');
assert.equal(metadata.front_glass_y_blender, -5);
assert.equal(metadata.front_glass_z_three, 5);
assert.equal(metadata.rear_y_blender, 4.8);
assert.ok(parsed.cameras.length === 1, 'approved camera is present');
const camera = parsed.cameras[0];
const cameraPosition = camera.getWorldPosition(new THREE.Vector3());
assert.ok(Math.abs(cameraPosition.y - 6.6) < 0.01);
assert.ok(Math.abs(cameraPosition.z - 15.3) < 0.01);

const nodeNames = gltfJson.nodes.map(node => node.name ?? '');
assert.ok(nodeNames.every(name => !/^hero-|^sparse water particle/i.test(name)),
  'posed fish and offline particles excluded');
assert.ok(nodeNames.every(name => !/environment_albedo|static environment plate/i.test(name)),
  'environment plate excluded');
for (const family of ['low foreground plants', 'irregular small leaf bushes',
  'fine feather plants', 'natural gravel bed', 'planted central wood',
  'partly buried rock-09', 'blue water background']) {
  assert.ok(nodeNames.some(name => name.includes(family)), `${family} present`);
}
const depth = name => {
  const matches = renderMeshes.filter(mesh => mesh.name.includes(name.replaceAll(' ', '_')));
  assert.ok(matches.length, `${name} loaded`);
  const box = new THREE.Box3();
  for (const mesh of matches) box.union(new THREE.Box3().setFromObject(mesh));
  return [box.min.z, box.max.z];
};
const foregroundDepth = depth('low foreground plants');
const midgroundDepth = depth('irregular small leaf bushes');
const backgroundDepth = depth('fine feather plants');
const rearDepth = depth('blue water background');
assert.ok(foregroundDepth[1] > midgroundDepth[1]);
assert.ok(midgroundDepth[1] > backgroundDepth[1]);
assert.ok(backgroundDepth[0] > rearDepth[1]);

const broad = gltfJson.materials.find(material => material.name?.includes('photographed broad leaf surfaces'));
assert.equal(broad?.alphaMode, 'MASK', 'cutout depth writes');
assert.equal(broad?.doubleSided, true, 'broad leaves are double sided');
assert.ok(Math.abs(broad.alphaCutoff - 0.45) < 0.001);
const loadedBroad = renderMeshes.find(mesh => mesh.material.name.includes('photographed broad leaf surfaces'));
assert.ok(loadedBroad, 'broad-leaf material loaded');
assert.equal(loadedBroad.material.depthWrite, true);
assert.ok(loadedBroad.material.alphaTest > 0.44 && loadedBroad.material.alphaTest < 0.46);

const primitives = gltfJson.meshes.flatMap(mesh => mesh.primitives);
const triangles = primitives.reduce((sum, primitive) => sum +
  gltfJson.accessors[primitive.indices].count / 3, 0);
const vertices = primitives.reduce((sum, primitive) => sum +
  gltfJson.accessors[primitive.attributes.POSITION].count, 0);
const round = vector => vector.toArray().map(value => Number(value.toFixed(4)));
const report = {
  file: asset.pathname, bytes: bytes.length, sourceMeshes: gltfJson.meshes.length,
  renderMeshes: renderMeshes.length, primitives: primitives.length,
  materials: gltfJson.materials.length, triangles, vertices,
  textures: images, bboxThree: { min: round(bounds.min), max: round(bounds.max) },
  camera: { name: camera.name, positionThree: round(cameraPosition),
    verticalFovDegrees: Number((camera.fov).toFixed(4)), aspect: camera.aspect },
  frontGlass: { blenderY: metadata.front_glass_y_blender,
    threeZ: metadata.front_glass_z_three },
  sliceX: [metadata.slice_x_min_blender, metadata.slice_x_max_blender],
  depthThreeZ: { foreground: foregroundDepth, midground: midgroundDepth,
    background: backgroundDepth, rear: rearDepth },
  excluded: { posedFish: true, offlineParticles: true, environmentPlate: true },
};
console.log(JSON.stringify(report, null, 2));
