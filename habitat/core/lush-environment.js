import * as THREE from '../vendor/three/three.module.js';

// The backdrop is rendered from the approved Blender scene with only the posed
// review fish and still-frame particles hidden. It preserves the approved
// vegetation, terrain, wood, camera and light exactly at 1920 x 1080.
function seededUnit(index, channel) {
  let value = (73109 ^ Math.imul(index + 1, 0x9e3779b1) ^ Math.imul(channel + 1, 0x85ebca77)) >>> 0;
  value ^= value >>> 16;
  value = Math.imul(value, 0x7feb352d);
  value ^= value >>> 15;
  return (value >>> 0) / 0x100000000;
}

export function createLushEnvironment(scene, _config, assets) {
  const plate = assets.textures.environment_albedo;
  if (!plate) throw new Error('lush environment plate is missing');
  const time = { value: 0 };
  const material = new THREE.MeshBasicMaterial({
    map: plate,
    toneMapped: false,
    depthTest: false,
    depthWrite: false,
  });
  material.onBeforeCompile = shader => {
    shader.uniforms.uWaterTime = time;
    shader.fragmentShader = `uniform float uWaterTime;\n${shader.fragmentShader}`
      .replace('#include <map_fragment>', `#include <map_fragment>
        float broad = sin(vMapUv.x * 5.3 + uWaterTime * 0.09)
          * sin(vMapUv.y * 4.1 - uWaterTime * 0.07);
        diffuseColor.rgb *= 1.0 + 0.006 * broad;`);
    shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>',
      'gl_Position = vec4(position.xy, 0.999, 1.0);');
  };
  material.customProgramCacheKey = () => 'lush-approved-plate-v1';
  const plane = new THREE.PlaneGeometry(2, 2);
  const uv = plane.getAttribute('uv');
  for (let i = 0; i < uv.count; i += 1) uv.setY(i, 1 - uv.getY(i));
  const background = new THREE.Mesh(plane, material);
  background.name = 'approved-lush-environment';
  background.frustumCulled = false;
  background.renderOrder = -100;
  scene.add(background);

  const count = 22;
  const anchors = new Float32Array(count * 3);
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 1) {
    anchors[i * 3] = (seededUnit(i, 0) - 0.5) * 5.8;
    anchors[i * 3 + 1] = (seededUnit(i, 1) - 0.5) * 2.6;
    anchors[i * 3 + 2] = -0.6 + seededUnit(i, 2) * 1.2;
  }
  positions.set(anchors);
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const particleMaterial = new THREE.PointsMaterial({
    color: 0xb7d5cc,
    size: 0.009,
    opacity: 0.16,
    transparent: true,
    depthWrite: false,
    sizeAttenuation: true,
  });
  const particles = new THREE.Points(particleGeometry, particleMaterial);
  particles.name = 'sparse-suspended-freshwater-particles';
  particles.frustumCulled = false;
  scene.add(particles);
  const ambient = new THREE.AmbientLight(0xffffff, 1.25);
  ambient.name = 'approved-fish-water-fill';
  scene.add(ambient);
  const top = new THREE.DirectionalLight(0xfff2d8, 1.45);
  top.position.set(-2.5, 4, 3);
  scene.add(top);

  return {
    artMode: 'lush',
    drawCallBudget: 5,
    updateVisuals(simulationTime) {
      time.value = simulationTime;
      for (let i = 0; i < count; i += 1) {
        positions[i * 3] = anchors[i * 3] + simulationTime * (0.0015 + seededUnit(i, 3) * 0.001);
      }
      particleGeometry.attributes.position.needsUpdate = true;
    },
    dispose() {
      scene.remove(background, particles, ambient, top);
      background.geometry.dispose();
      material.dispose();
      particleGeometry.dispose();
      particleMaterial.dispose();
      plate.image?.close?.();
      plate.dispose();
    },
  };
}
