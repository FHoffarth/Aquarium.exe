import * as THREE from '../vendor/three/three.module.js';
import { GLTFLoader } from '../vendor/three/addons/loaders/GLTFLoader.js';
import {
  AssetIntegrityError,
  indexManifest,
  verifyAssetBytes,
} from './asset-manifest.js';

const COLOR_TEXTURES = new Set(['albedo']);

async function fetchBytes(url, fetchImpl) {
  const response = await fetchImpl(url, { cache: 'no-store' });
  if (!response.ok) throw new AssetIntegrityError(`${url}: HTTP ${response.status}`);
  return response.arrayBuffer();
}

function parseGlb(bytes) {
  return new Promise((resolve, reject) => {
    new GLTFLoader().parse(bytes, '', resolve, error => {
      reject(new AssetIntegrityError(`GLB parse failed: ${error?.message ?? error}`));
    });
  });
}

async function decodeTexture(entry, bytes, maxAnisotropy) {
  const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/webp' }), {
    imageOrientation: 'none',
    premultiplyAlpha: 'none',
    colorSpaceConversion: 'none',
  });
  const texture = new THREE.Texture(bitmap);
  const kind = entry.file.replace(/^.*_(\w+)\.webp$/, '$1');
  texture.colorSpace = COLOR_TEXTURES.has(kind) ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  texture.flipY = false;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = maxAnisotropy;
  texture.name = entry.file;
  texture.needsUpdate = true;
  return texture;
}

// Loads every file of one art group, verifying size + SHA-256 against the
// manifest before anything is parsed. Any failure rejects with a reason.
export async function loadArtGroup(group, {
  baseUrl = './assets/',
  fetchImpl = globalThis.fetch.bind(globalThis),
  now = () => performance.now(),
  maxAnisotropy = 4,
} = {}) {
  const started = now();
  const manifestBytes = await fetchBytes(`${baseUrl}manifest.json`, fetchImpl);
  const entries = indexManifest(JSON.parse(new TextDecoder().decode(manifestBytes)));
  const groupEntries = [...entries.values()].filter(entry => entry.file.startsWith(`${group}/`));
  if (groupEntries.length === 0) throw new AssetIntegrityError(`no assets for ${group}`);

  const loaded = await Promise.all(groupEntries.map(async entry => {
    const bytes = await verifyAssetBytes(entry, await fetchBytes(`${baseUrl}${entry.file}`, fetchImpl));
    return { entry, bytes };
  }));

  const meshes = {};
  const textures = {};
  let totalBytes = 0;
  for (const { entry, bytes } of loaded) {
    totalBytes += bytes.byteLength;
    if (entry.role === 'geometry') {
      const gltf = await parseGlb(bytes);
      gltf.scene.traverse(object => {
        if (object.isMesh) meshes[object.name] = object;
      });
    } else if (entry.role === 'texture') {
      const key = entry.file.replace(/^.*\//, '').replace(/\.webp$/, '');
      textures[key] = await decodeTexture(entry, bytes, maxAnisotropy);
    }
  }
  return { meshes, textures, totalBytes, loadMs: now() - started };
}
