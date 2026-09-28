import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const assetsDir = new URL('../../habitat/assets/', import.meta.url);
const manifest = JSON.parse(await readFile(new URL('manifest.json', assetsDir), 'utf8'));
const MIB = 1024 * 1024;

// Per art group: only one group is loaded at a time. Slice A envelope
// (approved plan): scene <= ~100k triangles, <= 30 draw calls, <= ~96 MiB
// texture memory, 1K textures by default, 2K atlases max. Slice B (the
// Hero Frame translation) is held to the same totals. Slice C allows one
// original vegetation mesh while retaining bounded draw calls and texture
// memory.

const BUDGETS = {
  'lush-slice': {
    // Export-only proof. Keep the true spatial layers; this is not a runtime
    // draw-call target.
    environmentTriangles: 110_000,
    meshTriangles: {},
    environmentPrimitives: 64,
    textureMemoryMiB: 16,
    maxTextureSide: 2048,
  },
  lush: {
    environmentTriangles: 0,
    meshTriangles: {},
    environmentPrimitives: 0,
    textureMemoryMiB: 12,
    maxTextureSide: 2048,
  },
  'slice-a': {
    environmentTriangles: 90_000,
    meshTriangles: {
      'slice-a-rocks': 20_000,
      'slice-a-wood': 8_000,
      'slice-a-plants': 26_000,
      'slice-a-moss': 10_000,
      'slice-a-cards': 1_000,
      'slice-a-substrate': 8_000,
    },
    environmentPrimitives: 8,
    textureMemoryMiB: 96,
    maxTextureSide: 2048,
  },
  'slice-b': {
    environmentTriangles: 90_000,
    meshTriangles: {
      'slice-b-rocks': 20_000,
      'slice-b-wood': 8_000,
      'slice-b-plants': 26_000,
      'slice-b-moss': 10_000,
      'slice-b-cards': 1_000,
      'slice-b-substrate': 8_000,
    },
    environmentPrimitives: 8,
    textureMemoryMiB: 96,
    maxTextureSide: 2048,
  },
  'slice-c': {
    environmentTriangles: 85_000,
    meshTriangles: {
      'slice-c-rock-07': 4_000,
      'slice-c-boulder': 6_000,
      'slice-c-rock-09': 4_500,
      'slice-c-stones': 9_000,
      'slice-c-wood': 6_000,
      'slice-c-leaves': 14_000,
      'slice-c-growth': 35_000,
      'slice-c-substrate': 9_000,
    },
    environmentPrimitives: 9,
    textureMemoryMiB: 72,
    maxTextureSide: 2048,
  },
};

function parseGlb(buffer) {
  const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  assert.equal(view.getUint32(0, true), 0x46546c67, 'GLB magic');
  const jsonLength = view.getUint32(12, true);
  assert.equal(view.getUint32(16, true), 0x4e4f534a, 'first chunk is JSON');
  return JSON.parse(new TextDecoder().decode(buffer.subarray(20, 20 + jsonLength)));
}

function webpSize(bytes) {
  const tag = String.fromCharCode(...bytes.subarray(12, 16));
  if (tag === 'VP8X') {
    const width = 1 + (bytes[24] | (bytes[25] << 8) | (bytes[26] << 16));
    const height = 1 + (bytes[27] | (bytes[28] << 8) | (bytes[29] << 16));
    return { width, height };
  }
  if (tag === 'VP8L') {
    const bits = bytes[21] | (bytes[22] << 8) | (bytes[23] << 16) | (bytes[24] << 24);
    return { width: (bits & 0x3fff) + 1, height: ((bits >>> 14) & 0x3fff) + 1 };
  }
  if (tag === 'VP8 ') {
    return {
      width: (bytes[26] | (bytes[27] << 8)) & 0x3fff,
      height: (bytes[28] | (bytes[29] << 8)) & 0x3fff,
    };
  }
  throw new Error(`unknown WebP chunk ${tag}`);
}

const inGroup = group => entry => entry.file.startsWith(`${group}/`);

async function meshTriangles(geometryEntries) {
  const perMesh = {};
  let primitives = 0;
  for (const entry of geometryEntries) {
    const gltf = parseGlb(new Uint8Array(await readFile(new URL(entry.file, assetsDir))));
    // The runtime addresses meshes by node name, so budget by node name too.
    for (const node of gltf.nodes.filter(candidate => candidate.mesh !== undefined)) {
      for (const primitive of gltf.meshes[node.mesh].primitives) {
        assert.ok(primitive.mode === undefined || primitive.mode === 4, `${node.name} uses triangles`);
        const count = primitive.indices === undefined
          ? gltf.accessors[primitive.attributes.POSITION].count
          : gltf.accessors[primitive.indices].count;
        perMesh[node.name] = (perMesh[node.name] ?? 0) + count / 3;
        primitives += 1;
      }
    }
  }
  return { perMesh, primitives };
}

test('every shipped art group has a budget', () => {
  const groups = new Set(manifest.files.map(entry => entry.file.split('/')[0]));
  for (const group of groups) assert.ok(BUDGETS[group], `${group} has a budget`);
});

for (const [group, BUDGET] of Object.entries(BUDGETS)) {
  const geometryEntries = manifest.files.filter(entry => entry.role === 'geometry' && inGroup(group)(entry));
  const textureEntries = manifest.files.filter(entry => entry.role === 'texture' && inGroup(group)(entry));

  test(`${group} environment geometry stays inside its triangle and draw-call budget`, async () => {
    const { perMesh, primitives } = await meshTriangles(geometryEntries);
    const total = Object.values(perMesh).reduce((sum, value) => sum + value, 0);
    assert.ok(total <= BUDGET.environmentTriangles, `environment triangles ${total}`);
    assert.ok(primitives <= BUDGET.environmentPrimitives, `environment primitives ${primitives}`);
    for (const [name, limit] of Object.entries(BUDGET.meshTriangles)) {
      assert.ok(perMesh[name] !== undefined, `mesh ${name} is present`);
      assert.ok(perMesh[name] <= limit, `${name} has ${perMesh[name]} triangles (limit ${limit})`);
    }
  });

  test(`${group} textures stay at or below 2K and inside the GPU texture-memory budget`, async () => {
    let bytes = 0;
    for (const entry of textureEntries) {
      const data = new Uint8Array(await readFile(new URL(entry.file, assetsDir)));
      assert.equal(String.fromCharCode(...data.subarray(8, 12)), 'WEBP', entry.file);
      const { width, height } = webpSize(data);
      assert.ok(Math.max(width, height) <= BUDGET.maxTextureSide, `${entry.file} is ${width}x${height}`);
      bytes += width * height * 4 * (4 / 3);  // RGBA8 with a full mip chain
    }
    for (const entry of geometryEntries) {
      const data = new Uint8Array(await readFile(new URL(entry.file, assetsDir)));
      const gltf = parseGlb(data);
      const jsonLength = new DataView(data.buffer, data.byteOffset, data.byteLength).getUint32(12, true);
      const binOffset = 20 + jsonLength + 8;
      for (const image of gltf.images ?? []) {
        assert.equal(image.mimeType, 'image/webp', `${entry.file}/${image.name}`);
        const segment = gltf.bufferViews[image.bufferView];
        const embedded = data.subarray(binOffset + (segment.byteOffset ?? 0),
          binOffset + (segment.byteOffset ?? 0) + segment.byteLength);
        const { width, height } = webpSize(embedded);
        assert.ok(Math.max(width, height) <= BUDGET.maxTextureSide,
          `${entry.file}/${image.name} is ${width}x${height}`);
        bytes += width * height * 4 * (4 / 3);
      }
    }
    assert.ok(bytes / MIB <= BUDGET.textureMemoryMiB, `texture memory ${(bytes / MIB).toFixed(1)} MiB`);
  });
}
