// Small additions injected into standard PBR materials so lighting stays
// physically based: animated caustics on up-facing surfaces and gentle,
// low-frequency vegetation sway. Both read one shared time uniform.

// Depth haze fades distant surfaces toward the water backdrop. It is mixed
// in after tone mapping and colour-space encoding because the backdrop
// shader writes raw display values; only there can the two meet seamlessly.

export function createEffectUniforms() {
  return {
    uEffectTime: { value: 0 },
    uHazeColor: { value: [0, 0, 0] },
    uHazeRange: { value: [-0.5, -1.75] },
  };
}

export function effectDefines({ caustics = null, sway = null, haze = false } = {}) {
  const defines = [];
  if (caustics) defines.push('AQ_CAUSTICS');
  if (sway) defines.push('AQ_SWAY');
  if (haze) defines.push('AQ_HAZE');
  return defines;
}

export function applyMaterialEffects(material, shared, options = {}) {
  const defines = effectDefines(options);
  if (defines.length === 0) return material;
  material.onBeforeCompile = shader => injectMaterialEffects(shader, shared, options);
  material.customProgramCacheKey = () => `aq:${defines.join(',')}`;
  return material;
}

// Mutates a three.js shader in onBeforeCompile; callers composing their own
// vertex changes (e.g. the hero fish swim wave) call this afterwards.
export function injectMaterialEffects(shader, shared, {
  caustics = null,
  sway = null,
  haze = false,
} = {}) {
  const defines = effectDefines({ caustics, sway, haze });
  if (defines.length === 0) return;
  shader.uniforms.uEffectTime = shared.uEffectTime;
  shader.uniforms.uHazeColor = shared.uHazeColor;
  shader.uniforms.uHazeRange = shared.uHazeRange;
  shader.uniforms.uCausticStrength = { value: caustics?.strength ?? 0 };
  shader.uniforms.uCausticScale = { value: caustics?.scale ?? 1 };
  shader.uniforms.uCausticColor = { value: caustics?.color ?? [1, 1, 1] };
  shader.uniforms.uSwayAmplitude = { value: sway?.amplitude ?? 0 };
  shader.uniforms.uSwayFrequency = { value: sway?.frequency ?? 1 };
  const header = defines.map(name => `#define ${name}`).join('\n');

  shader.vertexShader = `${header}
uniform float uEffectTime;
uniform float uSwayAmplitude;
uniform float uSwayFrequency;
#ifdef AQ_SWAY
attribute float sway;
#endif
varying vec3 vAqWorld;
varying float vAqUp;
${shader.vertexShader}`
    .replace('#include <begin_vertex>', `#include <begin_vertex>
#ifdef AQ_SWAY
  vec3 aqSwayWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;
  float aqPhase = aqSwayWorld.x * 1.7 + aqSwayWorld.z * 1.3;
  transformed.x += sin(uEffectTime * uSwayFrequency + aqPhase) * uSwayAmplitude * sway;
  transformed.z += cos(uEffectTime * uSwayFrequency * 0.77 + aqPhase * 1.3) * uSwayAmplitude * 0.6 * sway;
#endif`)
    .replace('#include <project_vertex>', `#include <project_vertex>
  vAqWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;
  vAqUp = normalize(mat3(modelMatrix) * objectNormal).y;`);

  shader.fragmentShader = `${header}
uniform float uEffectTime;
uniform float uCausticStrength;
uniform float uCausticScale;
uniform vec3 uCausticColor;
uniform vec3 uHazeColor;
uniform vec2 uHazeRange;
varying vec3 vAqWorld;
varying float vAqUp;
${shader.fragmentShader}`
    .replace('#include <fog_fragment>', `#include <fog_fragment>
#ifdef AQ_HAZE
  float aqHaze = smoothstep(uHazeRange.x, uHazeRange.y, vAqWorld.z);
  gl_FragColor.rgb = mix(gl_FragColor.rgb, uHazeColor, aqHaze * 0.96);
#endif`)
    .replace('#include <opaque_fragment>', `#ifdef AQ_CAUSTICS
  vec2 aqP = vAqWorld.xz * uCausticScale;
  float aqA = sin(aqP.x * 3.1 + uEffectTime * 0.55 + sin(aqP.y * 2.3 + uEffectTime * 0.4) * 1.2);
  float aqB = sin(aqP.y * 3.7 - uEffectTime * 0.47 + sin(aqP.x * 2.9 - uEffectTime * 0.35) * 1.1);
  float aqCaustic = pow(max(0.0, 1.0 - abs(aqA + aqB) * 0.5), 6.0);
  outgoingLight += diffuseColor.rgb * uCausticColor * aqCaustic
  * clamp(vAqUp, 0.0, 1.0) * uCausticStrength;
#endif
#include <opaque_fragment>`);
}
