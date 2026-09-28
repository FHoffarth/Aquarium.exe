import * as THREE from '../vendor/three/three.module.js';

const ASSET = 'lush-slice/environment.glb';

// Render-side coordinate calibration only. Schooling remains in its existing
// [-3,3] x [-1.45,1.45] x [-0.65,0.65] simulation volume. The approved GLB
// has foreground plants near Three Z +2, middle plants near Z 0 and far
// plants near Z -3; this spread makes genuine depth crossings observable.
export function mapLushLiveSliceFish(fish) {
  return {
    ...fish,
    position: {
      x: fish.position.x * 0.9,
      y: 3.1 + fish.position.y,
      z: -0.9 + fish.position.z * 3.2,
    },
    velocity: {
      x: fish.velocity.x * 0.9,
      y: fish.velocity.y,
      z: fish.velocity.z * 3.2,
    },
  };
}

export function createLushLiveSliceEnvironment(scene, assets) {
  if (!scene?.isScene) throw new TypeError('scene must be a Three.js Scene');
  const root = assets.sceneGraphs?.[ASSET];
  if (!root) throw new Error(`${ASSET}: GLB scene graph missing`);

  let referenceCamera = null;
  let meshCount = 0;
  root.traverse(object => {
    if (object.isPerspectiveCamera) referenceCamera = object;
    if (!object.isMesh) return;
    meshCount += 1;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      if (material.transparent || !material.depthTest || !material.depthWrite) {
        throw new Error(`${object.name}: live slice requires depth-tested, depth-writing material`);
      }
      if (material.name.includes('photographed broad leaf surfaces')
          && Math.abs(material.alphaTest - 0.45) > 0.01) {
        throw new Error(`${object.name}: broad-leaf cutout threshold changed`);
      }
    }
  });
  if (!referenceCamera || meshCount < 3) {
    throw new Error(`${ASSET}: approved camera or spatial geometry missing`);
  }

  scene.add(root);
  // Fixed neutral inspection light. No fog, animated illumination, water
  // attenuation, shadow pass, particles, bloom or background plate.
  const ambient = new THREE.AmbientLight(0xd1dfe2, 0.55);
  const hemisphere = new THREE.HemisphereLight(0xf1f5ee, 0x4b5d56, 0.9);
  const top = new THREE.DirectionalLight(0xffffff, 1.75);
  top.position.set(-3, 9, 6);
  scene.add(ambient, hemisphere, top);

  return {
    referenceCamera,
    mapFish: mapLushLiveSliceFish,
    updateVisuals() {},
    dispose() {
      scene.remove(root, ambient, hemisphere, top);
      const geometries = new Set();
      const materials = new Set();
      const textures = new Set();
      root.traverse(object => {
        if (!object.isMesh) return;
        geometries.add(object.geometry);
        for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
          materials.add(material);
          if (material.map) textures.add(material.map);
        }
      });
      for (const geometry of geometries) geometry.dispose();
      for (const material of materials) material.dispose();
      for (const texture of textures) texture.dispose();
    },
  };
}
