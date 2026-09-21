#include "../src/host_policy.h"

#include <cstdlib>
#include <iostream>
#include <string>

namespace {

void require(bool condition, const char* message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << "\n";
    std::exit(1);
  }
}

}  // namespace

int main() {
  aquarium::RecoveryBackoff backoff;
  const int expected[]{250, 500, 1000, 2000, 5000, 5000};
  for (const int delay : expected) {
    require(backoff.next_delay().count() == delay, "recovery backoff sequence");
  }
  backoff.reset();
  require(backoff.next_delay().count() == 250, "recovery backoff reset");

  aquarium::HostLifecycle lifecycle;
  require(lifecycle.state() == aquarium::HostState::Starting, "initial host state");
  const auto first_generation = lifecycle.begin_initialization();
  require(lifecycle.state() == aquarium::HostState::Initializing, "initializing host state");
  require(lifecycle.mark_running(first_generation), "current generation can become running");
  require(lifecycle.state() == aquarium::HostState::Running, "running host state");
  lifecycle.mark_lost();
  require(lifecycle.state() == aquarium::HostState::Recovering, "recovering host state");
  require(!lifecycle.is_current(first_generation), "loss invalidates asynchronous callbacks");
  const auto recovery_generation = lifecycle.begin_initialization();
  require(recovery_generation > first_generation, "recovery uses a new generation");
  require(!lifecycle.mark_running(first_generation), "stale generation is rejected");
  require(lifecycle.mark_running(recovery_generation), "recovery generation can become running");
  lifecycle.stop();
  require(lifecycle.state() == aquarium::HostState::Stopping, "stopping host state");

  require(aquarium::pointer_message(false, 0.0, 0.0) ==
              R"({"type":"pointer","present":false})",
          "pointer-out JSON");
  require(aquarium::pointer_message(true, 0.125, 0.875) ==
              R"({"type":"pointer","present":true,"x":0.1250,"y":0.8750})",
          "normalized pointer JSON");
  require(aquarium::pause_message(true) == R"({"type":"state","paused":true})",
          "pause JSON");
  require(aquarium::pause_message(false) == R"({"type":"state","paused":false})",
          "resume JSON");
  require(aquarium::rate_message(30) == R"({"type":"rate","fps":30})",
          "render-rate JSON");
  require(aquarium::probe_message() == R"({"type":"probe"})", "probe JSON");

  std::cout << "PASS: host policy\n";
  return 0;
}
