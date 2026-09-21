#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <unknwn.h>
#include <d3d11.h>
#include <dcomp.h>
#include <dxgi.h>
#include <wrl.h>
#include <wrl/client.h>
#include <wrl/event.h>

#include <WebView2.h>
#include <WebView2EnvironmentOptions.h>

#include <array>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <utility>

#include "webview_runtime.h"

using Microsoft::WRL::Callback;
using Microsoft::WRL::ComPtr;
using Microsoft::WRL::Make;

namespace {

std::wstring hresult_text(const wchar_t* operation, HRESULT result) {
  std::wostringstream out;
  out << operation << L" HRESULT=0x" << std::hex << std::uppercase
      << static_cast<unsigned long>(result);
  return out.str();
}

std::wstring widen_ascii(const std::string& text) {
  return std::wstring(text.begin(), text.end());
}

}  // namespace

struct WebViewRuntime::Impl {
  bool initialize(HWND requested_renderer_window, HWND requested_controller_parent_window,
                  const RECT& requested_bounds,
                  const std::filesystem::path& habitat_directory,
                  const std::filesystem::path& user_data_directory,
                  std::uint64_t requested_generation, EventCallback requested_callback) {
    shutdown();
    renderer_window = requested_renderer_window;
    controller_parent_window = requested_controller_parent_window;
    bounds = requested_bounds;
    generation = requested_generation;
    callback = std::move(requested_callback);
    habitat = std::filesystem::weakly_canonical(habitat_directory);
    if (!std::filesystem::is_regular_file(habitat / L"index.html")) {
      emit(WebViewEvent::Failure, L"Local habitat/index.html was not found.");
      return false;
    }
    std::filesystem::create_directories(user_data_directory);

    const std::array feature_levels{D3D_FEATURE_LEVEL_11_1, D3D_FEATURE_LEVEL_11_0};
    D3D_FEATURE_LEVEL selected{};
    HRESULT result = D3D11CreateDevice(
        nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        feature_levels.data(), static_cast<UINT>(feature_levels.size()), D3D11_SDK_VERSION,
        d3d_device.GetAddressOf(), &selected, d3d_context.GetAddressOf());
    if (result == E_INVALIDARG) {
      result = D3D11CreateDevice(
          nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, D3D11_CREATE_DEVICE_BGRA_SUPPORT,
          feature_levels.data() + 1, 1, D3D11_SDK_VERSION,
          d3d_device.GetAddressOf(), &selected, d3d_context.GetAddressOf());
    }
    if (FAILED(result)) return fail_immediate(L"D3D11CreateDevice", result);

    ComPtr<IDXGIDevice> dxgi_device;
    if (FAILED(result = d3d_device.As(&dxgi_device))) {
      return fail_immediate(L"Query IDXGIDevice", result);
    }
    if (FAILED(result = DCompositionCreateDevice(
                   dxgi_device.Get(), IID_PPV_ARGS(composition_device.GetAddressOf()))) ||
        FAILED(result = composition_device->CreateTargetForHwnd(
                   requested_renderer_window, TRUE, composition_target.GetAddressOf())) ||
        FAILED(result = composition_device->CreateVisual(root_visual.GetAddressOf())) ||
        FAILED(result = composition_device->CreateVisual(webview_visual.GetAddressOf())) ||
        FAILED(result = root_visual->AddVisual(webview_visual.Get(), TRUE, nullptr)) ||
        FAILED(result = composition_target->SetRoot(root_visual.Get())) ||
        FAILED(result = composition_device->Commit())) {
      return fail_immediate(L"Create DirectComposition visual tree", result);
    }
    emit(WebViewEvent::Info,
         L"DirectComposition target and WebView visual created on renderer child HWND.");

    auto options = Make<CoreWebView2EnvironmentOptions>();
    if (!options) {
      emit(WebViewEvent::Failure, L"Unable to allocate WebView2 environment options.");
      return false;
    }
    options->put_AdditionalBrowserArguments(
        L"--disable-background-networking --disable-component-update --no-proxy-server");

    const auto callback_generation = generation;
    const HRESULT create_result = CreateCoreWebView2EnvironmentWithOptions(
        nullptr, user_data_directory.c_str(), options.Get(),
        Callback<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler>(
            [this, callback_generation](HRESULT environment_result,
                                        ICoreWebView2Environment* created_environment) -> HRESULT {
              if (!is_current(callback_generation)) return S_OK;
              if (FAILED(environment_result) || !created_environment) {
                emit(WebViewEvent::Failure,
                     hresult_text(L"CreateCoreWebView2Environment", environment_result));
                return S_OK;
              }
              environment = created_environment;
              ComPtr<ICoreWebView2Environment3> environment3;
              HRESULT result = environment.As(&environment3);
              if (FAILED(result)) {
                emit(WebViewEvent::Failure,
                     hresult_text(L"Query ICoreWebView2Environment3", result));
                return S_OK;
              }
              result = environment3->CreateCoreWebView2CompositionController(
                  this->controller_parent_window,
                  Callback<ICoreWebView2CreateCoreWebView2CompositionControllerCompletedHandler>(
                      [this, callback_generation](HRESULT controller_result,
                                                  ICoreWebView2CompositionController* created)
                          -> HRESULT {
                        if (!is_current(callback_generation)) return S_OK;
                        if (FAILED(controller_result) || !created) {
                          emit(WebViewEvent::Failure,
                               hresult_text(L"CreateCoreWebView2CompositionController",
                                            controller_result));
                          return S_OK;
                        }
                        composition_controller = created;
                        HRESULT result = composition_controller.As(&controller);
                        if (FAILED(result) ||
                            FAILED(result = controller->get_CoreWebView2(webview.GetAddressOf()))) {
                          emit(WebViewEvent::Failure,
                               hresult_text(L"Get CoreWebView2 controller", result));
                          return S_OK;
                        }
                        if (FAILED(result = controller->put_Bounds(this->bounds)) ||
                            FAILED(result = controller->put_IsVisible(TRUE)) ||
                            FAILED(result = composition_controller->put_RootVisualTarget(
                                               webview_visual.Get())) ||
                            FAILED(result = composition_device->Commit())) {
                          emit(WebViewEvent::Failure,
                               hresult_text(L"Bind CompositionController visual", result));
                          return S_OK;
                        }
                        configure_webview(callback_generation);
                        return S_OK;
                      }).Get());
              if (FAILED(result)) {
                emit(WebViewEvent::Failure,
                     hresult_text(L"Begin CreateCoreWebView2CompositionController", result));
              }
              return S_OK;
            }).Get());
    if (FAILED(create_result)) {
      return fail_immediate(L"Begin CreateCoreWebView2Environment", create_result);
    }
    emit(WebViewEvent::Info, L"WebView2 environment creation started.");
    return true;
  }

  void configure_webview(std::uint64_t callback_generation) {
    HRESULT result = S_OK;
    ComPtr<ICoreWebView2_3> webview3;
    if (FAILED(result = webview.As(&webview3)) ||
        FAILED(result = webview3->SetVirtualHostNameToFolderMapping(
                   L"aquarium.local", habitat.c_str(),
                   COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_DENY_CORS))) {
      emit(WebViewEvent::Failure, hresult_text(L"Map local habitat directory", result));
      return;
    }

    webview->add_NavigationStarting(
        Callback<ICoreWebView2NavigationStartingEventHandler>(
            [this, callback_generation](ICoreWebView2*,
                                        ICoreWebView2NavigationStartingEventArgs* args) -> HRESULT {
              if (!is_current(callback_generation)) return S_OK;
              LPWSTR uri = nullptr;
              if (SUCCEEDED(args->get_Uri(&uri)) && uri) {
                const std::wstring value(uri);
                CoTaskMemFree(uri);
                if (!value.starts_with(L"https://aquarium.local/")) {
                  args->put_Cancel(TRUE);
                  emit(WebViewEvent::Info, L"Blocked external navigation: " + value);
                }
              }
              return S_OK;
            }).Get(),
        &navigation_token);
    webview->add_WebMessageReceived(
        Callback<ICoreWebView2WebMessageReceivedEventHandler>(
            [this, callback_generation](ICoreWebView2*,
                                        ICoreWebView2WebMessageReceivedEventArgs* args) -> HRESULT {
              if (!is_current(callback_generation)) return S_OK;
              LPWSTR message = nullptr;
              if (SUCCEEDED(args->TryGetWebMessageAsString(&message)) && message) {
                const std::wstring value(message);
                CoTaskMemFree(message);
                if (value.starts_with(L"habitat-ready:")) {
                  is_ready = true;
                  emit(WebViewEvent::Ready, value);
                } else {
                  emit(WebViewEvent::Info, L"Habitat: " + value);
                }
              }
              return S_OK;
            }).Get(),
        &message_token);
    webview->add_ProcessFailed(
        Callback<ICoreWebView2ProcessFailedEventHandler>(
            [this, callback_generation](ICoreWebView2*,
                                        ICoreWebView2ProcessFailedEventArgs*) -> HRESULT {
              if (is_current(callback_generation)) {
                emit(WebViewEvent::Failure, L"WebView2 ProcessFailed event.");
              }
              return S_OK;
            }).Get(),
        &process_failed_token);

    ComPtr<ICoreWebView2Settings> settings;
    if (SUCCEEDED(webview->get_Settings(settings.GetAddressOf()))) {
      settings->put_AreDefaultContextMenusEnabled(FALSE);
      settings->put_AreDevToolsEnabled(FALSE);
      settings->put_IsStatusBarEnabled(FALSE);
    }
    result = webview->Navigate(L"https://aquarium.local/index.html");
    if (FAILED(result)) {
      emit(WebViewEvent::Failure, hresult_text(L"Navigate local habitat", result));
      return;
    }
    emit(WebViewEvent::Info,
         L"CompositionController bound; navigating to local aquarium habitat.");
  }

  bool post_json(const std::string& json) {
    if (!webview || !is_ready) return false;
    return SUCCEEDED(webview->PostWebMessageAsJson(widen_ascii(json).c_str()));
  }

  void set_visible(bool visible) {
    if (controller) controller->put_IsVisible(visible ? TRUE : FALSE);
  }

  void shutdown() {
    is_ready = false;
    ++generation;
    if (controller) controller->Close();
    webview.Reset();
    controller.Reset();
    composition_controller.Reset();
    environment.Reset();
    if (composition_target) composition_target->SetRoot(nullptr);
    if (composition_device) composition_device->Commit();
    webview_visual.Reset();
    root_visual.Reset();
    composition_target.Reset();
    composition_device.Reset();
    d3d_context.Reset();
    d3d_device.Reset();
  }

  bool fail_immediate(const wchar_t* operation, HRESULT result) {
    emit(WebViewEvent::Failure, hresult_text(operation, result));
    return false;
  }

  bool is_current(std::uint64_t callback_generation) const {
    return generation == callback_generation;
  }

  void emit(WebViewEvent event, const std::wstring& detail) const {
    if (callback) callback(generation, event, detail);
  }

  std::uint64_t generation = 0;
  EventCallback callback;
  bool is_ready = false;
  RECT bounds{};
  HWND renderer_window = nullptr;
  HWND controller_parent_window = nullptr;
  std::filesystem::path habitat;
  EventRegistrationToken navigation_token{};
  EventRegistrationToken message_token{};
  EventRegistrationToken process_failed_token{};
  ComPtr<ID3D11Device> d3d_device;
  ComPtr<ID3D11DeviceContext> d3d_context;
  ComPtr<IDCompositionDevice> composition_device;
  ComPtr<IDCompositionTarget> composition_target;
  ComPtr<IDCompositionVisual> root_visual;
  ComPtr<IDCompositionVisual> webview_visual;
  ComPtr<ICoreWebView2Environment> environment;
  ComPtr<ICoreWebView2CompositionController> composition_controller;
  ComPtr<ICoreWebView2Controller> controller;
  ComPtr<ICoreWebView2> webview;
};

WebViewRuntime::WebViewRuntime() : impl_(std::make_unique<Impl>()) {}
WebViewRuntime::~WebViewRuntime() { impl_->shutdown(); }

bool WebViewRuntime::initialize(HWND renderer_window, HWND controller_parent_window,
                                const RECT& bounds,
                                const std::filesystem::path& habitat_directory,
                                const std::filesystem::path& user_data_directory,
                                std::uint64_t generation, EventCallback callback) {
  impl_->bounds = bounds;
  impl_->renderer_window = renderer_window;
  return impl_->initialize(renderer_window, controller_parent_window, bounds, habitat_directory,
                           user_data_directory, generation, std::move(callback));
}

bool WebViewRuntime::post_json(const std::string& json) { return impl_->post_json(json); }
void WebViewRuntime::set_visible(bool visible) { impl_->set_visible(visible); }
void WebViewRuntime::shutdown() { impl_->shutdown(); }
bool WebViewRuntime::ready() const { return impl_->is_ready; }
