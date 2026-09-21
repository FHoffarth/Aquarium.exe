#pragma once

#include <algorithm>
#include <chrono>
#include <iomanip>
#include <locale>
#include <sstream>
#include <string>

namespace aquarium {

enum class HostState { Starting, Initializing, Running, Recovering, Stopping };

class RecoveryBackoff {
 public:
  std::chrono::milliseconds next_delay() {
    constexpr int delays[]{250, 500, 1000, 2000, 5000};
    const auto index = std::min(attempt_, std::size(delays) - 1);
    ++attempt_;
    return std::chrono::milliseconds(delays[index]);
  }

  void reset() { attempt_ = 0; }

 private:
  std::size_t attempt_ = 0;
};

class HostLifecycle {
 public:
  HostState state() const { return state_; }
  unsigned long long generation() const { return generation_; }
  bool is_current(unsigned long long generation) const { return generation == generation_; }

  unsigned long long begin_initialization() {
    state_ = HostState::Initializing;
    return ++generation_;
  }

  bool mark_running(unsigned long long generation) {
    if (state_ != HostState::Initializing || !is_current(generation)) return false;
    state_ = HostState::Running;
    return true;
  }

  void mark_lost() {
    if (state_ == HostState::Stopping) return;
    state_ = HostState::Recovering;
    ++generation_;
  }

  void stop() {
    state_ = HostState::Stopping;
    ++generation_;
  }

 private:
  HostState state_ = HostState::Starting;
  unsigned long long generation_ = 0;
};

inline std::string pointer_message(bool present, double x, double y) {
  if (!present) return R"({"type":"pointer","present":false})";
  std::ostringstream out;
  out.imbue(std::locale::classic());
  out << R"({"type":"pointer","present":true,"x":)" << std::fixed << std::setprecision(4)
      << std::clamp(x, 0.0, 1.0) << R"(,"y":)" << std::clamp(y, 0.0, 1.0) << "}";
  return out.str();
}

inline std::string pause_message(bool paused) {
  return std::string(R"({"type":"state","paused":)") + (paused ? "true}" : "false}");
}

inline std::string rate_message(int fps) {
  return std::string(R"({"type":"rate","fps":)") + std::to_string(std::max(0, fps)) + "}";
}

inline std::string probe_message() { return R"({"type":"probe"})"; }

}  // namespace aquarium
