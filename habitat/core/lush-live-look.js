import * as THREE from '../vendor/three/three.module.js';

// Bright freshwater look for the live aquarium: material recovery and
// lighting, derived from the approved Blender source (6dfd62d, audited in
// docs/architecture/lush-live-freshwater-recovery.md). The glTF export kept
// only flat base colours; the source relied on ~3.6 kW of large area lights,
// a leaf transmission light behind the plants, an HSV x2 brightening of the
// photographed broad leaves and Blender's AgX view transform. This module
// restores those intentions on the runtime materials; geometry, placement,
// camera, water model and fish are untouched.

// Per plant family (approved source object): linear multiplier on the source
// base colour, and a thin-leaf transmission weight. Restrained differentiation:
// fresh greens in front, lighter new growth on the feather plants, olive on
// the tall grass, mature darker ribbons that still glow when back-lit.
export const FOLIAGE_FAMILIES = Object.freeze({
  '07 low foreground plants': { tint: [1.35, 1.45, 0.9], transmission: 0.35 },
  '05 irregular small leaf bushes': { tint: [1.2, 1.3, 1.0], transmission: 0.35 },
  '03 fine feather plants': { tint: [1.9, 1.6, 0.8], transmission: 0.4 },
  '01 flowing ribbon plants': { tint: [1.45, 1.5, 1.0], transmission: 0.55 },
  '02 tall grass': { tint: [1.7, 1.35, 0.75], transmission: 0.45 },
  '04 medium stems': { tint: [1.25, 1.25, 0.95], transmission: 0.35 },
  '06 broad leaves': { tint: [1.0, 1.0, 1.0], transmission: 0.3 },
  'supporting stems': { tint: [1.1, 1.1, 0.9], transmission: 0.2 },
});

// Source HSV node on the photographed broad-leaf atlas (saturation 1.25,
// value 2.0) that the glTF export dropped; restored as a colour factor
// (value) plus a slightly stronger green (saturation approximation).
export const BROAD_LEAF_FACTOR = Object.freeze([1.75, 2.0, 1.55]);

// Pale, warm-neutral aquarium sand: the source gravel colours (0.08-0.24
// linear) were only pale under the offline area lights. Lifted and warmed,
// keeping the five gravel tones' relative variation.
export const SAND_FACTOR = Object.freeze([2.7, 2.75, 2.75]);
export const WOOD_FACTOR = Object.freeze([1.45, 1.12, 0.82]);
export const STONE_FACTOR = Object.freeze([1.2, 1.18, 1.12]);
export const STEM_ACCENTS = Object.freeze(['rust accent stems', 'golden olive accent stems']);

// Lighting after the approved offline layout (Blender -> Three: x, z, -y):
// a wide overhead aquarium lamp above the tank centre (falls off toward the
// rear) and a soft fill through the front glass, with a sky/ground
// hemisphere after the source world colour. The offline light behind the
// planting is represented by the leaf transmission term. No shadows.
export const LUSH_LIVE_LIGHTS = Object.freeze({
  hemisphere: { sky: 0xc9dde0, ground: 0x7a7560, intensity: 0.95 },
  overhead: { color: 0xfbfbf6, intensity: 330, position: [-0.8, 9.2, 0.6], target: [0.2, 0, -0.6],
    angle: 1.05, penumbra: 1, decay: 2 },
  frontGlass: { color: 0xe4f0ff, intensity: 0.85, position: [0, 4.5, 12] },
  // Output transform. The source used Blender AgX with a Medium High
  // Contrast look; three.js AgX has no look and rendered flat and grey, and
  // ACES Filmic greys the mid-tones where sand and leaves sit. Khronos PBR
  // Neutral keeps hue and saturation (fresh greens, pale sand, red fish).
  toneMapping: 'neutral',
  exposure: 1.5,
});

export function createLushLiveLights(config = LUSH_LIVE_LIGHTS) {
  const hemisphere = new THREE.HemisphereLight(config.hemisphere.sky, config.hemisphere.ground,
    config.hemisphere.intensity);
  const o = config.overhead;
  const overhead = new THREE.SpotLight(o.color, o.intensity, 0, o.angle, o.penumbra, o.decay);
  overhead.position.set(...o.position);
  overhead.target.position.set(...o.target);
  const directional = ({ color, intensity, position }) => {
    const light = new THREE.DirectionalLight(color, intensity);
    light.position.set(...position);
    return light;
  };
  // Only one directional light: every light costs a full BRDF evaluation on
  // every overlapping foliage fragment (measured: two more directional
  // lights took the host from ~60 to ~50 FPS). The offline rear and right
  // lamps are folded into the hemisphere and the leaf transmission term.
  const frontGlass = directional(config.frontGlass);
  for (const light of [overhead, frontGlass]) light.castShadow = false;
  return { key: overhead, lights: [hemisphere, overhead, overhead.target, frontGlass] };
}

// Rear boundary (real geometry, unlit, inside the water model): clear
// freshwater, lighter where the lamp lights the upper water column, deeper
// toward the floor, with a very low-frequency analytic brightness drift
// (+-3%) so it does not read as a flat painted card. No texture.
export const REAR_WATER = Object.freeze({
  top: '#8ccbe0',
  middle: '#4f95aa',
  bottom: '#26586a',
  variation: 0.03,
});

export function rearColorAt(t, colors = REAR_WATER) {
  const top = new THREE.Color(colors.top);
  const middle = new THREE.Color(colors.middle);
  const bottom = new THREE.Color(colors.bottom);
  return t < 0.5 ? bottom.lerp(middle, t / 0.5) : middle.lerp(top, (t - 0.5) / 0.5);
}

export function createRearMaterial(geometry, colors = REAR_WATER) {
  const position = geometry.getAttribute('position');
  geometry.computeBoundingBox();
  const { min, max } = geometry.boundingBox;
  const data = new Float32Array(position.count * 3);
  for (let index = 0; index < position.count; index += 1) {
    const t = (position.getY(index) - min.y) / Math.max(1e-6, max.y - min.y);
    rearColorAt(t, colors).toArray(data, index * 3);
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(data, 3));
  const material = new THREE.MeshBasicMaterial({ vertexColors: true });
  material.name = 'rear freshwater depth';
  const range = { value: [min.y, max.y] };
  const variation = { value: colors.variation };
  material.onBeforeCompile = shader => {
    shader.uniforms.uRearRange = range;
    shader.uniforms.uRearVariation = variation;
    shader.vertexShader = `varying vec3 vRearPosition;\n${shader.vertexShader}`
      .replace('#include <begin_vertex>', '#include <begin_vertex>\n  vRearPosition = position;');
    // Vertex colours interpolate linearly across 12 big triangles; the
    // gradient is recomputed per fragment (smooth in height) plus the drift.
    shader.fragmentShader = `uniform vec2 uRearRange;\nuniform float uRearVariation;\nvarying vec3 vRearPosition;\n${
      shader.fragmentShader}`.replace('#include <color_fragment>', `#include <color_fragment>
  {
    float rearT = clamp((vRearPosition.y - uRearRange.x) / (uRearRange.y - uRearRange.x), 0.0, 1.0);
    rearT = smoothstep(0.0, 1.0, rearT);
    float drift = sin(vRearPosition.x * 0.37 + 1.3) * 0.6 + sin(vRearPosition.x * 0.83 - vRearPosition.y * 0.41) * 0.4;
    diffuseColor.rgb *= (0.92 + 0.16 * rearT) * (1.0 + uRearVariation * drift);
  }`);
  };
  material.customProgramCacheKey = () => 'rear-freshwater-depth';
  return material;
}

function sourceObjectOf(object) {
  for (let node = object; node; node = node.parent) {
    if (node.userData?.approved_source_object) return node.userData.approved_source_object;
  }
  return null;
}

const baseName = name => name.replace(/\.\d{3}$/, '');

// Thin-leaf transmission: light arriving on the far side of a leaf shows
// through it (the source rendered this with a dedicated light behind the
// plants). Added to the lit colour for the side facing away from the light.
function injectLeafTransmission(shader, uniforms) {
  shader.uniforms.uLeafLightDir = uniforms.direction;
  shader.uniforms.uLeafLightColor = uniforms.color;
  shader.uniforms.uLeafTransmission = uniforms.weight;
  shader.fragmentShader = `uniform vec3 uLeafLightDir;\nuniform vec3 uLeafLightColor;\nuniform float uLeafTransmission;\n${
    shader.fragmentShader}`.replace('#include <opaque_fragment>', `{
    vec3 leafL = normalize((viewMatrix * vec4(uLeafLightDir, 0.0)).xyz);
    float leafBack = max(0.0, -dot(normal, leafL));
    outgoingLight += diffuseColor.rgb * uLeafLightColor * (uLeafTransmission * (0.35 + 0.65 * leafBack));
  }
#include <opaque_fragment>`);
}

// Clones the shared glTF materials per plant family (no geometry or draw-call
// change: every mesh keeps one material per primitive) and applies the
// recovery. Returns the created materials for disposal.
export function recoverMaterials(root, { leafLight }) {
  const created = [];
  const perFamily = new Map();
  root.traverse(object => {
    if (!object.isMesh || !object.material.isMeshStandardMaterial) return;   // rear boundary keeps its own
    const family = sourceObjectOf(object);
    const source = object.material;
    const name = baseName(source.name);
    const key = `${family}|${source.uuid}`;
    let material = perFamily.get(key);
    if (!material) {
      material = source.clone();
      material.name = source.name;
      material.userData.family = family;
      if (name.startsWith('gravel')) {
        material.color.multiply(new THREE.Color(...SAND_FACTOR));
        material.roughness = 0.92;
      } else if (name === 'rooted warm driftwood') {
        material.color.multiply(new THREE.Color(...WOOD_FACTOR));
        material.roughness = 0.85;
      } else if (name.startsWith('scanned stone')) {
        material.color.multiply(new THREE.Color(...STONE_FACTOR));
        material.roughness = 0.9;
      } else if (FOLIAGE_FAMILIES[family]) {
        const treatment = FOLIAGE_FAMILIES[family];
        if (name === 'photographed broad leaf surfaces') {
          material.color.multiply(new THREE.Color(...BROAD_LEAF_FACTOR));
        } else if (!STEM_ACCENTS.includes(name)) {
          material.color.multiply(new THREE.Color(...treatment.tint));
        }
        material.side = THREE.DoubleSide;
        material.roughness = Math.max(0.55, material.roughness);
        const weight = { value: treatment.transmission };
        material.userData.leafTransmission = weight.value;
        const previous = material.onBeforeCompile;
        material.onBeforeCompile = (shader, renderer) => {
          previous?.call(material, shader, renderer);
          injectLeafTransmission(shader, { ...leafLight, weight });
        };
        material.customProgramCacheKey = () => 'leaf-transmission';
      }
      perFamily.set(key, material);
      created.push(material);
    }
    object.material = material;
  });
  return created;
}
