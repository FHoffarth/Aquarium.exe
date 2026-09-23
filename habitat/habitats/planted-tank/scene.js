import * as THREE from '../../vendor/three/three.module.js';
import { createSchool, stepSchool } from '../../core/behavior.js';
import { createEnvironment } from '../../core/environment.js';
import { createFishRenderer } from '../../core/fish.js';
import { createHeroFishRenderer, createHeroStudio } from '../../core/hero-fish.js';
import { createSliceAEnvironment } from '../../core/slice-a-environment.js';
import { deriveAuditScenePlan } from '../../audit-config.js';
import { createPlantedTankConfig } from './config.js';

const DEFAULT_AUDIT = { enabled: false, mode: 'full', fishCount: 10 };
const HERO_OFF = Object.freeze({ enabled: false });

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
  heroFish = HERO_OFF,
}) {
  if (artMode === 'slice-a' && deriveAuditScenePlan(auditConfig).createEnvironment) {
    try {
      const artAssets = await loadArtGroup('slice-a');
      const habitat = createPlantedTank(renderer, overrides, auditConfig, performanceRecorder, {
        artAssets,
        heroFish,
      });
      return {
        habitat,
        art: { mode: 'slice-a', loadMs: artAssets.loadMs, bytes: artAssets.totalBytes },
      };
    } catch (error) {
      reportAssetFailure(error);
    }
  }
  return {
    habitat: createPlantedTank(renderer, overrides, auditConfig, performanceRecorder, { heroFish }),
    art: { mode: 'procedural', loadMs: 0, bytes: 0 },
  };
}

export function createPlantedTank(
  renderer,
  overrides = {},
  auditConfig = DEFAULT_AUDIT,
  performanceRecorder = null,
  { artAssets = null, heroFish = HERO_OFF } = {},
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
  // Hero Fish review: the whole school still simulates (authoritative); one
  // fish is rendered, either with the hero renderer or, for A/B, with the
  // production renderer at the same scale.
  const hero = heroFish.enabled && scenePlan.createFish ? heroFish : null;
  const fishRenderer = scenePlan.createFish && hero?.variant !== 'hero'
    ? createFishRenderer(scene, Math.max(1, scenePlan.fishCount))
    : null;
  let environment = null;
  if (scenePlan.createEnvironment) {
    environment = artAssets
      ? createSliceAEnvironment(scene, config, artAssets)
      : createEnvironment(scene, config);
  }
  const heroScreen = new THREE.Vector3();
  const heroRenderer = hero?.variant === 'hero'
    ? createHeroFishRenderer(scene, {
      renderer,
      scale: hero.scale,
      effectUniforms: environment?.effectUniforms ?? null,
    })
    : null;
  // Review-only stand-in for posed evidence; the school keeps simulating.
  const studio = hero?.studio ? createHeroStudio(school.fish[hero.fishIndex % school.fish.length], hero) : null;
  const heroSubject = simulationTime => (studio
    ? studio.update(simulationTime)
    : school.fish[hero.fishIndex % school.fish.length]);
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
      if (fishRenderer || heroRenderer) {
        const start = performanceRecorder?.enabled ? performanceRecorder.mark() : 0;
        const fish = hero ? heroSubject(simulationTime) : null;
        fishRenderer?.project(hero ? { fish: [{ ...fish, scale: fish.scale * hero.scale }] } : school,
          simulationTime);
        heroRenderer?.project([fish], simulationTime);
        if (hero) {
          // Review aid: where the reviewed fish is on screen (0..1, y down).
          heroScreen.set(fish.position.x, fish.position.y, fish.position.z).project(camera);
          globalThis.__aquariumHeroFish = {
            x: heroScreen.x * 0.5 + 0.5,
            y: 0.5 - heroScreen.y * 0.5,
            depth: fish.position.z,
            state: heroRenderer?.lastState ?? null,
          };
        }
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
      heroRenderer?.dispose();
      environment?.dispose();
      for (const light of auditLights) scene.remove(light);
    },
  };
}
