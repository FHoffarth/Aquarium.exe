export class AssetIntegrityError extends Error {
  constructor(message) {
    super(message);
    this.name = 'AssetIntegrityError';
  }
}

export function indexManifest(manifest) {
  if (manifest?.schema !== 1 || !Array.isArray(manifest.files)) {
    throw new AssetIntegrityError('unsupported asset manifest');
  }
  const entries = new Map();
  for (const entry of manifest.files) {
    if (entry.status !== 'GREEN') {
      throw new AssetIntegrityError(`asset ${entry.file} is not GREEN`);
    }
    if (!/^[0-9a-f]{64}$/.test(entry.sha256)) {
      throw new AssetIntegrityError(`asset ${entry.file} has no valid SHA-256`);
    }
    entries.set(entry.file, entry);
  }
  return entries;
}

export async function sha256Hex(bytes, subtle = globalThis.crypto?.subtle) {
  if (!subtle) throw new AssetIntegrityError('SHA-256 unavailable in this context');
  const digest = await subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

export async function verifyAssetBytes(entry, bytes, subtle) {
  if (bytes.byteLength !== entry.bytes) {
    throw new AssetIntegrityError(`${entry.file}: ${bytes.byteLength} bytes, manifest says ${entry.bytes}`);
  }
  const actual = await sha256Hex(bytes, subtle);
  if (actual !== entry.sha256) {
    throw new AssetIntegrityError(`${entry.file}: SHA-256 mismatch`);
  }
  return bytes;
}
