const DEFAULT_STEP_MS = 1000 / 60;

function finiteNonNegative(value, name) {
  if (!Number.isFinite(value) || value < 0) {
    throw new RangeError(`${name} must be a non-negative finite number`);
  }
  return value;
}

function finitePositive(value, name) {
  if (!Number.isFinite(value) || value <= 0) {
    throw new RangeError(`${name} must be a positive finite number`);
  }
  return value;
}

export class FrameClock {
  constructor({ fixedStepMs = DEFAULT_STEP_MS, maxSteps = 4, targetFps = 60 } = {}) {
    this.fixedStepMs = finitePositive(fixedStepMs, 'fixedStepMs');
    if (!Number.isInteger(maxSteps) || maxSteps < 1) {
      throw new RangeError('maxSteps must be a positive integer');
    }
    this.maxSteps = maxSteps;
    this.targetFps = finiteNonNegative(targetFps, 'targetFps');
    this.running = false;
    this.lastNowMs = 0;
    this.lastRenderMs = null;
    this.accumulatorMs = 0;
    this.frameDeltaMs = 0;
    this.stepCount = 0;
    this.shouldRender = false;
  }

  resume(nowMs) {
    this.lastNowMs = finiteNonNegative(nowMs, 'nowMs');
    this.lastRenderMs = null;
    this.accumulatorMs = 0;
    this.frameDeltaMs = 0;
    this.stepCount = 0;
    this.shouldRender = false;
    this.running = true;
  }

  pause() {
    this.running = false;
    this.frameDeltaMs = 0;
    this.stepCount = 0;
    this.shouldRender = false;
  }

  setTargetFps(fps) {
    this.targetFps = finiteNonNegative(fps, 'fps');
    this.lastRenderMs = null;
  }

  tick(nowMs) {
    if (!this.running) {
      this.frameDeltaMs = 0;
      this.stepCount = 0;
      this.shouldRender = false;
      return;
    }
    const currentNowMs = finiteNonNegative(nowMs, 'nowMs');
    const unboundedDelta = Math.max(0, currentNowMs - this.lastNowMs);
    this.lastNowMs = currentNowMs;
    this.frameDeltaMs = Math.min(unboundedDelta, this.fixedStepMs * this.maxSteps);
    this.accumulatorMs += this.frameDeltaMs;
    this.stepCount = Math.min(
      this.maxSteps,
      Math.floor((this.accumulatorMs + 1e-9) / this.fixedStepMs),
    );
    this.accumulatorMs -= this.stepCount * this.fixedStepMs;

    if (this.targetFps === 0) {
      this.shouldRender = false;
      return;
    }
    const renderInterval = 1000 / this.targetFps;
    this.shouldRender = this.lastRenderMs === null
      || currentNowMs - this.lastRenderMs + 1e-9 >= renderInterval;
    if (this.shouldRender) this.lastRenderMs = currentNowMs;
  }
}

function copyPointer(pointer) {
  return {
    present: Boolean(pointer?.present),
    x: Number.isFinite(pointer?.x) ? pointer.x : 0,
    y: Number.isFinite(pointer?.y) ? pointer.y : 0,
    z: Number.isFinite(pointer?.z) ? pointer.z : 0,
    eventsReceived: Number.isFinite(pointer?.eventsReceived)
      ? pointer.eventsReceived
      : 0,
  };
}

export function createHabitatEngine({
  habitat,
  requestFrame,
  cancelFrame,
  now,
  onReady,
  onDiagnostics,
  diagnosticsIntervalMs = 5000,
  fixedStepMs = DEFAULT_STEP_MS,
  maxSteps = 4,
  targetFps = 60,
  performanceRecorder = null,
}) {
  if (!habitat || typeof habitat.step !== 'function' || typeof habitat.project !== 'function') {
    throw new TypeError('habitat must provide step() and project()');
  }
  if (typeof requestFrame !== 'function' || typeof cancelFrame !== 'function') {
    throw new TypeError('requestFrame and cancelFrame are required');
  }
  if (typeof now !== 'function') throw new TypeError('now is required');
  finitePositive(diagnosticsIntervalMs, 'diagnosticsIntervalMs');

  const clock = new FrameClock({ fixedStepMs, maxSteps, targetFps });
  let pointer = copyPointer();
  let frameRequest = null;
  let started = false;
  let paused = false;
  let disposed = false;
  let ready = false;
  let simulationTime = 0;
  let reportStartMs = 0;
  let reportFrames = 0;
  let reportFrameTimeMs = 0;
  let measuredFps = 0;
  let measuredFrameTimeMs = 0;

  const active = () => started && !paused && clock.targetFps > 0 && !disposed;

  const snapshot = () => {
    const renderInfo = typeof habitat.getRenderInfo === 'function'
      ? habitat.getRenderInfo()
      : {};
    const report = {
      fps: measuredFps,
      frameTimeMs: measuredFrameTimeMs,
      fishCount: typeof habitat.getFishCount === 'function' ? habitat.getFishCount() : 0,
      calls: Number(renderInfo.calls) || 0,
      triangles: Number(renderInfo.triangles) || 0,
      pointerCount: pointer.eventsReceived,
      reactions: typeof habitat.getReactionCount === 'function'
        ? habitat.getReactionCount()
        : 0,
      paused: paused || clock.targetFps === 0,
      targetFps: clock.targetFps,
    };
    const performance = typeof habitat.getPerformanceSnapshot === 'function'
      ? habitat.getPerformanceSnapshot()
      : null;
    if (performance) report.performance = performance;
    return report;
  };

  const schedule = () => {
    if (active() && frameRequest === null) frameRequest = requestFrame(frame);
  };

  const resetTiming = () => {
    const timestamp = now();
    clock.resume(timestamp);
    reportStartMs = timestamp;
    reportFrames = 0;
    reportFrameTimeMs = 0;
  };

  function frame(timestamp) {
    frameRequest = null;
    if (!active()) return;
    const performanceStart = performanceRecorder?.enabled
      ? performanceRecorder.mark()
      : 0;
    clock.tick(timestamp);
    for (let index = 0; index < clock.stepCount; index += 1) {
      const deltaSeconds = clock.fixedStepMs / 1000;
      habitat.step(deltaSeconds, pointer);
      simulationTime += deltaSeconds;
    }
    if (clock.shouldRender) {
      if (performanceRecorder?.enabled) performanceRecorder.recordRender(timestamp);
      habitat.project(simulationTime);
      reportFrames += 1;
      reportFrameTimeMs += clock.frameDeltaMs;
      if (!ready) {
        ready = true;
        if (typeof onReady === 'function') onReady();
      }
      const reportDurationMs = timestamp - reportStartMs;
      if (reportDurationMs >= diagnosticsIntervalMs) {
        measuredFps = reportFrames * 1000 / reportDurationMs;
        measuredFrameTimeMs = reportFrames > 0 ? reportFrameTimeMs / reportFrames : 0;
        if (typeof onDiagnostics === 'function') onDiagnostics(snapshot());
        reportStartMs = timestamp;
        reportFrames = 0;
        reportFrameTimeMs = 0;
      }
    }
    schedule();
    if (performanceRecorder?.enabled) performanceRecorder.finishFrame(performanceStart);
  }

  const cancelScheduledFrame = () => {
    if (frameRequest !== null) {
      cancelFrame(frameRequest);
      frameRequest = null;
    }
  };

  return {
    start() {
      if (disposed || started) return;
      started = true;
      resetTiming();
      schedule();
    },
    setPaused(value) {
      const nextPaused = Boolean(value);
      if (nextPaused === paused || disposed) return;
      paused = nextPaused;
      if (paused) {
        cancelScheduledFrame();
        clock.pause();
      } else if (started && clock.targetFps > 0) {
        resetTiming();
        schedule();
      }
    },
    setTargetFps(fps) {
      const nextFps = Math.min(60, finiteNonNegative(Number(fps), 'fps'));
      if (nextFps === clock.targetFps || disposed) return;
      clock.setTargetFps(nextFps);
      if (nextFps === 0) {
        cancelScheduledFrame();
        clock.pause();
      } else if (started && !paused) {
        resetTiming();
        schedule();
      }
    },
    setPointer(nextPointer) {
      pointer = copyPointer(nextPointer);
    },
    resize(width, height) {
      if (!disposed && typeof habitat.resize === 'function') habitat.resize(width, height);
    },
    requestProbe() {
      const report = snapshot();
      if (typeof onDiagnostics === 'function') onDiagnostics(report);
      return report;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      cancelScheduledFrame();
      clock.pause();
      if (typeof habitat.dispose === 'function') habitat.dispose();
    },
  };
}
