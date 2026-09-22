const DEFAULT_CONFIG = {
  id: 'planted-tank',
  seed: 20260921,
  fishCount: 10,
  bounds: {
    minX: -3.0,
    maxX: 3.0,
    minY: -1.45,
    maxY: 1.45,
    minZ: -0.65,
    maxZ: 0.65,
  },
  fish: {
    preferredSpeed: [0.17, 0.34],
    maximumSpeed: [0.36, 0.5],
    maximumAcceleration: [0.42, 0.62],
    turnResponsiveness: [1.0, 2.15],
    scale: [0.82, 1.14],
    neighborRadius: [0.85, 1.15],
    separationRadius: [0.4, 0.58],
    cursorNoticeRadius: [1.0, 1.45],
    cursorThreatRadius: [0.3, 0.48],
    cursorResponseStrength: [0.9, 1.35],
    boundaryMargin: [0.38, 0.58],
    wanderStrength: [0.045, 0.1],
    cohesionWeight: [0.045, 0.1],
    alignmentWeight: [0.13, 0.24],
    separationWeight: [1.3, 2.05],
    depthWeight: [0.18, 0.32],
  },
  environment: {
    particleCount: 72,
    foregroundPlantCount: 30,
    midPlantCount: 24,
    stemCount: 18,
    rockCount: 7,
    driftwoodCount: 5,
    backgroundTop: 0x176872,
    backgroundBottom: 0x06242d,
    substrateColor: 0x172521,
    fogColor: 0x041f27,
  },
  diagnostics: false,
};

function mergeConfig(overrides) {
  return {
    ...DEFAULT_CONFIG,
    ...overrides,
    bounds: { ...DEFAULT_CONFIG.bounds, ...(overrides.bounds ?? {}) },
    fish: { ...DEFAULT_CONFIG.fish, ...(overrides.fish ?? {}) },
    environment: {
      ...DEFAULT_CONFIG.environment,
      ...(overrides.environment ?? {}),
    },
  };
}

function validateFiniteRange(value, name, { minimum = -Infinity } = {}) {
  if (!Array.isArray(value) || value.length !== 2
      || !value.every(Number.isFinite)) {
    throw new TypeError(`${name} must contain two finite numbers`);
  }
  if (value[0] < minimum || value[0] > value[1]) {
    throw new RangeError(`${name} must be ordered and at least ${minimum}`);
  }
}

function deepFreeze(value) {
  Object.freeze(value);
  for (const child of Object.values(value)) {
    if (child && typeof child === 'object' && !Object.isFrozen(child)) deepFreeze(child);
  }
  return value;
}

export function validatePlantedTankConfig(config) {
  if (!config || typeof config !== 'object') throw new TypeError('config must be an object');
  if (!Number.isInteger(config.seed)) throw new TypeError('seed must be an integer');
  if (!Number.isInteger(config.fishCount)) throw new TypeError('fishCount must be an integer');
  if (config.fishCount < 8 || config.fishCount > 12) {
    throw new RangeError('fishCount must be between 8 and 12');
  }

  const { bounds, fish, environment } = config;
  if (!bounds || !fish || !environment) throw new TypeError('config sections are required');
  for (const axis of ['X', 'Y', 'Z']) {
    const minimum = bounds[`min${axis}`];
    const maximum = bounds[`max${axis}`];
    if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) {
      throw new TypeError(`bounds ${axis} must be finite`);
    }
    if (minimum >= maximum) throw new RangeError(`bounds ${axis} must be ordered`);
  }

  for (const name of [
    'preferredSpeed',
    'maximumSpeed',
    'maximumAcceleration',
    'turnResponsiveness',
    'scale',
    'neighborRadius',
    'separationRadius',
    'cursorNoticeRadius',
    'cursorThreatRadius',
    'cursorResponseStrength',
    'boundaryMargin',
    'wanderStrength',
    'cohesionWeight',
    'alignmentWeight',
    'separationWeight',
    'depthWeight',
  ]) {
    validateFiniteRange(fish[name], `fish.${name}`, { minimum: 0 });
  }
  if (fish.maximumSpeed[0] < fish.preferredSpeed[0]
      || fish.maximumSpeed[1] < fish.preferredSpeed[1]) {
    throw new RangeError('maximumSpeed must not be below preferredSpeed');
  }
  if (fish.separationRadius[1] >= fish.neighborRadius[0]) {
    throw new RangeError('separation radius must stay below neighbor radius');
  }
  if (fish.cursorThreatRadius[1] >= fish.cursorNoticeRadius[0]) {
    throw new RangeError('cursor threat radius must stay below notice radius');
  }
  const environmentCounts = [
    'particleCount',
    'foregroundPlantCount',
    'midPlantCount',
    'stemCount',
    'rockCount',
    'driftwoodCount',
  ];
  if (environmentCounts.some(name => (
    !Number.isInteger(environment[name]) || environment[name] < 0
  ))) {
    throw new RangeError('environment counts must be non-negative integers');
  }
  return config;
}

export function createPlantedTankConfig(overrides = {}) {
  const config = mergeConfig(overrides);
  validatePlantedTankConfig(config);
  return deepFreeze(config);
}
