// Finite water volume seen from OUTSIDE the tank.
//
// The camera sits in air in front of the front glass. For every shaded
// fragment the view ray enters water where it crosses the front-glass plane;
// only the glass-to-fragment segment is water path. Light returning from the
// surface is attenuated per wavelength, T = exp(-sigma_rgb * d), and the water
// column itself contributes a bounded in-scattered term (1 - T) * waterLight.
// Applied in linear light before tone mapping, on the real materials: no fog,
// no screen-space pass, no extra draw calls.

export const WATER_MODES = Object.freeze(['full', 'extinction', 'off']);
export const DEFAULT_WATER_MODE = 'full';

// Development switch: ?water=off|extinction|full. Anything else -> default.
export function readWaterMode(locationLike) {
  const requested = new URLSearchParams(locationLike?.search ?? '').get('water');
  return WATER_MODES.includes(requested) ? requested : DEFAULT_WATER_MODE;
}

function finiteVector(value, name, { min = 0, max = Infinity } = {}) {
  if (!Array.isArray(value) || value.length !== 3 || value.some(v => !Number.isFinite(v) || v < min || v > max)) {
    throw new RangeError(`water ${name} must be three finite numbers in [${min}, ${max}]`);
  }
  return [...value];
}

// Water path length from a camera in air to a point, given the front-glass
// plane z = glassZ (the tank extends toward -z). Pure JS mirror of the GLSL.
export function waterPathLength(camera, point, glassZ) {
  const dx = point.x - camera.x;
  const dy = point.y - camera.y;
  const dz = point.z - camera.z;
  const length = Math.hypot(dx, dy, dz);
  if (point.z >= glassZ) return 0;                      // in front of the glass: air
  if (camera.z <= glassZ) return length;                // camera already underwater
  const inside = (glassZ - point.z) / (camera.z - point.z);
  return length * Math.min(1, Math.max(0, inside));
}

// Viewed transmittance after the foreground white balance: the eye adapts to
// the colour of the nearest planted layer, so light that crossed only the
// reference distance (the foreground) is shown neutral; everything deeper is
// attenuated relative to it. Equivalent to a per-channel exposure of
// exp(sigma * referenceDistance), clamped so nothing is ever brightened.
export function transmittance(sigma, distance, referenceDistance = 0) {
  return sigma.map(s => Math.exp(-s * Math.max(0, distance - referenceDistance)));
}

export function createWaterVolume({
  mode = DEFAULT_WATER_MODE,
  glassZ = 5,
  sigma,
  scatterColor,
  scatterStrength = 1,
  surfaceY = 7,
  floorY = 0,
  depthLight = 0.45,
  referenceDistance = 0,
} = {}) {
  if (!WATER_MODES.includes(mode)) throw new RangeError(`unknown water mode ${mode}`);
  if (!Number.isFinite(glassZ)) throw new RangeError('water glassZ must be finite');
  const sigmaRgb = finiteVector(sigma, 'sigma', { max: 2 });
  const scatter = finiteVector(scatterColor, 'scatterColor', { max: 4 });
  if (!(scatterStrength >= 0 && scatterStrength <= 2)) throw new RangeError('water scatterStrength out of range');
  if (!(surfaceY > floorY)) throw new RangeError('water surfaceY must be above floorY');
  if (!(depthLight >= 0 && depthLight <= 1)) throw new RangeError('water depthLight must be in [0, 1]');
  if (!(referenceDistance >= 0 && referenceDistance < 20)) throw new RangeError('water referenceDistance out of range');
  const enabled = mode !== 'off';
  return {
    mode,
    enabled,
    glassZ,
    sigma: sigmaRgb,
    scatterColor: scatter,
    scatterStrength: mode === 'full' ? scatterStrength : 0,
    surfaceY,
    floorY,
    depthLight,
    referenceDistance,
    uniforms: {
      uWaterGlassZ: { value: glassZ },
      uWaterSigma: { value: sigmaRgb },
      uWaterScatter: { value: scatter.map(c => c * (mode === 'full' ? scatterStrength : 0)) },
      uWaterSurfaceY: { value: surfaceY },
      uWaterFloorY: { value: floorY },
      uWaterDepthLight: { value: depthLight },
      uWaterReference: { value: referenceDistance },
    },
    cacheKey: `water:${mode}`,
  };
}

const WATER_UNIFORMS = `
uniform float uWaterGlassZ;
uniform vec3 uWaterSigma;
uniform vec3 uWaterScatter;
uniform float uWaterSurfaceY;
uniform float uWaterFloorY;
uniform float uWaterDepthLight;
uniform float uWaterReference;`;

// The water model for one world-space point: transmittance T and the
// in-scattered radiance (1 - T) * waterLight.
const WATER_FUNCTIONS = `
float waterPath(vec3 eye, vec3 point) {
  if (point.z >= uWaterGlassZ) return 0.0;
  float total = length(point - eye);
  if (eye.z <= uWaterGlassZ) return total;
  return total * clamp((uWaterGlassZ - point.z) / (eye.z - point.z), 0.0, 1.0);
}
void waterAt(vec3 world, out vec3 waterT, out vec3 waterIn) {
  float waterD = waterPath(cameraPosition, world);
  waterT = exp(-uWaterSigma * max(0.0, waterD - uWaterReference));
  // The water column is lit from above: in-scattered light is a little
  // weaker toward the floor (evaluated at the path's mean height).
  float entryY = mix(cameraPosition.y, world.y,
    clamp((cameraPosition.z - uWaterGlassZ) / max(1e-4, cameraPosition.z - world.z), 0.0, 1.0));
  float h = clamp((0.5 * (entryY + world.y) - uWaterFloorY) / (uWaterSurfaceY - uWaterFloorY), 0.0, 1.0);
  waterIn = uWaterScatter * mix(uWaterDepthLight, 1.0, h) * (1.0 - waterT);
}`;

const WORLD_POSITION = `
  vec4 waterWorld = vec4(transformed, 1.0);
  #ifdef USE_INSTANCING
    waterWorld = instanceMatrix * waterWorld;
  #endif
  waterWorld = modelMatrix * waterWorld;`;

// Per vertex (default): the model is evaluated once per vertex and
// interpolated. Vegetation and fish triangles are small, and the scene is
// fragment-bound on overlapping alpha-tested foliage, so per-fragment
// evaluation costs measurable frame time for no visible gain.
// Per fragment: exact, for large flat surfaces (the rear boundary) where the
// non-linear path would visibly interpolate across a few huge triangles.
export function injectWater(shader, water, { perFragment = false } = {}) {
  if (!water?.enabled) return shader;
  Object.assign(shader.uniforms, water.uniforms);
  if (perFragment) {
    shader.vertexShader = `varying vec3 vWaterWorld;\n${shader.vertexShader}`
      .replace('#include <project_vertex>', `#include <project_vertex>\n${WORLD_POSITION}\n  vWaterWorld = waterWorld.xyz;`);
    shader.fragmentShader = `${WATER_UNIFORMS}\nvarying vec3 vWaterWorld;\n${WATER_FUNCTIONS}\n${shader.fragmentShader}`
      .replace('#include <opaque_fragment>', `{
    vec3 waterT; vec3 waterIn;
    waterAt(vWaterWorld, waterT, waterIn);
    outgoingLight = outgoingLight * waterT + waterIn;
  }
#include <opaque_fragment>`);
  } else {
    shader.vertexShader = `${WATER_UNIFORMS}\nvarying vec3 vWaterT;\nvarying vec3 vWaterIn;\n${WATER_FUNCTIONS}\n${shader.vertexShader}`
      .replace('#include <project_vertex>', `#include <project_vertex>\n${WORLD_POSITION}\n  waterAt(waterWorld.xyz, vWaterT, vWaterIn);`);
    shader.fragmentShader = `varying vec3 vWaterT;\nvarying vec3 vWaterIn;\n${shader.fragmentShader}`
      .replace('#include <opaque_fragment>', `outgoingLight = outgoingLight * vWaterT + vWaterIn;\n#include <opaque_fragment>`);
  }
  return shader;
}

// Adds the water model to a material without disturbing its own shader
// hooks, alpha test, depth test/write or sidedness.
export function applyWater(material, water, { perFragment = false } = {}) {
  if (!water?.enabled) return material;
  const previous = material.onBeforeCompile;
  const previousKey = material.customProgramCacheKey?.bind(material);
  material.onBeforeCompile = (shader, renderer) => {
    previous?.call(material, shader, renderer);
    injectWater(shader, water, { perFragment });
  };
  material.customProgramCacheKey = () => `${previousKey ? previousKey() : ''}|${water.cacheKey}${perFragment ? ':px' : ''}`;
  material.needsUpdate = true;
  return material;
}
