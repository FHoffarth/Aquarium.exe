#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <objbase.h>
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

#include "host_policy.h"
#include "webview_runtime.h"

namespace {

constexpr wchar_t kWindowClass[] = L"AquariumSpike.RenderWindow.v1";
constexpr wchar_t kRendererChildClass[] = L"AquariumSpike.RendererChild.v1";
constexpr wchar_t kOwnerWindowClass[] = L"AquariumSpike.HiddenOwner.v1";
constexpr wchar_t kControlMessageName[] = L"AquariumSpike.Control.v1";
constexpr UINT kSpawnWorkerW = 0x052C;
constexpr LONG_PTR kWsExNoRedirectionBitmap = 0x00200000L;

enum class Control : WPARAM { Pause = 1, Resume = 2, Toggle = 3, Probe = 4, Quit = 5 };

std::wofstream g_log;
std::mutex g_log_mutex;
UINT g_control_message = 0;
bool g_paused = false;
bool g_quit = false;
unsigned long long g_frames = 0;
WebViewRuntime* g_webview_runtime = nullptr;
HWND g_window = nullptr;
HWND g_renderer_window = nullptr;
HWND g_owner_window = nullptr;
HWND g_progman = nullptr;
HWND g_defview = nullptr;
HWND g_workerw = nullptr;
bool g_raised_desktop = false;

std::wstring hex_handle(HWND handle) {
  std::wostringstream out;
  out << L"0x" << std::hex << std::uppercase << reinterpret_cast<UINT_PTR>(handle);
  return out.str();
}

std::wstring class_name(HWND window) {
  wchar_t value[256]{};
  GetClassNameW(window, value, static_cast<int>(std::size(value)));
  return value;
}

std::wstring rect_text(const RECT& rect) {
  std::wostringstream out;
  out << L"[" << rect.left << L"," << rect.top << L"," << rect.right << L"," << rect.bottom << L"]";
  return out.str();
}

void log_line(const std::wstring& message) {
  SYSTEMTIME now{};
  GetLocalTime(&now);
  std::lock_guard lock(g_log_mutex);
  g_log << std::setfill(L'0') << std::setw(2) << now.wHour << L":" << std::setw(2) << now.wMinute
        << L":" << std::setw(2) << now.wSecond << L"." << std::setw(3) << now.wMilliseconds << L" "
        << message << std::endl;
  OutputDebugStringW((message + L"\n").c_str());
}

void log_window(const wchar_t* label, HWND window) {
  RECT rect{};
  GetWindowRect(window, &rect);
  std::wostringstream out;
  out << label << L" hwnd=" << hex_handle(window) << L" class=" << class_name(window)
      << L" parent=" << hex_handle(GetParent(window))
      << L" style=0x" << std::hex << std::uppercase << GetWindowLongPtrW(window, GWL_STYLE)
      << L" ex=0x" << GetWindowLongPtrW(window, GWL_EXSTYLE) << std::dec
      << L" rect=" << rect_text(rect) << L" visible=" << IsWindowVisible(window);
  log_line(out.str());
}

void log_os_build() {
  using RtlGetVersionFn = LONG(WINAPI*)(PRTL_OSVERSIONINFOW);
  const auto ntdll = GetModuleHandleW(L"ntdll.dll");
  const auto rtl_get_version = reinterpret_cast<RtlGetVersionFn>(GetProcAddress(ntdll, "RtlGetVersion"));
  RTL_OSVERSIONINFOW version{sizeof(version)};
  if (rtl_get_version && rtl_get_version(&version) == 0) {
    std::wostringstream out;
    out << L"OS version=" << version.dwMajorVersion << L"." << version.dwMinorVersion
        << L" build=" << version.dwBuildNumber;
    log_line(out.str());
  }
}

HWND find_progman() {
  if (HWND window = FindWindowW(L"Progman", L"Program Manager")) return window;
  struct State { HWND found = nullptr; } state;
  EnumWindows([](HWND window, LPARAM data) -> BOOL {
    auto* state = reinterpret_cast<State*>(data);
    if (class_name(window) == L"Progman") {
      state->found = window;
      return FALSE;
    }
    return TRUE;
  }, reinterpret_cast<LPARAM>(&state));
  return state.found;
}

std::vector<HWND> direct_children(HWND parent) {
  std::vector<HWND> children;
  for (HWND child = GetWindow(parent, GW_CHILD); child; child = GetWindow(child, GW_HWNDNEXT)) {
    children.push_back(child);
  }
  return children;
}

bool ordered_above(HWND parent, HWND upper, HWND lower) {
  const auto children = direct_children(parent);
  const auto upper_position = std::find(children.begin(), children.end(), upper);
  const auto lower_position = std::find(children.begin(), children.end(), lower);
  return upper_position != children.end() && lower_position != children.end() &&
         upper_position < lower_position;
}

void log_progman_children(const wchar_t* stage) {
  log_line(std::wstring(L"Progman children ") + stage + L" (top-to-bottom Z order):");
  int index = 0;
  for (HWND child : direct_children(g_progman)) {
    std::wostringstream label;
    label << L"  z=" << index++;
    log_window(label.str().c_str(), child);
  }
}

bool covers_virtual_screen(HWND window) {
  RECT rect{};
  if (!GetWindowRect(window, &rect)) return false;
  const RECT desktop{
      GetSystemMetrics(SM_XVIRTUALSCREEN), GetSystemMetrics(SM_YVIRTUALSCREEN),
      GetSystemMetrics(SM_XVIRTUALSCREEN) + GetSystemMetrics(SM_CXVIRTUALSCREEN),
      GetSystemMetrics(SM_YVIRTUALSCREEN) + GetSystemMetrics(SM_CYVIRTUALSCREEN)};
  return rect.left <= desktop.left && rect.top <= desktop.top &&
         rect.right >= desktop.right && rect.bottom >= desktop.bottom;
}

HWND find_wallpaper_worker(HWND progman, HWND defview) {
  bool passed_defview = false;
  for (HWND child : direct_children(progman)) {
    if (child == defview) {
      passed_defview = true;
      continue;
    }
    if (passed_defview && class_name(child) == L"WorkerW" && covers_virtual_screen(child)) return child;
  }
  return nullptr;
}

bool discover_desktop_host() {
  g_progman = find_progman();
  if (!g_progman) {
    log_line(L"ATTACH FAILURE: Progman was not found; refusing ordinary-window fallback.");
    return false;
  }
  log_window(L"Progman", g_progman);
  const LONG_PTR progman_ex = GetWindowLongPtrW(g_progman, GWL_EXSTYLE);
  g_raised_desktop = (progman_ex & kWsExNoRedirectionBitmap) != 0;
  log_line(std::wstring(L"desktopMode=") +
           (g_raised_desktop ? L"raised (WS_EX_NOREDIRECTIONBITMAP)" : L"classic"));

  g_defview = FindWindowExW(g_progman, nullptr, L"SHELLDLL_DefView", nullptr);
  if (!g_defview) {
    log_line(L"ATTACH FAILURE: direct SHELLDLL_DefView child was not found; refusing fallback.");
    return false;
  }
  log_window(L"SHELLDLL_DefView", g_defview);
  log_progman_children(L"before WorkerW request");

  g_workerw = find_wallpaper_worker(g_progman, g_defview);
  if (!g_workerw) {
    DWORD_PTR message_result = 0;
    SetLastError(ERROR_SUCCESS);
    const LRESULT sent = SendMessageTimeoutW(
        g_progman, kSpawnWorkerW, 0xD, 0x1, SMTO_ABORTIFHUNG | SMTO_BLOCK, 1000, &message_result);
    std::wostringstream out;
    out << L"SendMessageTimeout(Progman,0x052C,wParam=0xD,lParam=0x1) return=" << sent
        << L" messageResult=" << message_result << L" lastError=" << GetLastError();
    log_line(out.str());
    for (int attempt = 0; attempt < 20 && !g_workerw; ++attempt) {
      Sleep(50);
      g_workerw = find_wallpaper_worker(g_progman, g_defview);
    }
  } else {
    log_line(L"A suitable wallpaper WorkerW already existed; spawn message was not sent.");
  }

  log_progman_children(L"after WorkerW request");
  if (!g_workerw) {
    log_line(L"ATTACH FAILURE: no full-virtual-screen WorkerW below SHELLDLL_DefView was found.");
    return false;
  }
  log_window(L"selected WorkerW", g_workerw);
  log_line(L"ATTACH ASSUMPTION VERIFIED: selected WorkerW is a direct Progman child below SHELLDLL_DefView in child Z order.");
  return true;
}

void log_probe() {
  POINT point{};
  GetCursorPos(&point);
  const HWND hit = WindowFromPoint(point);
  std::wostringstream out;
  out << L"PROBE state=" << (g_paused ? L"paused" : L"running")
      << L" bridgeUpdates=" << g_frames
      << L" webviewReady=" << (g_webview_runtime && g_webview_runtime->ready())
      << L" cursorScreen=(" << point.x << L"," << point.y << L")"
      << L" WindowFromPoint=" << hex_handle(hit) << L"/" << class_name(hit)
      << L" hostHitTest=" << SendMessageW(g_window, WM_NCHITTEST, 0, MAKELPARAM(point.x, point.y))
      << L" rendererHitTest=" << SendMessageW(g_renderer_window, WM_NCHITTEST, 0,
                                                MAKELPARAM(point.x, point.y));
  log_line(out.str());
}

LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
  if (message == g_control_message) {
    switch (static_cast<Control>(wparam)) {
      case Control::Pause:
        if (!g_paused) log_line(L"CONTROL pause");
        g_paused = true;
        if (g_webview_runtime) g_webview_runtime->post_json(aquarium::pause_message(true));
        break;
      case Control::Resume:
        if (g_paused) log_line(L"CONTROL resume");
        g_paused = false;
        if (g_webview_runtime) g_webview_runtime->post_json(aquarium::pause_message(false));
        break;
      case Control::Toggle:
        g_paused = !g_paused;
        log_line(std::wstring(L"CONTROL toggle -> ") + (g_paused ? L"paused" : L"running"));
        if (g_webview_runtime) g_webview_runtime->post_json(aquarium::pause_message(g_paused));
        break;
      case Control::Probe:
        log_probe();
        if (g_webview_runtime) g_webview_runtime->post_json(aquarium::probe_message());
        break;
      case Control::Quit:
        log_line(L"CONTROL quit");
        g_quit = true;
        PostQuitMessage(0);
        break;
    }
    return 1;
  }
  switch (message) {
    case WM_NCHITTEST: return HTTRANSPARENT;
    case WM_MOUSEACTIVATE: return MA_NOACTIVATE;
    case WM_ERASEBKGND: return 1;
    case WM_CLOSE:
      g_quit = true;
      DestroyWindow(window);
      return 0;
    case WM_DESTROY:
      PostQuitMessage(0);
      return 0;
    default: return DefWindowProcW(window, message, wparam, lparam);
  }
}

LRESULT CALLBACK renderer_window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
  switch (message) {
    case WM_NCHITTEST: return HTTRANSPARENT;
    case WM_MOUSEACTIVATE: return MA_NOACTIVATE;
    case WM_ERASEBKGND: return 1;
    default: return DefWindowProcW(window, message, wparam, lparam);
  }
}

HWND find_existing_render_window() {
  struct State { HWND result = nullptr; } state;
  EnumWindows([](HWND top, LPARAM data) -> BOOL {
    auto* state = reinterpret_cast<State*>(data);
    if (class_name(top) == kWindowClass) {
      state->result = top;
      return FALSE;
    }
    EnumChildWindows(top, [](HWND child, LPARAM nested) -> BOOL {
      auto* state = reinterpret_cast<State*>(nested);
      if (class_name(child) == kWindowClass) {
        state->result = child;
        return FALSE;
      }
      return TRUE;
    }, data);
    return state->result ? FALSE : TRUE;
  }, reinterpret_cast<LPARAM>(&state));
  return state.result;
}

int send_control(const std::wstring& argument) {
  g_control_message = RegisterWindowMessageW(kControlMessageName);
  const HWND target = find_existing_render_window();
  if (!target) {
    std::wcerr << L"AquariumSpike host window not found.\n";
    return 2;
  }
  Control control{};
  if (argument == L"--pause") control = Control::Pause;
  else if (argument == L"--resume") control = Control::Resume;
  else if (argument == L"--toggle") control = Control::Toggle;
  else if (argument == L"--probe") control = Control::Probe;
  else if (argument == L"--quit") control = Control::Quit;
  else return 3;
  if (!PostMessageW(target, g_control_message, static_cast<WPARAM>(control), 0)) {
    std::wcerr << L"PostMessage failed: " << GetLastError() << L"\n";
    return 4;
  }
  std::wcout << L"Sent " << argument << L" to " << hex_handle(target) << L"\n";
  return 0;
}

HWND create_top_level_host_window(HINSTANCE instance, int width, int height) {
  WNDCLASSEXW owner_class{sizeof(owner_class)};
  owner_class.style = CS_DBLCLKS;
  owner_class.lpfnWndProc = DefWindowProcW;
  owner_class.hInstance = instance;
  owner_class.lpszClassName = kOwnerWindowClass;
  if (!RegisterClassExW(&owner_class) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
    log_line(L"RegisterClassEx(hidden owner) failed error=" + std::to_wstring(GetLastError()));
    return nullptr;
  }
  WNDCLASSEXW window_class{sizeof(window_class)};
  window_class.style = CS_DBLCLKS;
  window_class.lpfnWndProc = window_proc;
  window_class.hInstance = instance;
  window_class.lpszClassName = kWindowClass;
  window_class.hCursor = LoadCursorW(nullptr, IDC_ARROW);
  if (!RegisterClassExW(&window_class) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
    log_line(L"RegisterClassEx failed error=" + std::to_wstring(GetLastError()));
    return nullptr;
  }
  WNDCLASSEXW renderer_class{sizeof(renderer_class)};
  renderer_class.style = CS_DBLCLKS;
  renderer_class.lpfnWndProc = renderer_window_proc;
  renderer_class.hInstance = instance;
  renderer_class.lpszClassName = kRendererChildClass;
  renderer_class.hCursor = LoadCursorW(nullptr, IDC_ARROW);
  if (!RegisterClassExW(&renderer_class) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
    log_line(L"RegisterClassEx(renderer child) failed error=" + std::to_wstring(GetLastError()));
    return nullptr;
  }
  g_owner_window = CreateWindowExW(
      WS_EX_TOOLWINDOW | WS_EX_WINDOWEDGE,
      kOwnerWindowClass, L"",
      WS_CAPTION | WS_CLIPSIBLINGS,
      0, 0, 0, 0, nullptr, nullptr, instance, nullptr);
  if (!g_owner_window) {
    log_line(L"CreateWindowEx(hidden owner) failed error=" + std::to_wstring(GetLastError()));
    return nullptr;
  }
  SetWindowPos(g_owner_window, nullptr, -32000, -32000, 16, 16,
               SWP_NOACTIVATE | SWP_NOZORDER | SWP_NOOWNERZORDER);
  log_window(L"Final hidden owner", g_owner_window);

  HWND window = CreateWindowExW(
      0,
      kWindowClass, L"Aquarium.exe WebView2 feasibility spike",
      WS_POPUP | WS_CLIPSIBLINGS | WS_CLIPCHILDREN,
      0, 0, width, height, g_owner_window, nullptr, instance, nullptr);
  if (!window) {
    log_line(L"CreateWindowEx failed error=" + std::to_wstring(GetLastError()));
    return nullptr;
  }
  g_renderer_window = CreateWindowExW(
      WS_EX_TRANSPARENT, kRendererChildClass, L"Aquarium.exe WebView2 renderer child",
      WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN | WS_TABSTOP,
      0, 0, width, height, window, nullptr, instance, nullptr);
  if (!g_renderer_window) {
    log_line(L"CreateWindowEx(renderer child) failed error=" + std::to_wstring(GetLastError()));
    DestroyWindow(window);
    return nullptr;
  }
  return window;
}

bool attach_render_window_to_desktop(HWND window, int width, int height) {
  LONG_PTR ex_style = GetWindowLongPtrW(window, GWL_EXSTYLE);
  ex_style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_CONTROLPARENT;
  SetLastError(ERROR_SUCCESS);
  if (!SetWindowLongPtrW(window, GWL_EXSTYLE, ex_style) && GetLastError() != ERROR_SUCCESS) {
    log_line(L"SetWindowLongPtr(desktop ex styles) failed error=" + std::to_wstring(GetLastError()));
    return false;
  }

  ex_style |= WS_EX_LAYERED;
  SetLastError(ERROR_SUCCESS);
  if (!SetWindowLongPtrW(window, GWL_EXSTYLE, ex_style) && GetLastError() != ERROR_SUCCESS) {
    log_line(L"SetWindowLongPtr(WS_EX_LAYERED) failed error=" + std::to_wstring(GetLastError()));
    return false;
  }
  if (!SetLayeredWindowAttributes(window, 0, 255, LWA_ALPHA)) {
    log_line(L"SetLayeredWindowAttributes failed error=" + std::to_wstring(GetLastError()));
    return false;
  }
  log_window(L"desktop host after extended-style setup", window);

  LONG_PTR style = GetWindowLongPtrW(window, GWL_STYLE);
  style = (style & ~static_cast<LONG_PTR>(WS_POPUP)) |
          WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN | WS_TABSTOP;
  SetLastError(ERROR_SUCCESS);
  if (!SetWindowLongPtrW(window, GWL_STYLE, style) && GetLastError() != ERROR_SUCCESS) {
    log_line(L"SetWindowLongPtr(WS_CHILD) failed error=" + std::to_wstring(GetLastError()));
    return false;
  }
  log_window(L"desktop host after WS_CHILD conversion", window);

  const HWND parent = g_raised_desktop ? g_progman : g_workerw;
  SetLastError(ERROR_SUCCESS);
  const HWND previous_parent = SetParent(window, parent);
  if (!previous_parent && GetLastError() != ERROR_SUCCESS) {
    log_line(L"SetParent failed error=" + std::to_wstring(GetLastError()));
    return false;
  }
  log_window(L"desktop host after SetParent", window);

  const HWND insert_after = g_raised_desktop ? g_defview : HWND_BOTTOM;
  if (!SetWindowPos(window, insert_after, 0, 0, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW)) {
    log_line(L"SetWindowPos failed error=" + std::to_wstring(GetLastError()));
    return false;
  }
  return true;
}

double process_cpu_percent(FILETIME previous_kernel, FILETIME previous_user, double wall_seconds,
                           FILETIME* next_kernel, FILETIME* next_user) {
  FILETIME creation{}, exit{};
  if (!GetProcessTimes(GetCurrentProcess(), &creation, &exit, next_kernel, next_user)) return -1;
  auto ticks = [](FILETIME value) {
    ULARGE_INTEGER number{};
    number.LowPart = value.dwLowDateTime;
    number.HighPart = value.dwHighDateTime;
    return number.QuadPart;
  };
  const double cpu_seconds = (ticks(*next_kernel) - ticks(previous_kernel) +
                              ticks(*next_user) - ticks(previous_user)) / 10000000.0;
  SYSTEM_INFO info{};
  GetSystemInfo(&info);
  return wall_seconds > 0 ? cpu_seconds / wall_seconds / std::max<DWORD>(1, info.dwNumberOfProcessors) * 100.0 : 0;
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
  if (argc == 2) return send_control(argv[1]);
  if (argc != 1) {
    std::wcerr << L"Usage: AquariumSpike.exe [--pause|--resume|--toggle|--probe|--quit]\n";
    return 64;
  }

  const auto log_path = std::filesystem::path(argv[0]).parent_path() / L"aquarium-spike.log";
  g_log.open(log_path, std::ios::out | std::ios::trunc);
  if (!g_log) {
    std::wcerr << L"Unable to open log: " << log_path << L"\n";
    return 65;
  }
  const HRESULT com_result = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
  if (FAILED(com_result)) {
    std::wcerr << L"CoInitializeEx failed: 0x" << std::hex << com_result << L"\n";
    return 66;
  }
  log_line(L"Aquarium.exe WebView2 composition wallpaper spike starting");
  log_os_build();
  g_control_message = RegisterWindowMessageW(kControlMessageName);

  if (!discover_desktop_host()) return 10;
  RECT client{};
  GetClientRect(g_workerw, &client);
  const int width = client.right - client.left;
  const int height = client.bottom - client.top;
  if (width <= 0 || height <= 0) {
    log_line(L"ATTACH FAILURE: selected WorkerW has an empty client area.");
    return 11;
  }

  g_window = create_top_level_host_window(GetModuleHandleW(nullptr), width, height);
  if (!g_window) return 12;

  if (!SetWindowPos(g_window, HWND_TOP, 0, 0, width, height,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW)) {
    log_line(L"Experiment A top-level SetWindowPos failed error=" + std::to_wstring(GetLastError()));
    DestroyWindow(g_window);
    return 12;
  }
  WebViewRuntime webview_runtime;
  g_webview_runtime = &webview_runtime;
  bool webview_ready = false;
  bool webview_failed = false;
  const auto executable_directory = std::filesystem::path(argv[0]).parent_path();
  const auto habitat_directory = executable_directory / L"habitat";
  const auto user_data_directory = executable_directory / L"webview2-user-data";
  const RECT webview_bounds{0, 0, width, height};
  if (!webview_runtime.initialize(
          g_renderer_window, g_owner_window, webview_bounds, habitat_directory,
          user_data_directory, 1,
          [&](std::uint64_t generation, WebViewEvent event, const std::wstring& detail) {
            std::wostringstream line;
            line << L"WEBVIEW generation=" << generation << L" event=";
            if (event == WebViewEvent::Ready) line << L"ready";
            else if (event == WebViewEvent::Failure) line << L"failure";
            else line << L"info";
            line << L" detail=" << detail;
            log_line(line.str());
            if (event == WebViewEvent::Ready) webview_ready = true;
            if (event == WebViewEvent::Failure) webview_failed = true;
          })) {
    DestroyWindow(g_window);
    CoUninitialize();
    return 14;
  }
  const auto initialization_deadline =
      std::chrono::steady_clock::now() + std::chrono::seconds(30);
  while (!webview_ready && !webview_failed &&
         std::chrono::steady_clock::now() < initialization_deadline) {
    MSG message{};
    while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
      TranslateMessage(&message);
      DispatchMessageW(&message);
    }
    MsgWaitForMultipleObjectsEx(0, nullptr, 50, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
  }
  if (!webview_ready) {
    log_line(webview_failed ? L"WEBVIEW INITIALIZATION FAILED" : L"WEBVIEW INITIALIZATION TIMEOUT");
    webview_runtime.shutdown();
    DestroyWindow(g_window);
    CoUninitialize();
    return 14;
  }
  log_window(L"WebView2 top-level host before desktop attachment", g_window);
  log_window(L"WebView2 renderer child before desktop attachment", g_renderer_window);
  log_line(L"WEBVIEW TOP-LEVEL PRESENT OK: local habitat reported ready before desktop attachment.");
  Sleep(1500);

  if (!attach_render_window_to_desktop(g_window, width, height)) {
    DestroyWindow(g_window);
    return 12;
  }
  log_window(L"WebView2 host after desktop attachment", g_window);
  log_line(L"WebView2 host owner after desktop attachment=" + hex_handle(GetWindow(g_window, GW_OWNER)));
  log_window(L"WebView2 renderer child after desktop attachment", g_renderer_window);
  const HWND expected_parent = g_raised_desktop ? g_progman : g_workerw;
  if (GetParent(g_window) != expected_parent) {
    log_line(L"ATTACH FAILURE: render window does not have the expected desktop parent.");
    DestroyWindow(g_window);
    return 13;
  }
  log_progman_children(L"after render-window attachment");
  if (g_raised_desktop &&
      !(ordered_above(g_progman, g_defview, g_window) &&
        ordered_above(g_progman, g_window, g_workerw))) {
    log_line(L"ATTACH FAILURE: raised-desktop Z order is not DefView > render window > WorkerW.");
    DestroyWindow(g_window);
    return 13;
  }
  log_line(g_raised_desktop
               ? L"ATTACH STRUCTURE OK: layered host is parented to Progman, immediately below SHELLDLL_DefView and above WorkerW."
               : L"ATTACH STRUCTURE OK: render child is parented to the classic below-icons WorkerW.");
  log_line(L"Structural attachment does not prove that Explorer/DWM visibly composites the surface.");
  log_line(L"No normal always-on-bottom fallback exists in this spike.");

  log_probe();

  using clock = std::chrono::steady_clock;
  auto previous = clock::now();
  auto report_start = previous;
  unsigned long long report_frames = 0;
  FILETIME creation{}, exit{}, previous_kernel{}, previous_user{};
  GetProcessTimes(GetCurrentProcess(), &creation, &exit, &previous_kernel, &previous_user);

  while (!g_quit) {
    MSG message{};
    while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
      if (message.message == WM_QUIT) g_quit = true;
      TranslateMessage(&message);
      DispatchMessageW(&message);
    }
    if (g_quit) break;
    const auto now = clock::now();
    const double elapsed = std::chrono::duration<double>(now - previous).count();
    if (elapsed < 1.0 / 30.0) {
      const DWORD wait_ms = static_cast<DWORD>(std::max(1.0, (1.0 / 30.0 - elapsed) * 1000.0));
      MsgWaitForMultipleObjectsEx(0, nullptr, wait_ms, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
      continue;
    }
    previous = now;
    POINT cursor{};
    bool present = false;
    double normalized_x = 0;
    double normalized_y = 0;
    if (GetCursorPos(&cursor) && ScreenToClient(g_renderer_window, &cursor)) {
      present = cursor.x >= 0 && cursor.y >= 0 && cursor.x < width && cursor.y < height;
      normalized_x = static_cast<double>(cursor.x) / width;
      normalized_y = static_cast<double>(cursor.y) / height;
    }
    webview_runtime.post_json(aquarium::pointer_message(present, normalized_x, normalized_y));
    ++g_frames;

    const double report_seconds = std::chrono::duration<double>(now - report_start).count();
    if (report_seconds >= 5.0) {
      FILETIME kernel{}, user{};
      const double cpu = process_cpu_percent(previous_kernel, previous_user, report_seconds, &kernel, &user);
      std::wostringstream out;
      out << L"PERF intervalSeconds=" << std::fixed << std::setprecision(2) << report_seconds
          << L" cursorBridgeHz=" << (g_frames - report_frames) / report_seconds
          << L" hostProcessCpuPercentNormalized=" << cpu << L" totalBridgeUpdates=" << g_frames;
      log_line(out.str());
      previous_kernel = kernel;
      previous_user = user;
      report_start = now;
      report_frames = g_frames;
    }
  }

  log_probe();
  g_webview_runtime = nullptr;
  webview_runtime.shutdown();
  if (g_window) DestroyWindow(g_window);
  if (g_owner_window) DestroyWindow(g_owner_window);
  log_line(L"Aquarium.exe WebView2 composition wallpaper spike stopped");
  CoUninitialize();
  return 0;
}
