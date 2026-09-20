#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <dxgi.h>
#include <wrl/client.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

#include "fish_logic.h"

using Microsoft::WRL::ComPtr;

namespace {

constexpr wchar_t kWindowClass[] = L"AquariumSpike.RenderWindow.v1";
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
aquarium::FishState g_fish{420.0f, 360.0f, 85.0f, 0.0f, 1.0f, 0};
aquarium::PointerState g_pointer{false, 0, 0};
HWND g_window = nullptr;
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

struct Vertex {
  float x, y;
  float r, g, b, a;
};

class Renderer {
 public:
  bool initialize(HWND window, int width, int height) {
    width_ = static_cast<float>(width);
    height_ = static_cast<float>(height);
    DXGI_SWAP_CHAIN_DESC swap{};
    swap.BufferDesc.Width = width;
    swap.BufferDesc.Height = height;
    swap.BufferDesc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    swap.SampleDesc.Count = 1;
    swap.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    swap.BufferCount = 2;
    swap.OutputWindow = window;
    swap.Windowed = TRUE;
    swap.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;

    const std::array levels{D3D_FEATURE_LEVEL_11_1, D3D_FEATURE_LEVEL_11_0};
    D3D_FEATURE_LEVEL selected{};
    HRESULT hr = D3D11CreateDeviceAndSwapChain(
        nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        levels.data(), static_cast<UINT>(levels.size()), D3D11_SDK_VERSION, &swap,
        swap_chain_.GetAddressOf(), device_.GetAddressOf(), &selected, context_.GetAddressOf());
    if (hr == E_INVALIDARG) {
      hr = D3D11CreateDeviceAndSwapChain(
          nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, D3D11_CREATE_DEVICE_BGRA_SUPPORT,
          levels.data() + 1, 1, D3D11_SDK_VERSION, &swap,
          swap_chain_.GetAddressOf(), device_.GetAddressOf(), &selected, context_.GetAddressOf());
    }
    if (FAILED(hr)) {
      log_hresult(L"D3D11CreateDeviceAndSwapChain(HARDWARE)", hr);
      return false;
    }

    ComPtr<IDXGIDevice> dxgi_device;
    ComPtr<IDXGIAdapter> adapter;
    DXGI_ADAPTER_DESC description{};
    if (SUCCEEDED(device_.As(&dxgi_device)) &&
        SUCCEEDED(dxgi_device->GetAdapter(adapter.GetAddressOf())) &&
        SUCCEEDED(adapter->GetDesc(&description))) {
      std::wostringstream out;
      out << L"D3D11 adapter=\"" << description.Description << L"\" vendor=0x" << std::hex
          << description.VendorId << L" device=0x" << description.DeviceId << std::dec
          << L" dedicatedVideoMB=" << description.DedicatedVideoMemory / (1024 * 1024)
          << L" featureLevel=0x" << std::hex << selected;
      log_line(out.str());
    }

    ComPtr<ID3D11Texture2D> back_buffer;
    if (FAILED(hr = swap_chain_->GetBuffer(0, IID_PPV_ARGS(back_buffer.GetAddressOf()))) ||
        FAILED(hr = device_->CreateRenderTargetView(back_buffer.Get(), nullptr, target_.GetAddressOf()))) {
      log_hresult(L"CreateRenderTargetView", hr);
      return false;
    }

    static constexpr char vertex_source[] =
        "struct V{float2 p:POSITION;float4 c:COLOR;};"
        "struct O{float4 p:SV_POSITION;float4 c:COLOR;};"
        "O main(V v){O o;o.p=float4(v.p,0,1);o.c=v.c;return o;}";
    static constexpr char pixel_source[] =
        "struct I{float4 p:SV_POSITION;float4 c:COLOR;};"
        "float4 main(I i):SV_TARGET{return i.c;}";
    ComPtr<ID3DBlob> vertex_blob;
    ComPtr<ID3DBlob> pixel_blob;
    ComPtr<ID3DBlob> errors;
    if (FAILED(hr = D3DCompile(vertex_source, sizeof(vertex_source), nullptr, nullptr, nullptr,
                               "main", "vs_4_0", 0, 0, vertex_blob.GetAddressOf(), errors.GetAddressOf()))) {
      log_shader_error(L"vertex shader", hr, errors.Get());
      return false;
    }
    errors.Reset();
    if (FAILED(hr = D3DCompile(pixel_source, sizeof(pixel_source), nullptr, nullptr, nullptr,
                               "main", "ps_4_0", 0, 0, pixel_blob.GetAddressOf(), errors.GetAddressOf()))) {
      log_shader_error(L"pixel shader", hr, errors.Get());
      return false;
    }
    if (FAILED(hr = device_->CreateVertexShader(vertex_blob->GetBufferPointer(), vertex_blob->GetBufferSize(),
                                                 nullptr, vertex_shader_.GetAddressOf())) ||
        FAILED(hr = device_->CreatePixelShader(pixel_blob->GetBufferPointer(), pixel_blob->GetBufferSize(),
                                                nullptr, pixel_shader_.GetAddressOf()))) {
      log_hresult(L"CreateShader", hr);
      return false;
    }
    const D3D11_INPUT_ELEMENT_DESC input[] = {
        {"POSITION", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 0, D3D11_INPUT_PER_VERTEX_DATA, 0},
        {"COLOR", 0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 8, D3D11_INPUT_PER_VERTEX_DATA, 0}};
    if (FAILED(hr = device_->CreateInputLayout(input, 2, vertex_blob->GetBufferPointer(),
                                                vertex_blob->GetBufferSize(), input_layout_.GetAddressOf()))) {
      log_hresult(L"CreateInputLayout", hr);
      return false;
    }
    D3D11_BUFFER_DESC buffer{};
    buffer.ByteWidth = sizeof(Vertex) * 256;
    buffer.Usage = D3D11_USAGE_DYNAMIC;
    buffer.BindFlags = D3D11_BIND_VERTEX_BUFFER;
    buffer.CPUAccessFlags = D3D11_CPU_ACCESS_WRITE;
    if (FAILED(hr = device_->CreateBuffer(&buffer, nullptr, vertex_buffer_.GetAddressOf()))) {
      log_hresult(L"CreateBuffer", hr);
      return false;
    }
    D3D11_VIEWPORT viewport{0, 0, static_cast<float>(width), static_cast<float>(height), 0, 1};
    context_->RSSetViewports(1, &viewport);
    return true;
  }

  bool draw(const aquarium::FishState& fish) {
    std::vector<Vertex> vertices;
    vertices.reserve(96);
    const bool alarm = fish.startled;
    const std::array<float, 4> body = alarm ? std::array{1.0f, 0.25f, 0.12f, 1.0f}
                                            : std::array{0.98f, 0.62f, 0.16f, 1.0f};
    constexpr int segments = 24;
    for (int i = 0; i < segments; ++i) {
      const float a0 = 6.2831853f * i / segments;
      const float a1 = 6.2831853f * (i + 1) / segments;
      add_triangle(vertices,
                   point(fish.x, fish.y, body),
                   point(fish.x + std::cos(a0) * 72.0f, fish.y + std::sin(a0) * 34.0f, body),
                   point(fish.x + std::cos(a1) * 72.0f, fish.y + std::sin(a1) * 34.0f, body));
    }
    const float tail_x = fish.x - fish.facing * 68.0f;
    const float tail_tip = fish.x - fish.facing * 118.0f;
    add_triangle(vertices,
                 point(tail_x, fish.y, body), point(tail_tip, fish.y - 45.0f, body),
                 point(tail_tip, fish.y + 45.0f, body));
    const std::array<float, 4> eye{0.02f, 0.03f, 0.04f, 1.0f};
    const float eye_x = fish.x + fish.facing * 42.0f;
    add_triangle(vertices, point(eye_x - 5, fish.y - 10, eye), point(eye_x + 5, fish.y - 10, eye),
                 point(eye_x, fish.y, eye));

    D3D11_MAPPED_SUBRESOURCE mapped{};
    const HRESULT hr = context_->Map(vertex_buffer_.Get(), 0, D3D11_MAP_WRITE_DISCARD, 0, &mapped);
    if (FAILED(hr)) {
      log_hresult(L"Map(vertex buffer)", hr);
      return false;
    }
    memcpy(mapped.pData, vertices.data(), vertices.size() * sizeof(Vertex));
    context_->Unmap(vertex_buffer_.Get(), 0);

    const float clear[]{0.018f, 0.105f, 0.145f, 1.0f};
    context_->OMSetRenderTargets(1, target_.GetAddressOf(), nullptr);
    context_->ClearRenderTargetView(target_.Get(), clear);
    const UINT stride = sizeof(Vertex), offset = 0;
    context_->IASetVertexBuffers(0, 1, vertex_buffer_.GetAddressOf(), &stride, &offset);
    context_->IASetInputLayout(input_layout_.Get());
    context_->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    context_->VSSetShader(vertex_shader_.Get(), nullptr, 0);
    context_->PSSetShader(pixel_shader_.Get(), nullptr, 0);
    context_->Draw(static_cast<UINT>(vertices.size()), 0);
    const HRESULT present = swap_chain_->Present(1, 0);
    if (FAILED(present)) {
      log_hresult(L"Present", present);
      return false;
    }
    return true;
  }

 private:
  Vertex point(float x, float y, const std::array<float, 4>& color) const {
    return {x / width_ * 2.0f - 1.0f, 1.0f - y / height_ * 2.0f,
            color[0], color[1], color[2], color[3]};
  }

  static void add_triangle(std::vector<Vertex>& vertices, Vertex a, Vertex b, Vertex c) {
    vertices.push_back(a);
    vertices.push_back(b);
    vertices.push_back(c);
  }

  static void log_hresult(const wchar_t* operation, HRESULT hr) {
    std::wostringstream out;
    out << operation << L" failed HRESULT=0x" << std::hex << std::uppercase << static_cast<unsigned long>(hr);
    log_line(out.str());
  }

  static void log_shader_error(const wchar_t* stage, HRESULT hr, ID3DBlob* errors) {
    std::wostringstream out;
    out << stage << L" compile failed HRESULT=0x" << std::hex << std::uppercase << static_cast<unsigned long>(hr);
    if (errors) out << L" detail=" << reinterpret_cast<const char*>(errors->GetBufferPointer());
    log_line(out.str());
  }

  float width_ = 1;
  float height_ = 1;
  ComPtr<ID3D11Device> device_;
  ComPtr<ID3D11DeviceContext> context_;
  ComPtr<IDXGISwapChain> swap_chain_;
  ComPtr<ID3D11RenderTargetView> target_;
  ComPtr<ID3D11VertexShader> vertex_shader_;
  ComPtr<ID3D11PixelShader> pixel_shader_;
  ComPtr<ID3D11InputLayout> input_layout_;
  ComPtr<ID3D11Buffer> vertex_buffer_;
};

void log_probe() {
  POINT point{};
  GetCursorPos(&point);
  const HWND hit = WindowFromPoint(point);
  std::wostringstream out;
  out << L"PROBE state=" << (g_paused ? L"paused" : L"running") << L" frames=" << g_frames
      << L" fish=(" << std::fixed << std::setprecision(1) << g_fish.x << L"," << g_fish.y << L")"
      << L" velocity=(" << g_fish.vx << L"," << g_fish.vy << L")"
      << L" cursorScreen=(" << point.x << L"," << point.y << L") reactions=" << g_fish.reactions
      << L" WindowFromPoint=" << hex_handle(hit) << L"/" << class_name(hit)
      << L" renderHitTest=" << SendMessageW(g_window, WM_NCHITTEST, 0, MAKELPARAM(point.x, point.y));
  log_line(out.str());
}

LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
  if (message == g_control_message) {
    switch (static_cast<Control>(wparam)) {
      case Control::Pause:
        if (!g_paused) log_line(L"CONTROL pause");
        g_paused = true;
        break;
      case Control::Resume:
        if (g_paused) log_line(L"CONTROL resume");
        g_paused = false;
        break;
      case Control::Toggle:
        g_paused = !g_paused;
        log_line(std::wstring(L"CONTROL toggle -> ") + (g_paused ? L"paused" : L"running"));
        break;
      case Control::Probe:
        log_probe();
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

HWND create_render_window(HINSTANCE instance, int width, int height) {
  WNDCLASSEXW window_class{sizeof(window_class)};
  window_class.lpfnWndProc = window_proc;
  window_class.hInstance = instance;
  window_class.lpszClassName = kWindowClass;
  window_class.hCursor = LoadCursorW(nullptr, IDC_ARROW);
  if (!RegisterClassExW(&window_class) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
    log_line(L"RegisterClassEx failed error=" + std::to_wstring(GetLastError()));
    return nullptr;
  }
  HWND window = CreateWindowExW(
      WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
      kWindowClass, L"Aquarium.exe D3D11 feasibility spike",
      WS_POPUP | WS_CLIPSIBLINGS | WS_CLIPCHILDREN,
      0, 0, width, height, nullptr, nullptr, instance, nullptr);
  if (!window) {
    log_line(L"CreateWindowEx failed error=" + std::to_wstring(GetLastError()));
    return nullptr;
  }
  if (!SetLayeredWindowAttributes(window, 0, 255, LWA_ALPHA)) {
    log_line(L"SetLayeredWindowAttributes failed error=" + std::to_wstring(GetLastError()));
    DestroyWindow(window);
    return nullptr;
  }

  LONG_PTR style = GetWindowLongPtrW(window, GWL_STYLE);
  style = (style & ~static_cast<LONG_PTR>(WS_POPUP)) |
          WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN;
  SetLastError(ERROR_SUCCESS);
  if (!SetWindowLongPtrW(window, GWL_STYLE, style) && GetLastError() != ERROR_SUCCESS) {
    log_line(L"SetWindowLongPtr(WS_CHILD) failed error=" + std::to_wstring(GetLastError()));
    DestroyWindow(window);
    return nullptr;
  }

  const HWND parent = g_raised_desktop ? g_progman : g_workerw;
  SetLastError(ERROR_SUCCESS);
  const HWND previous_parent = SetParent(window, parent);
  if (!previous_parent && GetLastError() != ERROR_SUCCESS) {
    log_line(L"SetParent failed error=" + std::to_wstring(GetLastError()));
    DestroyWindow(window);
    return nullptr;
  }

  const HWND insert_after = g_raised_desktop ? g_defview : HWND_BOTTOM;
  if (!SetWindowPos(window, insert_after, 0, 0, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW)) {
    log_line(L"SetWindowPos failed error=" + std::to_wstring(GetLastError()));
    DestroyWindow(window);
    return nullptr;
  }
  return window;
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
  log_line(L"Aquarium.exe D3D11 wallpaper spike starting");
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

  g_window = create_render_window(GetModuleHandleW(nullptr), width, height);
  if (!g_window) return 12;
  log_window(L"render window", g_window);
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
               ? L"ATTACH STRUCTURE OK: layered render child is parented to Progman, immediately below SHELLDLL_DefView and above WorkerW."
               : L"ATTACH STRUCTURE OK: render child is parented to the classic below-icons WorkerW.");
  log_line(L"Structural attachment does not prove that Explorer/DWM visibly composites the surface.");
  log_line(L"No normal always-on-bottom fallback exists in this spike.");

  Renderer renderer;
  if (!renderer.initialize(g_window, width, height)) {
    DestroyWindow(g_window);
    return 14;
  }
  g_fish.y = height * 0.55f;
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
    if (g_paused) {
      WaitMessage();
      previous = clock::now();
      continue;
    }

    const auto now = clock::now();
    const double elapsed = std::chrono::duration<double>(now - previous).count();
    if (elapsed < 1.0 / 60.0) {
      const DWORD wait_ms = static_cast<DWORD>(std::max(1.0, (1.0 / 60.0 - elapsed) * 1000.0));
      MsgWaitForMultipleObjectsEx(0, nullptr, wait_ms, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
      continue;
    }
    previous = now;
    POINT cursor{};
    if (GetCursorPos(&cursor) && ScreenToClient(g_window, &cursor)) {
      g_pointer = {cursor.x >= 0 && cursor.y >= 0 && cursor.x < width && cursor.y < height,
                   static_cast<float>(cursor.x), static_cast<float>(cursor.y)};
    } else {
      g_pointer.present = false;
    }
    g_fish = aquarium::advance_fish(g_fish, g_pointer, static_cast<float>(std::min(elapsed, 0.1)),
                                    static_cast<float>(width), static_cast<float>(height));
    if (!renderer.draw(g_fish)) break;
    ++g_frames;

    const double report_seconds = std::chrono::duration<double>(now - report_start).count();
    if (report_seconds >= 5.0) {
      FILETIME kernel{}, user{};
      const double cpu = process_cpu_percent(previous_kernel, previous_user, report_seconds, &kernel, &user);
      std::wostringstream out;
      out << L"PERF intervalSeconds=" << std::fixed << std::setprecision(2) << report_seconds
          << L" presentedFps=" << (g_frames - report_frames) / report_seconds
          << L" processCpuPercentNormalized=" << cpu << L" totalFrames=" << g_frames;
      log_line(out.str());
      previous_kernel = kernel;
      previous_user = user;
      report_start = now;
      report_frames = g_frames;
    }
  }

  log_probe();
  if (g_window) DestroyWindow(g_window);
  log_line(L"Aquarium.exe D3D11 wallpaper spike stopped");
  return 0;
}
