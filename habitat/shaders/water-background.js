export const waterBackgroundVertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const waterBackgroundFragmentShader = `
  uniform float uTime;
  uniform vec3 uTop;
  uniform vec3 uBottom;
  uniform float uShafts;
  varying vec2 vUv;
  void main() {
    float ripple = sin(vUv.x * 7.0 + uTime * 0.11) * 0.012;
    ripple += sin(vUv.x * 13.0 - uTime * 0.075) * 0.006;
    float gradient = smoothstep(0.0, 1.0, vUv.y + ripple);
    vec3 water = mix(uBottom, uTop, gradient);
    float caustic = sin(vUv.x * 19.0 + uTime * 0.17);
    caustic *= sin(vUv.x * 11.0 - uTime * 0.12 + vUv.y * 5.0);
    caustic = smoothstep(0.66, 1.0, caustic) * smoothstep(0.42, 1.0, vUv.y);
    float topGlow = smoothstep(0.54, 1.0, vUv.y) * (0.025 + caustic * 0.028);
    water += vec3(0.23, 0.42, 0.39) * topGlow;
    // Soft light shafts fanning down from the upper centre-right (0 = off).
    vec2 shaftOrigin = vUv - vec2(0.6, 1.08);
    float shaftAngle = atan(shaftOrigin.x, -shaftOrigin.y);
    float shafts = smoothstep(0.45, 1.0, sin(shaftAngle * 19.0 + uTime * 0.045) * 0.5 + 0.5);
    shafts += smoothstep(0.6, 1.0, sin(shaftAngle * 37.0 - uTime * 0.03 + 1.7) * 0.5 + 0.5) * 0.55;
    float shaftFade = smoothstep(0.05, 0.9, vUv.y) * smoothstep(0.62, 0.05, abs(shaftOrigin.x));
    water += vec3(0.22, 0.4, 0.37) * shafts * shaftFade * 0.05 * uShafts;
    float vignette = smoothstep(0.82, 0.28, distance(vUv, vec2(0.52, 0.55)));
    water *= 0.84 + vignette * 0.16;
    gl_FragColor = vec4(water, 1.0);
  }
`;

// Slice B backdrop: the deep water behind the Hero Frame translation. Calm
// vertical gradient, a faint warm glow and restrained shafts from the upper
// left (the hardscape key), darker and cooler toward the upper right. Below
// the floor horizon it is a plain gradient so the hazed rear floor meets it.
// uCalm sets how much darker the upper-right open water is (Slice B: 0.35).
export const waterBackgroundSliceBFragmentShader = `
  uniform float uTime;
  uniform vec3 uTop;
  uniform vec3 uBottom;
  uniform vec3 uGlow;
  uniform float uHorizon;
  uniform float uCalm;
  uniform float uSurfaceStrength;
  varying vec2 vUv;
  void main() {
    float surfaceBand = smoothstep(0.72, 0.94, vUv.y);
    float surfaceWarp = (sin(vUv.x * 21.0 + uTime * 0.19)
      + sin(vUv.x * 37.0 - uTime * 0.14)) * 0.002 * surfaceBand * uSurfaceStrength;
    float gradient = smoothstep(0.0, 1.0, vUv.y + surfaceWarp);
    vec3 water = mix(uBottom, uTop, gradient);
    float above = smoothstep(uHorizon, uHorizon + 0.2, vUv.y);
    // Warm key glow, upper left, very soft.
    float glow = exp(-pow(distance(vUv, vec2(0.18, 0.95)) / 0.42, 2.0));
    water += uGlow * glow * above;
    // Restrained shafts slanting down-right from the upper left.
    vec2 origin = vUv - vec2(0.08, 1.12);
    float angle = atan(origin.x, -origin.y);
    float shafts = smoothstep(0.55, 1.0, sin(angle * 23.0 + uTime * 0.035) * 0.5 + 0.5);
    shafts += smoothstep(0.7, 1.0, sin(angle * 41.0 - uTime * 0.025 + 1.3) * 0.5 + 0.5) * 0.5;
    float shaftFade = smoothstep(uHorizon, 0.95, vUv.y) * smoothstep(0.75, 0.1, vUv.x);
    water += uGlow * 0.55 * shafts * shaftFade * 0.35;
    // Deeper, calmer open water to the upper right.
    float calm = smoothstep(0.35, 1.0, vUv.x) * smoothstep(uHorizon, 1.0, vUv.y);
    water *= 1.0 - uCalm * calm;
    float surfaceRipple = 0.5 + 0.25 * sin(vUv.x * 22.0 + uTime * 0.21)
      + 0.25 * sin(vUv.x * 43.0 - uTime * 0.16);
    float surfaceLight = 1.0 - 0.35 * smoothstep(0.4, 1.0, vUv.x);
    water += (vec3(0.015, 0.025, 0.022)
      + vec3(0.028, 0.047, 0.047) * (0.34 + 0.82 * surfaceRipple))
      * surfaceBand * surfaceLight * uSurfaceStrength;
    gl_FragColor = vec4(water, 1.0);
  }
`;
