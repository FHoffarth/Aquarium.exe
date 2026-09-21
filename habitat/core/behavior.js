const EPSILON = 1e-9;
const TAU = Math.PI * 2;

function mix32(value) {
  let result = value >>> 0;
  result ^= result >>> 16;
  result = Math.imul(result, 0x7feb352d);
  result ^= result >>> 15;
  result = Math.imul(result, 0x846ca68b);
  result ^= result >>> 16;
  return result >>> 0;
}

function seededUnit(seed, index, channel) {
  const combined = (seed ^ Math.imul(index + 1, 0x9e3779b1)
    ^ Math.imul(channel + 1, 0x85ebca77)) >>> 0;
  return mix32(combined) / 0x100000000;
}

function ranged(range, seed, index, channel) {
  return range[0] + (range[1] - range[0]) * seededUnit(seed, index, channel);
}

function magnitude(x, y, z) {
  return Math.hypot(x, y, z);
}

function clampMagnitude(vector, maximum) {
  const length = magnitude(vector.x, vector.y, vector.z);
  if (length > maximum && length > EPSILON) {
    const scale = maximum / length;
    vector.x *= scale;
    vector.y *= scale;
    vector.z *= scale;
  }
}

function addNormalized(target, x, y, z, scale) {
  const length = magnitude(x, y, z);
  if (length <= EPSILON) return;
  const factor = scale / length;
  target.x += x * factor;
  target.y += y * factor;
  target.z += z * factor;
}

function approach(current, target, maximumDelta) {
  if (current < target) return Math.min(target, current + maximumDelta);
  return Math.max(target, current - maximumDelta);
}

function personality(seed, index) {
  const schooling = 0.35 + seededUnit(seed, index, 30) * 0.6;
  const curiosity = 0.08 + seededUnit(seed, index, 31) * 0.82;
  const caution = 0.12 + seededUnit(seed, index, 32) * 0.8;
  return { schooling, curiosity, caution };
}

function createScratch() {
  return {
    neighborCount: 0,
    positionX: 0,
    positionY: 0,
    positionZ: 0,
    velocityX: 0,
    velocityY: 0,
    velocityZ: 0,
    separationX: 0,
    separationY: 0,
    separationZ: 0,
    steering: { x: 0, y: 0, z: 0 },
  };
}

export function createPointerState() {
  return { present: false, x: 0, y: 0, z: 0, eventsReceived: 0 };
}

export function createSchool(config) {
  const fish = [];
  const columns = Math.ceil(Math.sqrt(config.fishCount * 1.5));
  const rows = Math.ceil(config.fishCount / columns);
  for (let index = 0; index < config.fishCount; index += 1) {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const direction = seededUnit(config.seed, index, 2) < 0.18 ? -1 : 1;
    const preferredSpeed = ranged(config.fish.preferredSpeed, config.seed, index, 3);
    const maximumSpeed = Math.max(
      preferredSpeed * 1.35,
      ranged(config.fish.maximumSpeed, config.seed, index, 4),
    );
    const fishPersonality = personality(config.seed, index);
    const depthPreference = config.bounds.minZ
      + (config.bounds.maxZ - config.bounds.minZ) * seededUnit(config.seed, index, 5);
    fish.push({
      id: index,
      seed: mix32(config.seed ^ index),
      position: {
        x: -1.2 + column * (2.4 / Math.max(1, columns - 1))
          + (seededUnit(config.seed, index, 6) - 0.5) * 0.22,
        y: -0.55 + row * (1.1 / Math.max(1, rows - 1))
          + (seededUnit(config.seed, index, 7) - 0.5) * 0.18,
        z: depthPreference + (seededUnit(config.seed, index, 8) - 0.5) * 0.12,
      },
      velocity: {
        x: preferredSpeed * direction,
        y: (seededUnit(config.seed, index, 9) - 0.5) * preferredSpeed * 0.35,
        z: (seededUnit(config.seed, index, 10) - 0.5) * preferredSpeed * 0.18,
      },
      preferredSpeed,
      maximumSpeed,
      maximumAcceleration: ranged(
        config.fish.maximumAcceleration, config.seed, index, 11,
      ),
      turnResponsiveness: ranged(
        config.fish.turnResponsiveness, config.seed, index, 12,
      ),
      scale: ranged(config.fish.scale, config.seed, index, 13),
      depthPreference,
      neighborRadius: ranged(config.fish.neighborRadius, config.seed, index, 14),
      separationRadius: ranged(config.fish.separationRadius, config.seed, index, 15),
      cursorNoticeRadius: ranged(
        config.fish.cursorNoticeRadius, config.seed, index, 16,
      ),
      cursorThreatRadius: ranged(
        config.fish.cursorThreatRadius, config.seed, index, 17,
      ),
      cursorResponseStrength: ranged(
        config.fish.cursorResponseStrength, config.seed, index, 18,
      ),
      boundaryMargin: ranged(config.fish.boundaryMargin, config.seed, index, 19),
      wanderStrength: ranged(config.fish.wanderStrength, config.seed, index, 20),
      cohesionWeight: ranged(config.fish.cohesionWeight, config.seed, index, 21),
      alignmentWeight: ranged(config.fish.alignmentWeight, config.seed, index, 22),
      separationWeight: ranged(config.fish.separationWeight, config.seed, index, 23),
      depthWeight: ranged(config.fish.depthWeight, config.seed, index, 24),
      personality: fishPersonality,
      wanderPhase: seededUnit(config.seed, index, 25) * TAU,
      wanderFrequency: 0.22 + seededUnit(config.seed, index, 26) * 0.24,
      cursorAwareness: 0,
      cursorBoost: 0,
      reactionCount: 0,
      threatened: false,
    });
  }
  return {
    seed: config.seed,
    elapsedSeconds: 0,
    fish,
    scratch: fish.map(createScratch),
  };
}

function resetScratch(scratch) {
  scratch.neighborCount = 0;
  scratch.positionX = 0;
  scratch.positionY = 0;
  scratch.positionZ = 0;
  scratch.velocityX = 0;
  scratch.velocityY = 0;
  scratch.velocityZ = 0;
  scratch.separationX = 0;
  scratch.separationY = 0;
  scratch.separationZ = 0;
  scratch.steering.x = 0;
  scratch.steering.y = 0;
  scratch.steering.z = 0;
}

function accumulateNeighbors(school) {
  for (const scratch of school.scratch) resetScratch(scratch);
  for (let leftIndex = 0; leftIndex < school.fish.length; leftIndex += 1) {
    const left = school.fish[leftIndex];
    const leftScratch = school.scratch[leftIndex];
    for (let rightIndex = 0; rightIndex < school.fish.length; rightIndex += 1) {
      if (leftIndex === rightIndex) continue;
      const right = school.fish[rightIndex];
      const dx = right.position.x - left.position.x;
      const dy = right.position.y - left.position.y;
      const dz = right.position.z - left.position.z;
      const distanceSquared = dx * dx + dy * dy + dz * dz;
      const neighborRadius = Math.min(left.neighborRadius, right.neighborRadius);
      if (distanceSquared < neighborRadius * neighborRadius) {
        leftScratch.neighborCount += 1;
        leftScratch.positionX += right.position.x;
        leftScratch.positionY += right.position.y;
        leftScratch.positionZ += right.position.z;
        leftScratch.velocityX += right.velocity.x;
        leftScratch.velocityY += right.velocity.y;
        leftScratch.velocityZ += right.velocity.z;
      }
      const separationRadius = Math.max(left.separationRadius, right.separationRadius);
      if (distanceSquared >= separationRadius * separationRadius) continue;
      if (distanceSquared <= EPSILON) {
        const pairSeed = mix32(school.seed ^ Math.imul(Math.min(leftIndex, rightIndex) + 1, 31)
          ^ Math.imul(Math.max(leftIndex, rightIndex) + 1, 131));
        const angle = (pairSeed / 0x100000000) * TAU;
        const sign = leftIndex < rightIndex ? -1 : 1;
        leftScratch.separationX += Math.cos(angle) * sign;
        leftScratch.separationY += Math.sin(angle) * sign;
      } else {
        const distance = Math.sqrt(distanceSquared);
        const strength = 1 - distance / separationRadius;
        leftScratch.separationX -= (dx / distance) * strength;
        leftScratch.separationY -= (dy / distance) * strength;
        leftScratch.separationZ -= (dz / distance) * strength;
      }
    }
  }
}

function addBoundarySteering(steering, fish, bounds) {
  const margin = fish.boundaryMargin;
  const addAxis = (position, minimum, maximum, axis) => {
    const lowerDistance = position - minimum;
    const upperDistance = maximum - position;
    if (lowerDistance < margin) {
      steering[axis] += (1 - Math.max(0, lowerDistance) / margin) ** 2;
    }
    if (upperDistance < margin) {
      steering[axis] -= (1 - Math.max(0, upperDistance) / margin) ** 2;
    }
  };
  addAxis(fish.position.x, bounds.minX, bounds.maxX, 'x');
  addAxis(fish.position.y, bounds.minY, bounds.maxY, 'y');
  addAxis(fish.position.z, bounds.minZ, bounds.maxZ, 'z');
}

function addCursorSteering(steering, fish, input, dtSeconds) {
  if (!input.present) {
    fish.cursorAwareness = approach(fish.cursorAwareness, 0, dtSeconds * 0.9);
    fish.cursorBoost = approach(fish.cursorBoost, 0, dtSeconds * 1.2);
    fish.threatened = false;
    return;
  }

  const dx = input.x - fish.position.x;
  const dy = input.y - fish.position.y;
  const dz = input.z - fish.position.z;
  const distance = magnitude(dx, dy, dz);
  const noticeRadius = fish.cursorNoticeRadius * (1 + fish.personality.caution * 0.22);
  const threatRadius = fish.cursorThreatRadius * (1 + fish.personality.caution * 0.38);
  const noticed = distance < noticeRadius;
  const awarenessTarget = noticed ? 1 - distance / noticeRadius : 0;
  const noticeRate = 0.7 + fish.personality.caution * 1.3;
  fish.cursorAwareness = approach(
    fish.cursorAwareness,
    awarenessTarget,
    dtSeconds * noticeRate,
  );

  const threatened = distance < threatRadius;
  if (threatened && distance > EPSILON) {
    const proximity = 1 - distance / threatRadius;
    addNormalized(
      steering,
      -dx,
      -dy,
      -dz * 0.35,
      fish.cursorResponseStrength * (0.35 + proximity * proximity)
        * (0.8 + fish.personality.caution * 0.45),
    );
    fish.cursorBoost = approach(fish.cursorBoost, proximity, dtSeconds * 2.2);
  } else if (noticed && distance > EPSILON && fish.personality.curiosity > 0.25) {
    const curiosity = fish.personality.curiosity * (1 - fish.personality.caution * 0.55);
    addNormalized(
      steering,
      dx,
      dy,
      dz * 0.2,
      curiosity * fish.cursorAwareness * 0.16,
    );
    fish.cursorBoost = approach(fish.cursorBoost, 0, dtSeconds * 1.2);
  } else {
    fish.cursorBoost = approach(fish.cursorBoost, 0, dtSeconds * 1.2);
  }
  if (threatened && !fish.threatened) fish.reactionCount += 1;
  fish.threatened = threatened;
}

function updateFish(fish, scratch, input, dtSeconds, elapsedSeconds, bounds) {
  const steering = scratch.steering;
  if (scratch.neighborCount > 0) {
    const inverseCount = 1 / scratch.neighborCount;
    addNormalized(
      steering,
      scratch.positionX * inverseCount - fish.position.x,
      scratch.positionY * inverseCount - fish.position.y,
      scratch.positionZ * inverseCount - fish.position.z,
      fish.cohesionWeight * fish.personality.schooling,
    );
    steering.x += (scratch.velocityX * inverseCount - fish.velocity.x)
      * fish.alignmentWeight * fish.personality.schooling;
    steering.y += (scratch.velocityY * inverseCount - fish.velocity.y)
      * fish.alignmentWeight * fish.personality.schooling;
    steering.z += (scratch.velocityZ * inverseCount - fish.velocity.z)
      * fish.alignmentWeight * fish.personality.schooling;
  }
  addNormalized(
    steering,
    scratch.separationX,
    scratch.separationY,
    scratch.separationZ,
    fish.separationWeight,
  );

  const wanderTime = elapsedSeconds * fish.wanderFrequency + fish.wanderPhase;
  steering.x += Math.cos(wanderTime) * fish.wanderStrength * 0.35;
  steering.y += Math.sin(wanderTime * 1.37) * fish.wanderStrength;
  steering.z += Math.sin(wanderTime * 0.73) * fish.wanderStrength * 0.24;
  steering.z += (fish.depthPreference - fish.position.z) * fish.depthWeight;
  addBoundarySteering(steering, fish, bounds);
  addCursorSteering(steering, fish, input, dtSeconds);

  clampMagnitude(steering, fish.maximumAcceleration);
  const response = fish.turnResponsiveness * dtSeconds;
  fish.velocity.x += steering.x * response;
  fish.velocity.y += steering.y * response;
  fish.velocity.z += steering.z * response;

  let speed = magnitude(fish.velocity.x, fish.velocity.y, fish.velocity.z);
  if (speed < fish.preferredSpeed * 0.45 && magnitude(steering.x, steering.y, steering.z) < 0.02) {
    const direction = fish.velocity.x < 0 ? -1 : 1;
    fish.velocity.x += direction * fish.preferredSpeed * dtSeconds * 0.5;
    speed = magnitude(fish.velocity.x, fish.velocity.y, fish.velocity.z);
  }
  const maximumSpeed = fish.maximumSpeed * (1 + fish.cursorBoost * 0.35);
  if (speed > maximumSpeed) {
    const speedScale = maximumSpeed / speed;
    fish.velocity.x *= speedScale;
    fish.velocity.y *= speedScale;
    fish.velocity.z *= speedScale;
  }

  const damping = Math.exp(-0.045 * dtSeconds);
  fish.velocity.x *= damping;
  fish.velocity.y *= damping;
  fish.velocity.z *= damping;
  fish.position.x += fish.velocity.x * dtSeconds;
  fish.position.y += fish.velocity.y * dtSeconds;
  fish.position.z += fish.velocity.z * dtSeconds;

  for (const axis of ['x', 'y', 'z']) {
    const upper = bounds[`max${axis.toUpperCase()}`];
    const lower = bounds[`min${axis.toUpperCase()}`];
    if (fish.position[axis] > upper) {
      fish.position[axis] = upper;
      fish.velocity[axis] = -Math.abs(fish.velocity[axis]) * 0.35;
    } else if (fish.position[axis] < lower) {
      fish.position[axis] = lower;
      fish.velocity[axis] = Math.abs(fish.velocity[axis]) * 0.35;
    }
  }
}

export function stepSchool(school, input, dtSeconds, bounds) {
  if (!Number.isFinite(dtSeconds) || dtSeconds < 0) {
    throw new RangeError('dtSeconds must be a non-negative finite number');
  }
  if (dtSeconds === 0) return;
  const boundedDelta = Math.min(dtSeconds, 0.1);
  school.elapsedSeconds += boundedDelta;
  accumulateNeighbors(school);
  for (let index = 0; index < school.fish.length; index += 1) {
    updateFish(
      school.fish[index],
      school.scratch[index],
      input,
      boundedDelta,
      school.elapsedSeconds,
      bounds,
    );
  }
}
