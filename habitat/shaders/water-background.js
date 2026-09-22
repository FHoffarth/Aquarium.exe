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
    float vignette = smoothstep(0.82, 0.28, distance(vUv, vec2(0.52, 0.55)));
    water *= 0.84 + vignette * 0.16;
    gl_FragColor = vec4(water, 1.0);
  }
`;
