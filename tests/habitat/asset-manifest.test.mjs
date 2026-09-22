import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';

import {
  AssetIntegrityError,
  indexManifest,
  verifyAssetBytes,
} from '../../habitat/core/asset-manifest.js';

const root = new URL('../../', import.meta.url);
const assetsDir = new URL('habitat/assets/', root);
const manifest = JSON.parse(await readFile(new URL('manifest.json', assetsDir), 'utf8'));
const acquisitions = JSON.parse(
  await readFile(new URL('art/provenance/polyhaven/acquisitions.json', root), 'utf8'),
);

async function listFiles(dir, prefix = '') {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const relative = `${prefix}${entry.name}`;
    if (entry.isDirectory()) files.push(...await listFiles(new URL(`${entry.name}/`, dir), `${relative}/`));
    else files.push(relative);
  }
  return files;
}

test('every shipped art file is listed in the manifest and nothing listed is missing', async () => {
  const onDisk = (await listFiles(assetsDir)).filter(file => file !== 'manifest.json').sort();
  const listed = manifest.files.map(entry => entry.file).sort();
  assert.deepEqual(listed, onDisk);
});

test('manifest SHA-256 and byte sizes match the shipped bytes exactly', async () => {
  for (const entry of manifest.files) {
    const bytes = await readFile(new URL(entry.file, assetsDir));
    assert.equal(bytes.byteLength, entry.bytes, entry.file);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), entry.sha256, entry.file);
  }
});

test('every shipped file is GREEN CC0 with recorded provenance for each source', () => {
  for (const entry of manifest.files) {
    assert.equal(entry.status, 'GREEN', entry.file);
    assert.equal(entry.license, 'CC0-1.0', entry.file);
    assert.ok(entry.modifications.length > 20, `${entry.file} documents its modifications`);
    assert.ok(entry.derivedFrom.length > 0, `${entry.file} names its sources`);
    for (const sourceId of entry.derivedFrom) {
      const source = manifest.sources[sourceId];
      assert.ok(source, `${entry.file} source ${sourceId} is recorded`);
      assert.equal(source.status, 'GREEN');
      assert.equal(source.license, 'CC0-1.0');
      assert.match(source.sourcePage, /^https:\/\/polyhaven\.com\/a\//);
      assert.ok(source.creator && Object.keys(source.creator).length > 0, `${sourceId} creator`);
      assert.match(source.dateAcquired, /^\d{4}-\d{2}-\d{2}$/);
      assert.ok(acquisitions[sourceId], `${sourceId} has an acquisition record`);
      const recorded = new Set(acquisitions[sourceId].files.map(file => file.sha256));
      for (const original of source.originalFiles) {
        assert.ok(recorded.has(original.sha256), `${sourceId}/${original.filename} matches acquisition`);
      }
    }
  }
});

test('archived license evidence exists in the repository', () => {
  for (const evidence of manifest.licenseEvidence) {
    assert.ok(existsSync(new URL(evidence, root)), evidence);
  }
});

test('runtime integrity check rejects tampered or truncated asset bytes', async () => {
  const entries = indexManifest(manifest);
  const entry = entries.get('slice-a/environment.glb');
  const bytes = new Uint8Array(await readFile(new URL(entry.file, assetsDir)));
  await verifyAssetBytes(entry, bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));

  const tampered = bytes.slice();
  tampered[100] ^= 0xff;
  await assert.rejects(verifyAssetBytes(entry, tampered.buffer), AssetIntegrityError);
  await assert.rejects(verifyAssetBytes(entry, bytes.slice(0, 64).buffer), AssetIntegrityError);
});

test('manifest indexing refuses non-GREEN or unhashed entries', () => {
  const base = structuredClone(manifest);
  base.files[0].status = 'REVIEW';
  assert.throws(() => indexManifest(base), AssetIntegrityError);
  const unhashed = structuredClone(manifest);
  unhashed.files[0].sha256 = 'not-a-hash';
  assert.throws(() => indexManifest(unhashed), AssetIntegrityError);
});
