import * as THREE from './vendor/three/three.module.js';
import { readAuditConfig } from './audit-config.js';
import { readArtMode } from './core/art-mode.js';
import { createHabitatEngine } from './core/engine.js';
import { createPerformanceRecorder } from './core/performance.js';
import { createPlantedTankForArt } from './habitats/planted-tank/scene.js';

const bridge = window.chrome?.webview;
const canvas = document.getElementById('aquarium');
const diagnostics = document.getElementById('diagnostics');
const auditConfig = readAuditConfig(location);
const artMode = readArtMode(location);
const performanceRecorder = createPerformanceRecorder({ enabled: auditConfig.enabled });
// Measured in the real host (1920x1080, Intel UHD): 4x MSAA multiplied by the
// planted corner's alpha-tested overdraw cost ~31 FPS; without it ~59 FPS at
// a visually near-identical result. The procedural baseline keeps MSAA. The
// context exists before assets load, so a fallback to procedural after an
// asset failure runs without MSAA.
const antialias = artMode !== 'slice-a';
const context = canvas.getContext('webgl2', {
  alpha: false,
  antialias,
  depth: true,
  powerPreference: 'high-performance',
});

function post(message) {
  if (bridge) bridge.postMessage(message);
}

if (!context) {
  post('habitat-failure:webgl2-unavailable');
  throw new Error('WebGL2 is required by Aquarium.exe.');
}

const renderer = new THREE.WebGLRenderer({
  canvas,
  context,
  antialias,
  alpha: false,
});
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2) * auditConfig.renderScale);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.42;
renderer.setClearColor(0x02141d, 1);

const { habitat, art } = await createPlantedTankForArt(renderer, {
  artMode,
  auditConfig,
  performanceRecorder,
  // Imported lazily so even a loader module failure falls back to procedural.
  loadArtGroup: async group => (await import('./core/assets.js')).loadArtGroup(group, {
    maxAnisotropy: Math.min(4, renderer.capabilities.getMaxAnisotropy()),
  }),
  // Deliberately not `habitat-failure:`: the host treats that as a lost
  // runtime and rebuilds. The fallback habitat is healthy, so report as info.
  reportAssetFailure: error => {
    const reason = `${error?.name ?? 'Error'}: ${error?.message ?? error}`;
    console.error('Aquarium art assets unavailable; using procedural environment.', error);
    window.__aquariumAssetFailure = reason;
    post(`habitat-asset-failure:${reason}`);
  },
});
let diagnosticsVisible = new URLSearchParams(location.search).get('diagnostics') === '1';
let previewPaused = false;
let pointerCount = 0;

function formatMetrics(report, prefix = 'habitat-metrics') {
  return `${prefix}:fps=${report.fps.toFixed(1)}`
    + `;frameTimeMs=${report.frameTimeMs.toFixed(2)}`
    + `;fishCount=${report.fishCount}`
    + `;drawCalls=${report.calls}`
    + `;triangles=${report.triangles}`
    + `;pointerCount=${report.pointerCount}`
    + `;reactions=${report.reactions}`
    + `;paused=${report.paused}`
    + `;targetFps=${report.targetFps}`
    + `;art=${art.mode}`
    + `;msaa=${antialias}`
    + `;assetLoadMs=${art.loadMs.toFixed(0)}`
    + `;assetBytes=${art.bytes}`;
}

function presentDiagnostics(report) {
  const message = formatMetrics(report);
  post(message);
  if (report.performance) {
    const auditReport = { config: auditConfig, performance: report.performance };
    post(`audit-performance:${JSON.stringify(auditReport)}`);
    if (auditConfig.enabled) {
      window.__aquariumAuditReports ??= [];
      window.__aquariumAuditReports.push(auditReport);
    }
  }
  diagnostics.textContent = message.replace('habitat-metrics:', '').replaceAll(';', '\n')
    + (report.performance
      ? `\nrenderMedianMs=${report.performance.renderedIntervals.median.toFixed(2)}`
      : '');
  diagnostics.hidden = !diagnosticsVisible;
}

const engine = createHabitatEngine({
  habitat,
  requestFrame: callback => requestAnimationFrame(callback),
  cancelFrame: id => cancelAnimationFrame(id),
  now: () => performance.now(),
  onReady: () => post('habitat-ready:three-webgl2'),
  onDiagnostics: presentDiagnostics,
  targetFps: auditConfig.targetFps ?? 60,
  performanceRecorder,
});

function resize() {
  engine.resize(innerWidth, innerHeight);
}

function updatePointer(present, x = 0, y = 0) {
  pointerCount += 1;
  if (auditConfig.pointerMode === 'ignore') return;
  if (auditConfig.pointerMode === 'stationary' && pointerCount > 1) return;
  engine.setPointer({ present, x, y, z: 0, eventsReceived: pointerCount });
}

if (bridge) {
  bridge.addEventListener('message', event => {
    const message = event.data || {};
    if (message.type === 'pointer') {
      updatePointer(
        Boolean(message.present),
        Math.max(0, Math.min(1, Number(message.x) || 0)),
        Math.max(0, Math.min(1, Number(message.y) || 0)),
      );
    } else if (message.type === 'state') {
      engine.setPaused(Boolean(message.paused));
    } else if (message.type === 'rate') {
      engine.setTargetFps(auditConfig.targetFps
        ?? Math.max(0, Math.min(60, Number(message.fps) || 0)));
    } else if (message.type === 'probe') {
      post(formatMetrics(engine.requestProbe(), 'probe'));
    }
  });
} else {
  addEventListener('pointermove', event => {
    updatePointer(
      true,
      event.clientX / Math.max(1, innerWidth),
      event.clientY / Math.max(1, innerHeight),
    );
  }, { passive: true });
  addEventListener('pointerleave', () => updatePointer(false), { passive: true });
  addEventListener('keydown', event => {
    if (event.code === 'Space') {
      event.preventDefault();
      previewPaused = !previewPaused;
      engine.setPaused(previewPaused);
      engine.requestProbe();
    } else if (event.key.toLowerCase() === 'd') {
      diagnosticsVisible = !diagnosticsVisible;
      engine.requestProbe();
    }
  });
}

addEventListener('resize', resize);
addEventListener('pagehide', () => {
  engine.dispose();
  renderer.dispose();
}, { once: true });
resize();
engine.start();
