import * as THREE from '../vendor/three/three.module.js';
import { injectMaterialEffects } from '../shaders/material-effects.js';

// Aquarium.exe hero fish: an anatomically shaped small tetra/rasbora-type
// fish rendered as two InstancedMeshes (body+eyes, fin membranes) driven by
// per-instance swim parameters. The simulation stays authoritative; this
// module only reads fish state and derives rendering from it.
//
// Local frame: +X toward the snout, +Y dorsal, Z lateral. Anatomy is
// authored in "s" units along the body: s = 0 snout, s = 1 caudal base
// (hypural), caudal lobe tips at ~1.33. Local x = (PIVOT - s) * K.

export const K = 0.5;              // world units per s: total length ~0.67 like production
export const PIVOT = 0.3;          // s of the swimming pivot (instance origin)

// Stations: s, dorsal half-depth, ventral half-depth, half-width,
// dorsal fullness exponent, ventral fullness exponent (2 = ellipse,
// < 2 pinched keel, > 2 fuller). Silver tetra/rasbora proportions:
// greatest depth ~0.3 SL just behind the head, head ~0.26 SL, thin peduncle.
const STATIONS = [
  [0.000, 0.000, 0.000, 0.000, 2.0, 2.0],
  [0.006, 0.017, 0.013, 0.012, 2.0, 2.0],
  [0.025, 0.034, 0.028, 0.022, 2.0, 2.0],
  [0.045, 0.047, 0.042, 0.03, 2.0, 2.1],
  [0.070, 0.063, 0.058, 0.034, 2.0, 2.2],
  [0.110, 0.087, 0.084, 0.042, 1.95, 2.3],
  [0.160, 0.110, 0.110, 0.048, 1.9, 2.35],
  [0.215, 0.127, 0.132, 0.053, 1.9, 2.35],
  [0.250, 0.135, 0.142, 0.054, 1.85, 2.2],
  [0.320, 0.145, 0.153, 0.056, 1.8, 2.15],
  [0.400, 0.146, 0.154, 0.055, 1.8, 2.1],
  [0.480, 0.138, 0.143, 0.051, 1.8, 2.05],
  [0.570, 0.121, 0.122, 0.045, 1.8, 2.0],
  [0.660, 0.098, 0.095, 0.037, 1.85, 2.0],
  [0.750, 0.074, 0.068, 0.028, 1.9, 1.95],
  [0.830, 0.055, 0.050, 0.020, 1.9, 1.9],
  [0.890, 0.046, 0.042, 0.015, 1.9, 1.9],
  [0.940, 0.047, 0.043, 0.012, 1.9, 1.9],
  [0.975, 0.053, 0.049, 0.009, 1.9, 1.9],
  [1.000, 0.057, 0.053, 0.006, 1.9, 1.9],
];

const EYE = { s: 0.104, lift: 0.024, radius: 0.034, bulge: 0.3 };
const OPERCLE = { s: 0.238, bow: 0.03 };
const BODY_RINGS = 57;
const BODY_SEGMENTS = 28;

// Fin part ids (vertex attribute aPart).
export const PART = Object.freeze({
  body: 0, eye: 1, caudal: 10, dorsal: 11, adipose: 12, anal: 13,
  pelvicL: 14, pelvicR: 15, pectoralL: 16, pectoralR: 17,
});

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function smoothstep(edge0, edge1, x) {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

function mix(a, b, t) {
  return a + (b - a) * t;
}

function gauss(x, center, width) {
  return Math.exp(-(((x - center) / width) ** 2));
}

function catmullRom(p0, p1, p2, p3, t) {
  const t2 = t * t;
  return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
    + (-p0 + 3 * p1 - 3 * p2 + p3) * t2 * t);
}

// ------------------------------------------------------------- anatomy

export function station(s) {
  const x = clamp(s, 0, 1);
  let index = 0;
  while (index < STATIONS.length - 2 && STATIONS[index + 1][0] < x) index += 1;
  const a = STATIONS[Math.max(0, index - 1)];
  const b = STATIONS[index];
  const c = STATIONS[index + 1];
  const d = STATIONS[Math.min(STATIONS.length - 1, index + 2)];
  const t = (x - b[0]) / Math.max(1e-6, c[0] - b[0]);
  const channel = i => catmullRom(a[i], b[i], c[i], d[i], t);
  const top = Math.max(0, channel(1));
  const bottom = Math.max(0, channel(2));
  // Terminal, slightly upturned mouth; a faint dorsal arch over the trunk.
  const center = (top - bottom) * 0.5
    + 0.011 * (1 - smoothstep(0, 0.07, x))
    + 0.004 * gauss(x, 0.42, 0.25);
  return {
    top,
    bottom,
    width: Math.max(0, channel(3)),
    fullUp: channel(4),
    fullDown: channel(5),
    center,
  };
}

function dorsalY(s) {
  const p = station(s);
  return p.center + p.top;
}

function ventralY(s) {
  const p = station(s);
  return p.center - p.bottom;
}

function superPow(value, exponent) {
  return Math.sign(value) * Math.abs(value) ** (2 / exponent);
}

// Lateral half-width of the body surface at (s, y), including head anatomy.
function lateral(s, y, p, up) {
  let z = p.width;
  // Opercle: a slight lip at the gill-cover edge, bowed back top and bottom.
  const edge = OPERCLE.s + OPERCLE.bow * (up * up);
  z *= 1 + 0.022 * gauss(s, edge - 0.008, 0.014) - 0.012 * gauss(s, edge + 0.014, 0.014);
  // Mouth cleft: a shallow groove from the snout tip back along the jaw line.
  const cleftY = p.center - 0.004;
  z *= 1 - 0.28 * gauss(y, cleftY, 0.006) * (1 - smoothstep(0.02, 0.05, s)) * smoothstep(0.0, 0.01, s);
  // Orbit: the eye sits in a shallow socket rather than on the surface.
  const eyeY = station(EYE.s).center + EYE.lift;
  const d = Math.hypot(s - EYE.s, y - eyeY) / (EYE.radius * 1.35);
  if (d < 1) z *= 1 - 0.16 * (1 - d) * (1 - d);
  return z;
}

function ringParameter(t) {
  // Seam on the belly; extra columns at the dorsal and ventral silhouette.
  return Math.PI + 2 * Math.PI * t - 0.18 * Math.sin(4 * Math.PI * t);
}

function bodyStations(count) {
  // Inverse-CDF sampling of a density that concentrates rings at the
  // snout, the opercle and the caudal peduncle.
  const samples = 2000;
  const density = s => 1 + 2.2 * gauss(s, 0.03, 0.05) + 1.2 * gauss(s, OPERCLE.s, 0.04)
    + 1.6 * gauss(s, 0.93, 0.07);
  const cumulative = [0];
  for (let i = 1; i <= samples; i += 1) {
    cumulative.push(cumulative[i - 1] + density(i / samples));
  }
  const total = cumulative[samples];
  const result = [];
  let j = 0;
  for (let ring = 0; ring < count; ring += 1) {
    const target = (ring / (count - 1)) * total;
    while (j < samples && cumulative[j + 1] < target) j += 1;
    result.push(Math.min(1, j / samples));
  }
  result[count - 1] = 1;
  return result;
}

// ------------------------------------------------------------ geometry

class Builder {
  constructor() {
    this.position = [];
    this.uv = [];
    this.part = [];
    this.progress = [];
    this.surface = [];
    this.index = [];
  }

  add(s, y, z, u, v, part, progress = 0, surface = 0) {
    this.position.push((PIVOT - s) * K, y * K, z * K);
    this.uv.push(u, v);
    this.part.push(part);
    this.progress.push(progress);
    this.surface.push(surface);
    return this.part.length - 1;
  }

  geometry() {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(this.position, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
    geometry.setAttribute('aPart', new THREE.Float32BufferAttribute(this.part, 1));
    geometry.setAttribute('aProgress', new THREE.Float32BufferAttribute(this.progress, 1));
    geometry.setAttribute('aSurface', new THREE.Float32BufferAttribute(this.surface, 1));
    geometry.setIndex(this.index);
    geometry.computeVertexNormals();
    return geometry;
  }
}

function addBody(builder) {
  const rings = bodyStations(BODY_RINGS);
  const rows = rings.map(s => {
    const p = station(s);
    const row = [];
    for (let segment = 0; segment <= BODY_SEGMENTS; segment += 1) {
      const theta = ringParameter(segment / BODY_SEGMENTS);
      const up = Math.cos(theta);
      const radius = up >= 0 ? p.top : p.bottom;
      const exponent = up >= 0 ? p.fullUp : p.fullDown;
      const y = p.center + superPow(up, exponent) * radius;
      const z = superPow(Math.sin(theta), exponent) * lateral(s, y, p, up);
      row.push(builder.add(s, y, z, s, segment / BODY_SEGMENTS, PART.body, 0, up));
    }
    return row;
  });
  for (let r = 0; r < rows.length - 1; r += 1) {
    for (let c = 0; c < BODY_SEGMENTS; c += 1) {
      const a = rows[r][c];
      const b = rows[r + 1][c];
      builder.index.push(a, b, rows[r][c + 1], b, rows[r + 1][c + 1], rows[r][c + 1]);
    }
  }
  return rows;
}

function addEyes(builder) {
  const p = station(EYE.s);
  const latitudes = 9;
  const longitudes = 16;
  for (const side of [1, -1]) {
    const centerY = p.center + EYE.lift;
    const socket = lateral(EYE.s, centerY, p, 0.3);
    const first = builder.part.length;
    for (let lat = 0; lat <= latitudes; lat += 1) {
      // Only the outer cap is built; it meets the socket at its rim.
      const phi = (Math.PI * 0.62 * lat) / latitudes;
      for (let lon = 0; lon <= longitudes; lon += 1) {
        const theta = (2 * Math.PI * lon) / longitudes;
        const ds = Math.sin(phi) * Math.cos(theta) * EYE.radius;
        const dy = Math.sin(phi) * Math.sin(theta) * EYE.radius;
        const dz = (Math.cos(phi) - Math.cos(Math.PI * 0.62)) * EYE.radius * EYE.bulge;
        // UVs of the head skin under the eye, so the rim blends into the head.
        const up = clamp((centerY + dy - p.center) / Math.max(1e-4, p.top), -1, 1);
        builder.add(EYE.s + ds, centerY + dy, side * (socket * 0.84 + dz), EYE.s + ds,
          Math.acos(-up) / (2 * Math.PI), PART.eye, 0, Math.cos(phi));
      }
    }
    for (let lat = 0; lat < latitudes; lat += 1) {
      for (let lon = 0; lon < longitudes; lon += 1) {
        const a = first + lat * (longitudes + 1) + lon;
        const b = a + longitudes + 1;
        if (side > 0) builder.index.push(a, a + 1, b, b, a + 1, b + 1);
        else builder.index.push(a, b, a + 1, b, b + 1, a + 1);
      }
    }
  }
}

// A fin membrane: rays fan from an insertion line on the body to a free edge.
function addFin(builder, part, rays, steps, ray) {
  const grid = [];
  for (let r = 0; r < rays; r += 1) {
    const u = r / (rays - 1);
    const { base, edge, bend = 0 } = ray(u);
    const column = [];
    for (let k = 0; k <= steps; k += 1) {
      const t = k / steps;
      const sag = Math.sin(Math.PI * t) * bend;
      column.push(builder.add(
        mix(base[0], edge[0], t),
        mix(base[1], edge[1], t) + sag,
        mix(base[2], edge[2], t),
        u,
        t,
        part,
        t,
      ));
    }
    grid.push(column);
  }
  for (let r = 0; r < rays - 1; r += 1) {
    for (let k = 0; k < steps; k += 1) {
      const a = grid[r][k];
      const b = grid[r + 1][k];
      builder.index.push(a, b, grid[r][k + 1], b, grid[r + 1][k + 1], grid[r][k + 1]);
    }
  }
}

function addFins(builder) {
  const sink = 0.006;
  // Caudal: forked, lobes swept back, a shallow rounded notch.
  addFin(builder, PART.caudal, 17, 6, u => {
    const baseS = 0.972;
    const base = [baseS, mix(dorsalY(baseS) - sink, ventralY(baseS) + sink, u), 0];
    let edge;
    if (u < 0.5) {
      const t = u / 0.5;
      edge = [mix(1.33, 1.165, t ** 0.7), mix(0.178, 0.012, t) + 0.012 * Math.sin(Math.PI * t), 0];
    } else {
      const t = (u - 0.5) / 0.5;
      edge = [mix(1.165, 1.32, t ** 1.4), mix(-0.01, -0.17, t) - 0.012 * Math.sin(Math.PI * t), 0];
    }
    return { base, edge };
  });
  // Dorsal: origin just behind greatest depth, tall leading rays, swept back.
  addFin(builder, PART.dorsal, 10, 5, u => {
    const s = mix(0.425, 0.53, u);
    const height = mix(0.148, 0.028, u ** 0.75);
    return {
      base: [s, dorsalY(s) - sink, 0],
      edge: [s + mix(0.07, 0.085, u), dorsalY(s) + height, 0],
      bend: -0.006 * u,
    };
  });
  addFin(builder, PART.adipose, 4, 2, u => {
    const s = mix(0.8, 0.842, u);
    return {
      base: [s, dorsalY(s) - sink * 0.5, 0],
      edge: [s + 0.02, dorsalY(s) + mix(0.021, 0.005, u), 0],
    };
  });
  // Anal: long tetra anal fin, deepest anteriorly.
  addFin(builder, PART.anal, 13, 5, u => {
    const s = mix(0.6, 0.868, u);
    const depth = mix(0.1, 0.024, u ** 0.85);
    return {
      base: [s, ventralY(s) + sink, 0],
      edge: [s + 0.05, ventralY(s) - depth, 0],
      bend: 0.004,
    };
  });
  for (const [side, pelvic, pectoral] of [[1, PART.pelvicL, PART.pectoralL],
    [-1, PART.pelvicR, PART.pectoralR]]) {
    addFin(builder, pelvic, 5, 3, u => {
      const s = mix(0.43, 0.47, u);
      const p = station(s);
      const y = p.center - p.bottom * 0.84;
      const z = side * p.width * 0.42;
      return { base: [s, y, z], edge: [s + 0.1, y - 0.04, z + side * 0.022] };
    });
    addFin(builder, pectoral, 6, 4, u => {
      const s = mix(OPERCLE.s + 0.004, OPERCLE.s + 0.036, u);
      const p = station(s);
      const y = p.center - p.bottom * 0.52;
      const z = side * p.width * 0.9;
      return {
        base: [s, y, z],
        edge: [s + mix(0.13, 0.1, u), y - mix(0.012, 0.045, u), z + side * 0.036],
      };
    });
  }
}

export function buildHeroFishGeometry() {
  const body = new Builder();
  const rows = addBody(body);
  addEyes(body);
  const fins = new Builder();
  addFins(fins);
  const bodyGeometry = body.geometry();
  // Weld normals across the belly seam.
  const normal = bodyGeometry.attributes.normal;
  for (const row of rows) {
    const first = row[0];
    const last = row[BODY_SEGMENTS];
    const n = new THREE.Vector3(
      normal.getX(first) + normal.getX(last),
      normal.getY(first) + normal.getY(last),
      normal.getZ(first) + normal.getZ(last),
    ).normalize();
    normal.setXYZ(first, n.x, n.y, n.z);
    normal.setXYZ(last, n.x, n.y, n.z);
  }
  return { body: bodyGeometry, fins: fins.geometry() };
}

// ------------------------------------------------------------ textures

function hash2(x, y) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263)) >>> 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177) >>> 0;
  return ((h ^ (h >>> 16)) >>> 0) / 0x100000000;
}

function noise(x, y) {
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const fx = x - x0;
  const fy = y - y0;
  const sx = fx * fx * (3 - 2 * fx);
  const sy = fy * fy * (3 - 2 * fy);
  return mix(mix(hash2(x0, y0), hash2(x0 + 1, y0), sx),
    mix(hash2(x0, y0 + 1), hash2(x0 + 1, y0 + 1), sx), sy);
}

function mixRGB(a, b, t) {
  return [mix(a[0], b[0], t), mix(a[1], b[1], t), mix(a[2], b[2], t)];
}

function srgb(hex) {
  return [(hex >> 16 & 255) / 255, (hex >> 8 & 255) / 255, (hex & 255) / 255];
}

// Body: pearl-silver base, darker dorsum, warm pale belly, a restrained teal
// band along the flank, faint opercle and scale reticulation.
export function shadeBody(s, v) {
  const h = -Math.cos(2 * Math.PI * v);     // +1 dorsal ridge, -1 belly
  const dorsum = srgb(0x151a13);
  const shoulder = srgb(0x3f463a);
  const flank = srgb(0xaeb4ac);
  const belly = srgb(0xd9ccb4);
  let color;
  if (h > 0.22) color = mixRGB(shoulder, dorsum, smoothstep(0.22, 0.7, h));
  else if (h > -0.25) color = mixRGB(flank, shoulder, smoothstep(-0.25, 0.22, h));
  else color = mixRGB(flank, belly, smoothstep(-0.3, -0.9, h));
  // Head: darker nape, pearl cheek, faint warm opercle.
  const head = 1 - smoothstep(0.14, 0.27, s);
  color = mixRGB(color, srgb(0x3f4845), head * smoothstep(0.35, 0.8, h) * 0.5);
  color = mixRGB(color, srgb(0xd8d0bd), head * smoothstep(0.25, -0.4, h) * 0.35);
  const opercle = gauss(s, OPERCLE.s + 0.03 * h * h, 0.008) * smoothstep(0.7, -0.2, h);
  color = mixRGB(color, srgb(0x8c7f68), opercle * 0.2);
  // Teal band: mid-flank, strongest mid-body, fading at both ends.
  const bandCenter = 0.12 + 0.03 * Math.sin(s * 3);
  const along = smoothstep(0.24, 0.36, s) * smoothstep(0.93, 0.7, s);
  const band = gauss(h, bandCenter, 0.09) * along;
  color = mixRGB(color, srgb(0x2f8683), band * 0.5);
  color = mixRGB(color, srgb(0x2f4a4a), gauss(h, bandCenter + 0.16, 0.04) * along * 0.25);
  // Warm blush at the caudal peduncle (ties to the fin colour).
  color = mixRGB(color, srgb(0xc8704d), smoothstep(0.84, 0.98, s) * smoothstep(-0.7, 0.3, h) * 0.3);
  // Scale reticulation: offset rows of scales, darker at each exposed edge.
  const row = h * 7.5;
  const column = s * 46 + 0.5 * Math.floor(row);
  const cellX = column - Math.floor(column) - 0.5;
  const cellY = row - Math.floor(row) - 0.5;
  const jitter = hash2(Math.floor(column), Math.floor(row) + 97);
  const outline = smoothstep(0.36, 0.5, Math.hypot(cellX * 1.1 + 0.1 * (jitter - 0.5), cellY + 0.08 * (0.5 - jitter)));
  const fadeRows = smoothstep(0.95, 0.4, Math.abs(h));
  const shade = (1 - 0.055 * outline * fadeRows * (0.6 + 0.8 * jitter) * smoothstep(0.24, 0.34, s) + 0.06 * (noise(s * 16, v * 11) - 0.5))
    * (1 - 0.55 * gauss(h, -0.03, 0.05) * (1 - smoothstep(0.03, 0.055, s)));
  return [color[0] * shade, color[1] * shade, color[2] * shade, 1];
}

// Optical masks: R iridescence, G roughness, B metalness (guanine silvering).
export function shadeMask(s, v) {
  const h = -Math.cos(2 * Math.PI * v);
  const along = smoothstep(0.24, 0.36, s) * smoothstep(0.95, 0.7, s);
  const bandCenter = 0.12 + 0.03 * Math.sin(s * 3);
  const band = gauss(h, bandCenter, 0.11) * along;
  const flank = smoothstep(0.85, 0.1, Math.abs(h)) * smoothstep(0.1, 0.3, s);
  const iridescence = clamp(0.18 + 0.55 * band + 0.1 * flank, 0, 1);
  const roughness = clamp(0.42 - 0.12 * flank - 0.06 * band + 0.1 * smoothstep(0.5, 0.95, h), 0.2, 0.7);
  const metalness = clamp(0.08 + 0.5 * flank * (1 - 0.4 * band), 0, 1);
  return [iridescence, roughness, metalness, 1];
}

// Fin membrane: warm red-orange at the base and leading rays, clearing
// toward the edge; rays slightly denser than membrane.
export function shadeFin(u, v) {
  const rays = Math.abs(Math.sin(u * Math.PI * 8.5)) ** 14;
  const edge = 1 - smoothstep(0.8, 1.0, v);
  const alpha = (mix(0.56, 0.16, v ** 0.8) + rays * 0.12) * edge;
  const warm = srgb(0xc4553a);
  const pale = srgb(0xe9ddd0);
  const color = mixRGB(warm, pale, smoothstep(0.15, 0.85, v));
  const ray = 1 + rays * 0.15;
  return [color[0] * ray, color[1] * ray, color[2] * ray, alpha];
}

function dataTexture(width, height, shade, colorSpace) {
  const data = new Uint8Array(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const rgba = shade((x + 0.5) / width, (y + 0.5) / height);
      const offset = (y * width + x) * 4;
      for (let channel = 0; channel < 4; channel += 1) {
        data[offset + channel] = clamp(Math.round(rgba[channel] * 255), 0, 255);
      }
    }
  }
  const texture = new THREE.DataTexture(data, width, height, THREE.RGBAFormat);
  texture.colorSpace = colorSpace;
  texture.wrapS = THREE.ClampToEdgeWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;   // scale detail fades with distance
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}

// Small prefiltered environment for the fish only: bright aquarium lamp
// above, teal water around, dark substrate below. Gives wet skin and silver
// flanks something real to reflect without touching the scene lighting.
function fishEnvironment(renderer) {
  if (!renderer?.isWebGLRenderer) return null;
  const scene = new THREE.Scene();
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(10, 32, 16),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      vertexShader: 'varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `varying vec3 vDir;
        void main(){
          float y = vDir.y;
          vec3 water = mix(vec3(0.05, 0.16, 0.17), vec3(0.2, 0.46, 0.46), smoothstep(-0.2, 0.6, y));
          vec3 floorTone = vec3(0.04, 0.05, 0.04);
          vec3 c = mix(floorTone, water, smoothstep(-0.55, -0.1, y));
          float lamp = smoothstep(0.82, 0.97, y) * (0.7 + 0.3 * smoothstep(0.2, 0.9, vDir.z + 0.5));
          c += vec3(1.3, 1.2, 1.05) * lamp;
          gl_FragColor = vec4(c, 1.0);
        }`,
    }),
  );
  scene.add(sphere);
  const generator = new THREE.PMREMGenerator(renderer);
  // A smooth gradient: a 64px cube (~0.6 MB half-float) is enough.
  const target = generator.fromScene(scene, 0.02, 0.1, 100, { size: 64 });
  generator.dispose();
  sphere.geometry.dispose();
  sphere.material.dispose();
  return target;
}

// ------------------------------------------------------------ shaders

const SWIM_VERTEX = /* glsl */ `
attribute float aPart;
attribute float aProgress;
attribute float aSurface;
attribute vec4 aSwim;   // per fish: wave phase, wave amplitude, turn curvature, pectoral brake
attribute vec2 aFin;    // per fish: fin phase, hover effort
varying float vFishPart;
varying float vFishSurface;
varying float vFishS;
const float HF_PIVOT = ${PIVOT.toFixed(3)};
const float HF_K = ${K.toFixed(3)};

// Lateral spine angle at body station s: a travelling wave whose amplitude
// grows from behind the head to the tail, a C-bend for turns, and a small
// head recoil. The head stays nearly still.
float hfSpineAngle(float s) {
  float envelope = pow(clamp((s - 0.12) / 1.2, 0.0, 1.0), 1.45);
  float wave = aSwim.y * envelope * sin(aSwim.x - s * 5.3);
  float along = s - HF_PIVOT;
  float turn = aSwim.z * along * (along < 0.0 ? 0.3 : 1.0);
  return wave + turn - 0.035 * aSwim.y * sin(aSwim.x);
}

vec3 hfFinMotion(vec3 p, float s) {
  if (aPart > 15.5) {
    float side = aPart < 16.5 ? 1.0 : -1.0;
    float beat = sin(aFin.x + side * 0.8);
    p.z += side * aProgress * (0.012 * beat * (0.3 + aFin.y) + 0.018 * aSwim.w) * HF_K;
    p.x += aProgress * (0.005 * beat - 0.03 * aSwim.w) * HF_K;
    p.y += aProgress * 0.006 * cos(aFin.x + side * 0.8) * HF_K;
  } else if (aPart > 13.5) {
    float side = aPart < 14.5 ? 1.0 : -1.0;
    p.z += side * aProgress * 0.005 * sin(aFin.x * 0.8 + side) * HF_K;
  } else if (aPart > 9.5 && aPart < 10.5) {
    p.z += aSwim.y * 0.07 * aProgress * aProgress * sin(aSwim.x - s * 5.3 - 0.7) * HF_K;
  } else if (aPart > 10.5) {
    p.z += aProgress * 0.005 * sin(aFin.x * 0.7 - s * 9.0) * HF_K;
  }
  return p;
}

// Bend the body along the spine without stretching it: integrate the spine
// from the pivot, then place the cross-section perpendicular to it.
vec3 hfBend(vec3 p, inout vec3 n) {
  float s = HF_PIVOT - p.x / HF_K;
  float along = s - HF_PIVOT;
  vec2 spine = vec2(0.0);
  float stepLength = along / 6.0;
  for (int i = 0; i < 6; i++) {
    float angle = hfSpineAngle(HF_PIVOT + (float(i) + 0.5) * stepLength);
    spine += vec2(-cos(angle), sin(angle)) * stepLength;
  }
  float theta = hfSpineAngle(s);
  float c = cos(theta);
  float sn = sin(theta);
  n = normalize(vec3(n.x * c + n.z * sn, n.y, -n.x * sn + n.z * c));
  return vec3(spine.x * HF_K + p.z * sn, p.y, spine.y * HF_K + p.z * c);
}
`;

function applyHeroShader(material, {
  key, effectUniforms, albedo = '', optics = '', scatter = '', physical = '',
}) {
  material.onBeforeCompile = shader => {
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', `#include <common>\n${SWIM_VERTEX}`)
      .replace('#include <beginnormal_vertex>', `vec3 objectNormal = vec3(normal);
  float hfS = HF_PIVOT - position.x / HF_K;
  vec3 hfPosition = hfBend(hfFinMotion(position, hfS), objectNormal);
  vFishPart = aPart;
  vFishSurface = aSurface;
  vFishS = hfS;`)
      .replace('#include <begin_vertex>', 'vec3 transformed = hfPosition;');
    shader.fragmentShader = `varying float vFishPart;\nvarying float vFishSurface;\nvarying float vFishS;\n${shader.fragmentShader}`;
    if (albedo) {
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <color_fragment>', `#include <color_fragment>\n${albedo}`);
    }
    if (optics) {
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <metalnessmap_fragment>', `#include <metalnessmap_fragment>
${optics}`);
    }
    if (physical) {
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <lights_physical_fragment>', `#include <lights_physical_fragment>\n${physical}`);
    }
    if (scatter) {
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <opaque_fragment>', `${scatter}\n#include <opaque_fragment>`);
    }
    if (effectUniforms) {
      injectMaterialEffects(shader, effectUniforms, {
        caustics: { strength: 0.32, scale: 1.25, color: [0.62, 0.86, 0.8] },
        haze: true,
      });
    }
  };
  material.customProgramCacheKey = () => `hero-fish:${key}:${effectUniforms ? 'fx' : 'plain'}`;
  return material;
}

// Eye (part 1): dark pupil, warm iris, dark socket; the corneal highlight
// is real clearcoat specular from the aquarium lamp and environment.
const EYE_ALBEDO = /* glsl */ `
  if (vFishPart > 0.5 && vFishPart < 1.5) {
    float iris = smoothstep(0.25, 0.45, vFishSurface);
    float pupil = smoothstep(0.86, 0.885, vFishSurface);
    vec3 socket = diffuseColor.rgb * 0.75;
    vec3 irisColour = mix(vec3(0.17, 0.15, 0.12), vec3(0.16, 0.1, 0.04), smoothstep(0.35, 0.84, vFishSurface));
    diffuseColor.rgb = mix(mix(socket, irisColour, iris), vec3(0.008, 0.01, 0.014), pupil);
  }`;

// The iris is guanine-silvered like the flank: reflective rather than a
// bright diffuse disc.
const EYE_OPTICS = /* glsl */ `
  if (vFishPart > 0.5 && vFishPart < 1.5) {
    float irisMetal = smoothstep(0.25, 0.45, vFishSurface) * (1.0 - smoothstep(0.86, 0.885, vFishSurface));
    metalnessFactor = 0.75 * irisMetal;
    roughnessFactor = mix(0.45, 0.3, irisMetal);
  }`;

const EYE_PHYSICAL = /* glsl */ `
  if (vFishPart > 0.5 && vFishPart < 1.5) {
    #ifdef USE_CLEARCOAT
      material.clearcoat = smoothstep(0.35, 0.75, vFishSurface);
      material.clearcoatRoughness = 0.03;
    #endif
  }`;

// Thin tissue: light scattered through the peduncle and belly edge, plus a
// soft rim where the body turns away. Scaled by albedo; never self-lit.
const BODY_SCATTER = /* glsl */ `
  if (vFishPart < 0.5) {
    float rim = pow(1.0 - clamp(dot(normal, normalize(vViewPosition)), 0.0, 1.0), 2.5);
    float thin = smoothstep(0.72, 0.97, vFishS);
    float belly = clamp(-vFishSurface, 0.0, 1.0);
    outgoingLight += diffuseColor.rgb * (vec3(0.13, 0.17, 0.17) * rim
      + vec3(0.26, 0.13, 0.08) * thin * (0.35 + rim)
      + vec3(0.05, 0.035, 0.025) * belly);
  }`;

const FIN_SCATTER = /* glsl */ `
  float facing = abs(dot(normal, normalize(vViewPosition)));
  outgoingLight += diffuseColor.rgb * (0.14 + 0.24 * (1.0 - facing));`;

// ------------------------------------------------------------ render state

const MAX_PITCH = 0.42;
const TAU = Math.PI * 2;

function wrapAngle(angle) {
  return Math.atan2(Math.sin(angle), Math.cos(angle));
}

// Render-side state per fish, derived only from simulation state: smoothed
// heading, integrated swim phase and gait parameters. Nothing is written
// back into the simulation.
export function createSwimAnimator() {
  const states = new Map();
  return function animate(key, fish, simulationTime) {
    const speed = Math.hypot(fish.velocity.x, fish.velocity.y, fish.velocity.z);
    const maximum = Math.max(0.05, fish.maximumSpeed ?? 0.45);
    const speedRatio = clamp(speed / maximum, 0, 1.5);
    const horizontal = Math.hypot(fish.velocity.x, fish.velocity.z);
    let state = states.get(key);
    if (!state) {
      state = {
        time: simulationTime,
        yaw: Math.atan2(fish.velocity.z, fish.velocity.x || 1e-4),
        pitch: 0,
        phase: (fish.visualPhase ?? 0),
        finPhase: (fish.visualPhase ?? 0) * 1.7,
        speed,
        curvature: 0,
        brake: 0,
        yawRate: 0,
      };
      states.set(key, state);
    }
    const dt = clamp(simulationTime - state.time, 0, 0.1);
    state.time = simulationTime;
    const boost = clamp(fish.cursorBoost ?? 0, 0, 1);

    // Heading: turn at a limited rate; reversals pass through facing the
    // camera (+Z) so the fish turns its head toward the viewer.
    if (horizontal > 0.15 * Math.max(speed, 1e-4) && horizontal > 1e-4) {
      const target = Math.atan2(fish.velocity.z, fish.velocity.x);
      let delta = wrapAngle(target - state.yaw);
      if (Math.abs(delta) > 0.75 * Math.PI) {
        const other = delta - Math.sign(delta) * TAU;
        if (Math.sin(state.yaw + other / 2) > Math.sin(state.yaw + delta / 2)) delta = other;
      }
      const maxStep = (3.0 + 3.0 * boost) * dt;
      const step = clamp(delta, -maxStep, maxStep);
      state.yaw = wrapAngle(state.yaw + step);
      state.yawRate = dt > 0 ? step / dt : 0;
    } else {
      state.yawRate *= Math.exp(-6 * dt);
    }
    const targetPitch = clamp(Math.atan2(fish.velocity.y, Math.max(1e-4, horizontal)), -MAX_PITCH, MAX_PITCH);
    state.pitch += (targetPitch - state.pitch) * (1 - Math.exp(-4 * dt));

    // Gait: frequency and amplitude follow speed; escape adds thrust.
    const hover = 1 - smoothstep(0.1, 0.35, speedRatio);
    const frequency = 0.8 + 2.3 * Math.min(1, speedRatio) + 1.8 * boost;
    state.phase = (state.phase + TAU * frequency * dt) % (TAU * 1000);
    const amplitude = (0.09 + 0.2 * Math.min(1, speedRatio) + 0.16 * boost) * mix(1, 0.35, hover);
    const decel = dt > 0 ? (state.speed - speed) / dt : 0;
    state.speed = speed;
    state.brake += (clamp(decel * 2.5, 0, 1) - state.brake) * (1 - Math.exp(-5 * dt));
    state.curvature += (clamp(state.yawRate * 0.55, -1.4, 1.4) - state.curvature) * (1 - Math.exp(-8 * dt));
    state.finPhase = (state.finPhase + TAU * (0.7 + 1.5 * hover + 0.8 * state.brake) * dt) % (TAU * 1000);
    return {
      yaw: state.yaw,
      pitch: state.pitch,
      roll: clamp(-state.yawRate * 0.1, -0.3, 0.3),
      phase: state.phase,
      amplitude,
      curvature: state.curvature,
      brake: state.brake,
      finPhase: state.finPhase,
      hover,
    };
  };
}

export function orientationBasis(yaw, pitch, target) {
  const forward = new THREE.Vector3(Math.cos(yaw) * Math.cos(pitch), Math.sin(pitch), Math.sin(yaw) * Math.cos(pitch));
  const side = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();
  const up = new THREE.Vector3().crossVectors(side, forward).normalize();
  return target.makeBasis(forward, up, side);
}

// ------------------------------------------------------------ renderer

export function createHeroFishRenderer(scene, {
  renderer = null,
  capacity = 1,
  scale = 1,
  effectUniforms = null,
} = {}) {
  if (!scene?.isScene) throw new TypeError('scene must be a Three.js Scene');
  const geometry = buildHeroFishGeometry();
  const swim = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 4), 4);
  const fin = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 2), 2);
  swim.setUsage(THREE.DynamicDrawUsage);
  fin.setUsage(THREE.DynamicDrawUsage);
  for (const g of Object.values(geometry)) {
    g.setAttribute('aSwim', swim);
    g.setAttribute('aFin', fin);
  }
  const textures = {
    body: dataTexture(512, 256, shadeBody, THREE.SRGBColorSpace),
    mask: dataTexture(256, 128, shadeMask, THREE.NoColorSpace),
    fin: dataTexture(256, 128, shadeFin, THREE.SRGBColorSpace),
  };
  const environment = fishEnvironment(renderer);

  const bodyMaterial = applyHeroShader(new THREE.MeshPhysicalMaterial({
    map: textures.body,
    roughness: 1,
    roughnessMap: textures.mask,
    metalness: 1,
    metalnessMap: textures.mask,
    iridescence: 0.55,
    iridescenceMap: textures.mask,
    iridescenceIOR: 1.33,
    iridescenceThicknessRange: [240, 520],
    clearcoat: 0.35,
    clearcoatRoughness: 0.16,
    envMap: environment?.texture ?? null,
    envMapIntensity: 0.6,
  }), {
    key: 'body',
    effectUniforms,
    albedo: EYE_ALBEDO,
    optics: EYE_OPTICS,
    physical: EYE_PHYSICAL,
    scatter: BODY_SCATTER,
  });

  const finMaterial = applyHeroShader(new THREE.MeshStandardMaterial({
    map: textures.fin,
    roughness: 0.45,
    metalness: 0,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    envMap: environment?.texture ?? null,
    envMapIntensity: 0.35,
  }), { key: 'fins', effectUniforms, scatter: FIN_SCATTER });

  const bodies = new THREE.InstancedMesh(geometry.body, bodyMaterial, capacity);
  const membranes = new THREE.InstancedMesh(geometry.fins, finMaterial, capacity);
  bodies.name = 'hero-fish-bodies';
  membranes.name = 'hero-fish-membranes';
  membranes.renderOrder = 2;
  for (const mesh of [bodies, membranes]) {
    mesh.frustumCulled = false;
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.count = 0;
    scene.add(mesh);
  }

  const animate = createSwimAnimator();
  const basis = new THREE.Matrix4();
  const rotation = new THREE.Quaternion();
  const roll = new THREE.Quaternion();
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const scaleVector = new THREE.Vector3();
  const xAxis = new THREE.Vector3(1, 0, 0);
  const triangles = {
    body: geometry.body.index.count / 3,
    fins: geometry.fins.index.count / 3,
  };

  return {
    triangles,
    vertices: geometry.body.attributes.position.count + geometry.fins.attributes.position.count,
    drawCallBudget: 3,          // bodies + membranes (transparent double-sided: two passes)
    meshes: Object.freeze({ bodies, membranes }),
    lastState: null,
    // fishStates: simulation fish (or review stand-ins) — read only.
    project(fishStates, simulationTime) {
      const count = Math.min(capacity, fishStates.length);
      for (let index = 0; index < count; index += 1) {
        const fish = fishStates[index];
        const state = animate(index, fish, simulationTime);
        orientationBasis(state.yaw, state.pitch, basis);
        rotation.setFromRotationMatrix(basis).multiply(roll.setFromAxisAngle(xAxis, state.roll));
        position.set(fish.position.x, fish.position.y, fish.position.z);
        scaleVector.setScalar((fish.scale ?? 1) * scale);
        matrix.compose(position, rotation, scaleVector);
        bodies.setMatrixAt(index, matrix);
        membranes.setMatrixAt(index, matrix);
        swim.setXYZW(index, state.phase, state.amplitude, state.curvature, state.brake);
        fin.setXY(index, state.finPhase, state.hover);
        this.lastState = state;
      }
      bodies.count = count;
      membranes.count = count;
      bodies.instanceMatrix.needsUpdate = true;
      membranes.instanceMatrix.needsUpdate = true;
      swim.needsUpdate = true;
      fin.needsUpdate = true;
    },
    dispose() {
      scene.remove(bodies, membranes);
      for (const g of Object.values(geometry)) g.dispose();
      for (const texture of Object.values(textures)) texture.dispose();
      environment?.dispose();
      bodyMaterial.dispose();
      finMaterial.dispose();
    },
  };
}

// ------------------------------------------------------------ review mode

const GAITS = ['auto', 'cruise', 'hover', 'turn', 'escape'];

export function readHeroFishConfig(locationLike) {
  const params = new URLSearchParams(locationLike?.search ?? '');
  const number = (name, fallback, minimum, maximum) => {
    const value = Number(params.get(name));
    return params.has(name) && Number.isFinite(value) ? clamp(value, minimum, maximum) : fallback;
  };
  const at = (params.get('heroAt') ?? '').split(',').map(Number);
  return Object.freeze({
    enabled: params.get('heroFish') === '1',
    variant: params.get('heroVariant') === 'production' ? 'production' : 'hero',
    scale: number('heroScale', 1.8, 0.25, 4),
    fishIndex: 2,
    studio: params.get('heroStudio') === '1',
    gait: GAITS.includes(params.get('heroGait')) ? params.get('heroGait') : 'auto',
    yaw: params.has('heroYaw') ? number('heroYaw', 0, -360, 360) * Math.PI / 180 : null,
    at: at.length === 3 && at.every(Number.isFinite) ? at : [0.4, 0.15, 0.25],
  });
}

// Review-only stand-in: holds a pose or runs a scripted gait cycle so the
// four swim states can be inspected on demand. Production never uses it.
export function createHeroStudio(template, config) {
  const fish = {
    ...template,
    position: { x: config.at[0], y: config.at[1], z: config.at[2] },
    velocity: { x: 0.25, y: 0, z: 0 },
    cursorBoost: 0,
    maximumSpeed: 0.45,
  };
  const gaitSpeed = { cruise: 0.26, hover: 0.035, turn: 0.22, escape: 0.5 };
  const setHeading = (yaw, speed, climb = 0) => {
    fish.velocity.x = Math.cos(yaw) * speed;
    fish.velocity.z = Math.sin(yaw) * speed;
    fish.velocity.y = climb;
  };
  return {
    fish,
    update(time) {
      if (config.gait !== 'auto') {
        const turning = config.gait === 'turn';
        const yaw = (config.yaw ?? 0) + (turning ? time * 1.4 : 0);
        setHeading(yaw, gaitSpeed[config.gait], config.gait === 'hover' ? 0.004 * Math.sin(time * 1.3) : 0);
        fish.cursorBoost = config.gait === 'escape' ? 1 : 0;
        return fish;
      }
      // 16 s loop: cruise right, brake to hover, U-turn toward the viewer,
      // escape burst, settle to cruise. Position drifts within a small box.
      const t = time % 16;
      let yaw = 0;
      let speed = 0.26;
      fish.cursorBoost = 0;
      if (t < 4) { yaw = 0; speed = 0.26; }
      else if (t < 7) { yaw = 0; speed = mix(0.26, 0.03, smoothstep(4, 5.5, t)); }
      else if (t < 9) { yaw = Math.PI * smoothstep(7, 8.4, t); speed = mix(0.03, 0.22, smoothstep(7, 8, t)); }
      else if (t < 11.5) { yaw = Math.PI; speed = 0.5; fish.cursorBoost = 1 - smoothstep(10.5, 11.5, t); }
      else { yaw = Math.PI; speed = mix(0.5, 0.26, smoothstep(11.5, 13, t)); }
      setHeading(yaw, speed);
      const dt = 1 / 60;
      fish.position.x = clamp(fish.position.x + fish.velocity.x * dt, config.at[0] - 1.2, config.at[0] + 1.2);
      fish.position.z = clamp(fish.position.z + fish.velocity.z * dt, config.at[2] - 0.4, config.at[2] + 0.4);
      return fish;
    },
  };
}
