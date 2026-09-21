import * as THREE from './vendor/three/three.module.js';

const canvas = document.getElementById('probe');
const context = canvas.getContext('webgl2', {
  alpha: false,
  antialias: true,
  depth: true,
  powerPreference: 'high-performance',
});

if (!context) {
  window.chrome.webview.postMessage('habitat-failure:webgl2-unavailable');
  throw new Error('WebGL2 is required by this feasibility probe.');
}

const renderer = new THREE.WebGLRenderer({ canvas, context, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
renderer.setClearColor(0x031d29, 1);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x031d29);
const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 10);
camera.position.z = 3;

scene.add(new THREE.HemisphereLight(0xb9f5ff, 0x05202c, 2.4));
const keyLight = new THREE.DirectionalLight(0xffffff, 2.0);
keyLight.position.set(-1, 1, 2);
scene.add(keyLight);

const fishColors = [0xf59e3d, 0x61d4c7, 0xb888f8];
const fish = fishColors.map((color, index) => {
  const root = new THREE.Group();
  const bodyMaterial = new THREE.MeshStandardMaterial({ color, roughness: 0.62, metalness: 0 });
  const darkMaterial = new THREE.MeshBasicMaterial({ color: 0x07161d });
  const body = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 12), bodyMaterial);
  body.scale.set(0.12, 0.055, 0.045);
  root.add(body);

  const tail = new THREE.Mesh(new THREE.ConeGeometry(0.065, 0.12, 3), bodyMaterial);
  tail.rotation.z = -Math.PI / 2;
  tail.position.x = -0.145;
  root.add(tail);

  const eye = new THREE.Mesh(new THREE.SphereGeometry(0.012, 10, 6), darkMaterial);
  eye.position.set(0.085, 0.018, 0.044);
  root.add(eye);

  const initial = [
    [-0.55, 0.34, 0.24, 0.04],
    [0.38, 0.02, -0.20, 0.06],
    [-0.10, -0.42, 0.17, -0.05],
  ][index];
  root.position.set(initial[0], initial[1], 0);
  scene.add(root);
  return {
    root,
    velocity: new THREE.Vector2(initial[2], initial[3]),
    phase: index * 2.1,
    reactions: 0,
    reacting: false,
  };
});

const pointer = new THREE.Vector2();
let pointerPresent = false;
let paused = false;
let targetFps = 60;
let previousUpdate = performance.now();
let previousRender = 0;
let reportStart = previousUpdate;
let renderedFrames = 0;
let readySent = false;

function resize() {
  const width = Math.max(1, innerWidth);
  const height = Math.max(1, innerHeight);
  const aspect = width / height;
  camera.left = -aspect;
  camera.right = aspect;
  camera.top = 1;
  camera.bottom = -1;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
}

function updateFish(item, elapsed, aspect) {
  item.phase += elapsed;
  item.velocity.y += Math.sin(item.phase * 1.3) * elapsed * 0.012;

  if (pointerPresent) {
    const away = new THREE.Vector2().subVectors(item.root.position, pointer);
    const distance = away.length();
    const reacting = distance < 0.42;
    if (reacting && distance > 0.001) {
      away.multiplyScalar(1 / distance);
      item.velocity.addScaledVector(away, elapsed * (0.9 - distance));
    }
    if (reacting && !item.reacting) item.reactions += 1;
    item.reacting = reacting;
  } else {
    item.reacting = false;
  }

  const speed = item.velocity.length();
  if (speed > 0.42) item.velocity.multiplyScalar(0.42 / speed);
  item.velocity.multiplyScalar(Math.pow(0.985, elapsed * 60));
  item.root.position.x += item.velocity.x * elapsed;
  item.root.position.y += item.velocity.y * elapsed;

  const horizontalLimit = aspect - 0.20;
  if (item.root.position.x < -horizontalLimit || item.root.position.x > horizontalLimit) {
    item.root.position.x = THREE.MathUtils.clamp(item.root.position.x, -horizontalLimit, horizontalLimit);
    item.velocity.x *= -1;
  }
  if (item.root.position.y < -0.82 || item.root.position.y > 0.82) {
    item.root.position.y = THREE.MathUtils.clamp(item.root.position.y, -0.82, 0.82);
    item.velocity.y *= -1;
  }
  item.root.scale.x = item.velocity.x < 0 ? -1 : 1;
  item.root.rotation.z = THREE.MathUtils.clamp(item.velocity.y * 0.5, -0.18, 0.18);
}

function postDiagnostics(now) {
  const seconds = (now - reportStart) / 1000;
  if (seconds < 5) return;
  const fps = renderedFrames / seconds;
  const reactions = fish.reduce((sum, item) => sum + item.reactions, 0);
  window.chrome.webview.postMessage(
    `three-fps:${fps.toFixed(1)};drawCalls:${renderer.info.render.calls};reactions:${reactions}`,
  );
  reportStart = now;
  renderedFrames = 0;
}

function frame(now) {
  requestAnimationFrame(frame);
  const interval = targetFps > 0 ? 1000 / targetFps : Infinity;
  if (now - previousRender < interval) return;
  previousRender = now;

  const elapsed = Math.min(0.1, (now - previousUpdate) / 1000);
  previousUpdate = now;
  if (!paused) {
    const aspect = innerWidth / Math.max(1, innerHeight);
    for (const item of fish) updateFish(item, elapsed, aspect);
  }
  renderer.render(scene, camera);
  renderedFrames += 1;
  if (!readySent) {
    readySent = true;
    window.chrome.webview.postMessage('habitat-ready:three-webgl2');
  }
  postDiagnostics(now);
}

window.chrome.webview.addEventListener('message', event => {
  const message = event.data || {};
  if (message.type === 'pointer') {
    pointerPresent = Boolean(message.present);
    if (pointerPresent) {
      const aspect = innerWidth / Math.max(1, innerHeight);
      pointer.set((Number(message.x) * 2 - 1) * aspect, 1 - Number(message.y) * 2);
    }
  } else if (message.type === 'state') {
    paused = Boolean(message.paused);
  } else if (message.type === 'rate') {
    targetFps = Math.max(0, Math.min(60, Number(message.fps) || 0));
  } else if (message.type === 'probe') {
    const reactions = fish.reduce((sum, item) => sum + item.reactions, 0);
    window.chrome.webview.postMessage(
      `probe:webgl2=true;paused=${paused};targetFps=${targetFps};reactions=${reactions}`,
    );
  }
});

addEventListener('resize', resize);
resize();
requestAnimationFrame(frame);
