#pragma once

#include <windows.h>

#include <cstdint>
#include <filesystem>
#include <functional>
#include <memory>
#include <string>

enum class WebViewEvent {
  Info,
  Ready,
  Failure,
};

class WebViewRuntime {
 public:
  using EventCallback =
      std::function<void(std::uint64_t generation, WebViewEvent event, const std::wstring& detail)>;

  WebViewRuntime();
  ~WebViewRuntime();
  WebViewRuntime(const WebViewRuntime&) = delete;
  WebViewRuntime& operator=(const WebViewRuntime&) = delete;

  bool initialize(HWND renderer_window, HWND controller_parent_window, const RECT& bounds,
                  const std::filesystem::path& habitat_directory,
                  const std::filesystem::path& user_data_directory,
                  std::uint64_t generation, EventCallback callback);
  bool post_json(const std::string& json);
  void set_visible(bool visible);
  void shutdown();
  bool ready() const;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
