(() => {
  'use strict';

  const canvas = document.getElementById('probe');
  const context = canvas.getContext('2d', { alpha: false });
  let paused = false;
  let rate = 1;
  let phase = 0;
  let previous = performance.now();
  let frameCount = 0;
  let reportStart = previous;

  function resize() {
    const scale = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(innerWidth * scale));
    canvas.height = Math.max(1, Math.round(innerHeight * scale));
    context.setTransform(scale, 0, 0, scale, 0, 0);
  }

  function render(now) {
    const elapsed = Math.min(0.1, (now - previous) / 1000);
    previous = now;
    if (!paused) phase += elapsed * rate;

    const gradient = context.createLinearGradient(0, 0, 0, innerHeight);
    gradient.addColorStop(0, '#062d3d');
    gradient.addColorStop(1, '#03151f');
    context.fillStyle = gradient;
    context.fillRect(0, 0, innerWidth, innerHeight);

    const x = innerWidth * (0.5 + 0.32 * Math.sin(phase));
    const y = innerHeight * (0.52 + 0.16 * Math.cos(phase * 0.73));
    context.fillStyle = '#58e1e8';
    context.beginPath();
    context.arc(x, y, 44, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = '#08212b';
    context.font = '600 20px Segoe UI';
    context.fillText('WEBVIEW2 COMPOSITION PROBE', 36, 52);
    context.font = '16px Consolas';
    context.fillText(paused ? 'PAUSED' : 'RUNNING', 36, 80);

    frameCount += 1;
    if (now - reportStart >= 5000) {
      const fps = frameCount * 1000 / (now - reportStart);
      window.chrome.webview.postMessage(`canvas-fps:${fps.toFixed(1)}`);
      reportStart = now;
      frameCount = 0;
    }
    requestAnimationFrame(render);
  }

  window.chrome.webview.addEventListener('message', event => {
    const message = event.data || {};
    if (message.type === 'state') paused = Boolean(message.paused);
    if (message.type === 'rate') rate = Math.max(0, Number(message.fps) || 0) / 60;
  });
  addEventListener('resize', resize);
  resize();
  window.chrome.webview.postMessage('habitat-ready:canvas');
  requestAnimationFrame(render);
})();
