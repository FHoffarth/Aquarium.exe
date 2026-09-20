#pragma once

#include <algorithm>
#include <cmath>

namespace aquarium {

struct PointerState {
  bool present;
  float x;
  float y;
};

struct FishState {
  float x;
  float y;
  float vx;
  float vy;
  float facing;
  unsigned long long reactions;
  bool startled = false;
};

inline FishState advance_fish(
    FishState fish,
    PointerState pointer,
    float seconds,
    float width,
    float height) {
  if (!(seconds > 0.0f) || !(width > 0.0f) || !(height > 0.0f)) return fish;

  if (pointer.present) {
    const float dx = fish.x - pointer.x;
    const float dy = fish.y - pointer.y;
    const float distance_squared = dx * dx + dy * dy;
    constexpr float reaction_radius = 220.0f;
    if (distance_squared < reaction_radius * reaction_radius) {
      const float distance = std::sqrt(std::max(distance_squared, 1.0f));
      const float away_x = distance_squared > 1.0f ? dx / distance : -fish.facing;
      const float away_y = distance_squared > 1.0f ? dy / distance : 0.0f;
      const float urgency = 1.0f - distance / reaction_radius;
      fish.vx += away_x * (900.0f + 700.0f * urgency) * seconds;
      fish.vy += away_y * (700.0f + 500.0f * urgency) * seconds;
      if (!fish.startled) ++fish.reactions;
      fish.startled = true;
    } else if (distance_squared > 260.0f * 260.0f) {
      fish.startled = false;
    }
  } else {
    fish.startled = false;
  }

  const float speed = std::sqrt(fish.vx * fish.vx + fish.vy * fish.vy);
  if (speed > 480.0f) {
    fish.vx *= 480.0f / speed;
    fish.vy *= 480.0f / speed;
  }

  fish.x += fish.vx * seconds;
  fish.y += fish.vy * seconds;

  constexpr float margin_x = 70.0f;
  constexpr float margin_y = 45.0f;
  if (fish.x < margin_x) {
    fish.x = margin_x;
    fish.vx = std::abs(fish.vx);
  } else if (fish.x > width - margin_x) {
    fish.x = width - margin_x;
    fish.vx = -std::abs(fish.vx);
  }
  if (fish.y < margin_y) {
    fish.y = margin_y;
    fish.vy = std::abs(fish.vy);
  } else if (fish.y > height - margin_y) {
    fish.y = height - margin_y;
    fish.vy = -std::abs(fish.vy);
  }

  fish.vy *= std::pow(0.35f, seconds);
  if (std::abs(fish.vx) > 1.0f) fish.facing = fish.vx > 0.0f ? 1.0f : -1.0f;
  return fish;
}

}  // namespace aquarium
