import * as THREE from '../../vendor/three/three.module.js';
import { createSchool, stepSchool } from '../../core/behavior.js';
import { createEnvironment } from '../../core/environment.js';
import { createFishRenderer } from '../../core/fish.js';
import { createPlantedTankConfig } from './config.js';

export function createPlantedTank(renderer, overrides = {}) {
  if (!renderer?.isWebGLRenderer) {
    throw new TypeError('renderer must be a Three.js WebGLRenderer');
  }
  const config = createPlantedTankConfig(overrides);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 20);
  camera.position.set(0, 0.06, 6.2);
  camera.lookAt(0, 0, 0);

  const school = createSchool(config);
  const fishRenderer = createFishRenderer(scene, 12);
  const environment = createEnvironment(scene, config);
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
      stepSchool(school, simulationPointer, deltaSeconds, config.bounds);
    },
    project(simulationTime) {
      fishRenderer.project(school, simulationTime);
      environment.updateVisuals(simulationTime);
      renderer.render(scene, camera);
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
    dispose() {
      fishRenderer.dispose();
      environment.dispose();
    },
  };
}
