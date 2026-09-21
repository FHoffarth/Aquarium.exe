const COMPONENT_NAMES = [
  'simulationMs',
  'fishProjectionMs',
  'environmentMs',
  'renderMs',
  'callbackMs',
];
const MAX_INTERVALS = 4096;

function rounded(value) {
  return Math.round(value * 1000) / 1000;
}

function summarize(values) {
  if (values.length === 0) {
    return { count: 0, mean: 0, median: 0, p95: 0, min: 0, max: 0 };
  }
  const sorted = values.slice().sort((left, right) => left - right);
  const sum = sorted.reduce((total, value) => total + value, 0);
  const middle = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle];
  const p95Index = Math.min(sorted.length - 1, Math.ceil(sorted.length * 0.95) - 1);
  return {
    count: sorted.length,
    mean: rounded(sum / sorted.length),
    median: rounded(median),
    p95: rounded(sorted[p95Index]),
    min: rounded(sorted[0]),
    max: rounded(sorted.at(-1)),
  };
}

export function createPerformanceRecorder({ enabled = false, now } = {}) {
  const clock = now ?? (() => performance.now());
  const intervals = [];
  const callbackIntervals = [];
  let lastRenderTimestamp = null;
  let lastCallbackTimestamp = null;
  let callbackCount = 0;
  let renderedFrameCount = 0;
  let gateSkippedCallbackCount = 0;
  const components = Object.fromEntries(
    COMPONENT_NAMES.map(name => [name, { count: 0, sum: 0, min: Infinity, max: 0 }]),
  );

  function reset() {
    intervals.length = 0;
    callbackIntervals.length = 0;
    lastRenderTimestamp = null;
    lastCallbackTimestamp = null;
    callbackCount = 0;
    renderedFrameCount = 0;
    gateSkippedCallbackCount = 0;
    for (const value of Object.values(components)) {
      value.count = 0;
      value.sum = 0;
      value.min = Infinity;
      value.max = 0;
    }
  }

  return {
    enabled: Boolean(enabled),
    mark() {
      return enabled ? clock() : 0;
    },
    beginFrame() {},
    finishFrame(start) {
      if (enabled) this.add('callbackMs', clock() - start);
    },
    recordRender(timestamp) {
      if (!enabled) return;
      renderedFrameCount += 1;
      if (lastRenderTimestamp !== null && intervals.length < MAX_INTERVALS) {
        intervals.push(Math.max(0, timestamp - lastRenderTimestamp));
      }
      lastRenderTimestamp = timestamp;
    },
    recordCallback(timestamp, rendered) {
      if (!enabled) return;
      callbackCount += 1;
      if (!rendered) gateSkippedCallbackCount += 1;
      if (lastCallbackTimestamp !== null && callbackIntervals.length < MAX_INTERVALS) {
        callbackIntervals.push(Math.max(0, timestamp - lastCallbackTimestamp));
      }
      lastCallbackTimestamp = timestamp;
    },
    add(name, durationMs) {
      if (!enabled) return;
      const value = components[name];
      if (!value || !Number.isFinite(durationMs) || durationMs < 0) return;
      value.count += 1;
      value.sum += durationMs;
      value.min = Math.min(value.min, durationMs);
      value.max = Math.max(value.max, durationMs);
    },
    end(name, start) {
      if (enabled) this.add(name, clock() - start);
    },
    record(name, start) {
      if (enabled) this.add(name, clock() - start);
    },
    snapshot() {
      if (!enabled) return null;
      const renderedIntervals = summarize(intervals);
      renderedIntervals.values = intervals.map(rounded);
      const clusters = {};
      for (const interval of intervals) {
        const bucket = String(Math.round(interval));
        clusters[bucket] = (clusters[bucket] ?? 0) + 1;
      }
      renderedIntervals.clusters = clusters;
      const callbackSummary = summarize(callbackIntervals);
      callbackSummary.values = callbackIntervals.map(rounded);
      const callbackClusters = {};
      for (const interval of callbackIntervals) {
        const bucket = String(Math.round(interval));
        callbackClusters[bucket] = (callbackClusters[bucket] ?? 0) + 1;
      }
      callbackSummary.clusters = callbackClusters;
      const componentSummary = {};
      for (const [name, value] of Object.entries(components)) {
        componentSummary[name] = {
          count: value.count,
          mean: value.count ? rounded(value.sum / value.count) : 0,
          min: value.count ? rounded(value.min) : 0,
          max: value.count ? rounded(value.max) : 0,
        };
      }
      const result = {
        callbackCount,
        renderedFrameCount,
        gateSkippedCallbackCount,
        callbackIntervals: callbackSummary,
        renderedIntervals,
        components: componentSummary,
      };
      reset();
      return result;
    },
  };
}
