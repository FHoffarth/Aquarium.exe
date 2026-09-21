import * as THREE from './vendor/three/three.module.js';
import { createHabitatEngine } from './core/engine.js';
import { createPlantedTank } from './habitats/planted-tank/scene.js';

const bridge = window.chrome?.webview;
const canvas = document.getElementById('aquarium');
const diagnostics = document.getElementById('diagnostics');
const context = canvas.getContext('webgl2', {
  alpha: false,
  antialias: true,
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
  antialias: true,
  alpha: false,
});
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;
renderer.setClearColor(0x02141d, 1);

const habitat = createPlantedTank(renderer);
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
    + `;targetFps=${report.targetFps}`;
}

function presentDiagnostics(report) {
  const message = formatMetrics(report);
  post(message);
  diagnostics.textContent = message.replace('habitat-metrics:', '').replaceAll(';', '\n');
  diagnostics.hidden = !diagnosticsVisible;
}

const engine = createHabitatEngine({
  habitat,
  requestFrame: callback => requestAnimationFrame(callback),
  cancelFrame: id => cancelAnimationFrame(id),
  now: () => performance.now(),
  onReady: () => post('habitat-ready:three-webgl2'),
  onDiagnostics: presentDiagnostics,
});

function resize() {
  engine.resize(innerWidth, innerHeight);
}

function updatePointer(present, x = 0, y = 0) {
  pointerCount += 1;
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
      engine.setTargetFps(Math.max(0, Math.min(60, Number(message.fps) || 0)));
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
