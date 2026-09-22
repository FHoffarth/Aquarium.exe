import * as THREE from '../../vendor/three/three.module.js';
import { createSchool, stepSchool } from '../../core/behavior.js';
import { createEnvironment } from '../../core/environment.js';
import { createFishRenderer } from '../../core/fish.js';
import { createSliceAEnvironment } from '../../core/slice-a-environment.js';
import { deriveAuditScenePlan } from '../../audit-config.js';
import { createPlantedTankConfig } from './config.js';

const DEFAULT_AUDIT = { enabled: false, mode: 'full', fishCount: 10 };

// Tries the requested art mode and falls back to the accepted procedural
// environment if its assets cannot be loaded or verified. The failure is
// reported, never hidden; the wallpaper keeps working either way.
export async function createPlantedTankForArt(renderer, {
  artMode,
  loadArtGroup,
  reportAssetFailure,
  overrides = {},
  auditConfig = DEFAULT_AUDIT,
  performanceRecorder = null,
}) {
  if (artMode === 'slice-a' && deriveAuditScenePlan(auditConfig).createEnvironment) {
    try {
      const artAssets = await loadArtGroup('slice-a');
      const habitat = createPlantedTank(renderer, overrides, auditConfig, performanceRecorder, { artAssets });
      return {
        habitat,
        art: { mode: 'slice-a', loadMs: artAssets.loadMs, bytes: artAssets.totalBytes },
      };
    } catch (error) {
      reportAssetFailure(error);
    }
  }
  return {
    habitat: createPlantedTank(renderer, overrides, auditConfig, performanceRecorder),
    art: { mode: 'procedural', loadMs: 0, bytes: 0 },
  };
}

export function createPlantedTank(
  renderer,
  overrides = {},
  auditConfig = DEFAULT_AUDIT,
  performanceRecorder = null,
  { artAssets = null } = {},
) {
  if (!renderer?.isWebGLRenderer) {
    throw new TypeError('renderer must be a Three.js WebGLRenderer');
  }
  const productConfig = createPlantedTankConfig(overrides);
  const scenePlan = deriveAuditScenePlan(auditConfig);
  const config = scenePlan.fishCount === productConfig.fishCount
    ? productConfig
    : Object.freeze({ ...productConfig, fishCount: scenePlan.fishCount });
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 20);
  camera.position.set(0, 0.06, 6.2);
  camera.lookAt(0, 0, 0);

  const school = createSchool(config);
  const fishRenderer = scenePlan.createFish
    ? createFishRenderer(scene, Math.max(1, scenePlan.fishCount))
    : null;
  let environment = null;
  if (scenePlan.createEnvironment) {
    environment = artAssets
      ? createSliceAEnvironment(scene, config, artAssets)
      : createEnvironment(scene, config);
  }
  const auditLights = [];
  if (scenePlan.createFish && !scenePlan.createEnvironment) {
    const hemisphere = new THREE.HemisphereLight(0xd8fff7, 0x102426, 2.15);
    const directional = new THREE.DirectionalLight(0xfff5dc, 2.35);
    directional.position.set(-2.2, 2.8, 3.4);
    scene.add(hemisphere, directional);
    auditLights.push(hemisphere, directional);
  }
  const simulationPointer = {
    present: false,
    x: 0,
    y: 0,
    z: 0,
    eventsReceived: 0,
  };

  return {
    step(deltaSeconds, pointer) {
      simulationPointer.present = Boolean(pointer.present);
      simulationPointer.eventsReceived = pointer.eventsReceived;
      if (simulationPointer.present) {
        simulationPointer.x = config.bounds.minX
          + pointer.x * (config.bounds.maxX - config.bounds.minX);
        simulationPointer.y = config.bounds.maxY
          - pointer.y * (config.bounds.maxY - config.bounds.minY);
        simulationPointer.z = 0;
      }
      const start = performanceRecorder?.enabled ? performanceRecorder.mark() : 0;
      stepSchool(school, simulationPointer, deltaSeconds, config.bounds);
      if (performanceRecorder?.enabled) performanceRecorder.record('simulationMs', start);
    },
    project(simulationTime) {
      if (fishRenderer) {
        const start = performanceRecorder?.enabled ? performanceRecorder.mark() : 0;
        fishRenderer.project(school, simulationTime);
        if (performanceRecorder?.enabled) {
          performanceRecorder.record('fishProjectionMs', start);
        }
      }
      if (environment) {
        const start = performanceRecorder?.enabled ? performanceRecorder.mark() : 0;
        environment.updateVisuals(simulationTime);
        if (performanceRecorder?.enabled) performanceRecorder.record('environmentMs', start);
      }
      if (scenePlan.render) {
        const start = performanceRecorder?.enabled ? performanceRecorder.mark() : 0;
        renderer.render(scene, camera);
        if (performanceRecorder?.enabled) performanceRecorder.record('renderMs', start);
      }
    },
    resize(width, height) {
      const safeWidth = Math.max(1, width);
      const safeHeight = Math.max(1, height);
      camera.aspect = safeWidth / safeHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(safeWidth, safeHeight, false);
    },
    getFishCount() {
      return school.fish.length;
    },
    getReactionCount() {
      return school.fish.reduce((total, fish) => total + fish.reactionCount, 0);
    },
    getRenderInfo() {
      return {
        calls: renderer.info.render.calls,
        triangles: renderer.info.render.triangles,
      };
    },
    getPerformanceSnapshot() {
      return performanceRecorder?.snapshot() ?? null;
    },
    dispose() {
      fishRenderer?.dispose();
      environment?.dispose();
      for (const light of auditLights) scene.remove(light);
    },
  };
}
