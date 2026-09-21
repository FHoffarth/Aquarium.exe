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
    float ripple = sin(vUv.x * 7.0 + uTime * 0.13) * 0.012;
    ripple += sin(vUv.x * 13.0 - uTime * 0.09) * 0.006;
    float gradient = smoothstep(0.0, 1.0, vUv.y + ripple);
    vec3 water = mix(uBottom, uTop, gradient);
    gl_FragColor = vec4(water, 1.0);
  }
`;
