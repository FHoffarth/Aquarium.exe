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
