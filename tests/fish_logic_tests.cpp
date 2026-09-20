#include "../src/fish_logic.h"

#include <cmath>
#include <iostream>

namespace {
bool near(float left, float right, float epsilon = 0.001f) {
  return std::abs(left - right) <= epsilon;
}

int fail(const char* message) {
  std::cerr << "FAIL: " << message << '\n';
  return 1;
}
}  // namespace

int main() {
  using aquarium::FishState;
  using aquarium::PointerState;

  {
    FishState fish{500.0f, 300.0f, 60.0f, 0.0f, 1.0f, 0};
    const auto next = aquarium::advance_fish(fish, PointerState{false, 0, 0}, 0.5f, 1920, 1080);
    if (!near(next.x, 530.0f)) return fail("an undisturbed fish should cruise at its current velocity");
    if (next.reactions != 0) return fail("an absent cursor must not count as a reaction");
  }

  {
    FishState fish{500.0f, 300.0f, 60.0f, 0.0f, 1.0f, 0};
    const auto next = aquarium::advance_fish(fish, PointerState{true, 540.0f, 300.0f}, 0.1f, 1920, 1080);
    if (!(next.vx < 0.0f)) return fail("a nearby cursor on the right should make the fish flee left");
    if (next.reactions != 1) return fail("entering cursor proximity should count one reaction");
  }

  {
    FishState fish{80.0f, 300.0f, -120.0f, 0.0f, -1.0f, 0};
    const auto next = aquarium::advance_fish(fish, PointerState{false, 0, 0}, 1.0f, 1920, 1080);
    if (!(next.vx > 0.0f && next.facing > 0.0f)) return fail("a fish crossing the left boundary should turn right");
  }

  {
    FishState fish{500.0f, 300.0f, 60.0f, 0.0f, 1.0f, 0};
    const auto next = aquarium::advance_fish(fish, PointerState{false, 0, 0}, 0.0f, 1920, 1080);
    if (!near(next.x, fish.x) || !near(next.y, fish.y)) return fail("zero elapsed time should not move the fish");
  }

  std::cout << "PASS: fish logic\n";
  return 0;
}
