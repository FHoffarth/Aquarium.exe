const NATIVE_AUDIT_OVERRIDE = null;

const MODES = new Set([
  'full',
  'fish-only',
  'environment-only',
  'minimal-render',
  'no-render',
]);
const POINTER_MODES = new Set(['normal', 'stationary', 'ignore']);
const DEFAULT_CONFIG = Object.freeze({
  enabled: false,
  mode: 'full',
  fishCount: 10,
  renderScale: 1,
  targetFps: null,
  pointerMode: 'normal',
});

function finiteNumber(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new TypeError(`${name} must be finite`);
  return number;
}

function validate(config) {
  if (!MODES.has(config.mode)) throw new RangeError('unsupported audit mode');
  if (!Number.isInteger(config.fishCount)
      || config.fishCount < 0 || config.fishCount > 50) {
    throw new RangeError('audit fishCount must be an integer from 0 to 50');
  }
  if (!(config.renderScale > 0 && config.renderScale <= 1)) {
    throw new RangeError('audit renderScale must be above 0 and at most 1');
  }
  if (config.targetFps !== null
      && (!(config.targetFps >= 0 && config.targetFps <= 60))) {
    throw new RangeError('audit targetFps must be null or from 0 to 60');
  }
  if (!POINTER_MODES.has(config.pointerMode)) {
    throw new RangeError('unsupported audit pointerMode');
  }
  return Object.freeze(config);
}

export function readAuditConfig(locationLike, nativeOverride = NATIVE_AUDIT_OVERRIDE) {
  const params = new URLSearchParams(locationLike?.search ?? '');
  const enabled = params.get('audit') === '1' || Boolean(nativeOverride?.enabled);
  if (!enabled) return DEFAULT_CONFIG;
  const source = nativeOverride ?? {};
  const targetValue = params.has('fps') ? params.get('fps') : source.targetFps;
  const config = {
    enabled,
    mode: params.get('mode') ?? source.mode ?? 'full',
    fishCount: params.has('fish')
      ? finiteNumber(params.get('fish'), 'fish')
      : source.fishCount ?? 10,
    renderScale: params.has('scale')
      ? finiteNumber(params.get('scale'), 'scale')
      : source.renderScale ?? 1,
    targetFps: targetValue === undefined || targetValue === null
      ? null
      : finiteNumber(targetValue, 'fps'),
    pointerMode: params.get('pointer') ?? source.pointerMode ?? 'normal',
  };
  return validate(config);
}

export function deriveAuditScenePlan(config) {
  const enabled = Boolean(config?.enabled);
  const mode = enabled ? config.mode : 'full';
  const requestedFishCount = enabled ? config.fishCount : 10;
  const createFish = mode === 'full' || mode === 'fish-only' || mode === 'no-render';
  const createEnvironment = mode === 'full'
    || mode === 'environment-only'
    || mode === 'no-render';
  return Object.freeze({
    fishCount: createFish ? requestedFishCount : 0,
    createFish,
    createEnvironment,
    render: mode !== 'no-render',
  });
}
