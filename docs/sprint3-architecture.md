# Aquarium.exe Sprint #3 architecture

## Purpose

Prove the production-shaped runtime chain on Windows 11 build 26200.9457:

```text
Aquarium native Win32 host
  -> DirectComposition visual tree
  -> WebView2 CompositionController
  -> local habitat HTML/JavaScript
  -> WebGL2 / Three.js primitive fish
```

This remains feasibility code. It does not add product UI, packaging, multi-monitor support, telemetry, accounts, remote content, or visual polish.

## Preserved host boundary

The existing raised-desktop discovery and attachment from commit `00e0b58` remains authoritative: `Progman > SHELLDLL_DefView > Aquarium host > WorkerW`. The host stays layered, non-activating, and hit-test transparent. There is no normal top-level, always-on-bottom, or conventional HWND WebView2 fallback.

The native host owns Explorer discovery, HWND/DirectComposition lifetime, cursor sampling, controls, recovery, and future power/session integration. The habitat owns fish state, movement, proximity response, and drawing. Neither side reaches across that boundary.

## WebView2 composition host

The host creates a D3D11 BGRA device only to establish the proven DirectComposition device. It creates an `IDCompositionTarget` for the Aquarium renderer child, a root visual, and a WebView visual. `ICoreWebView2Environment3::CreateCoreWebView2CompositionController` creates the windowless WebView2 controller; `ICoreWebView2CompositionController::put_RootVisualTarget` connects WebView2 to the WebView visual. The host commits the composition tree after binding.

Content is exposed through `SetVirtualHostNameToFolderMapping` at `https://aquarium.local/`. Navigation outside that origin is cancelled. All HTML, JavaScript, Three.js, and licenses are local. The WebView2 environment disables background networking and uses a local user-data directory.

## Bridge

Native-to-JavaScript communication uses `PostWebMessageAsJson` with four small message forms:

- pointer: normalized `x`, `y`, and `present`;
- pause/resume: `paused`;
- rate hint: `fps`;
- diagnostic request: `probe`.

JavaScript-to-native communication is limited to string readiness and diagnostic messages through `window.chrome.webview.postMessage`. The WebView receives no forwarded mouse or keyboard input.

## Recovery

A hidden Aquarium-owned top-level control window survives Explorer. Explorer loss is detected from the registered `TaskbarCreated` broadcast, invalid desktop HWNDs, invalid parent/Z-order, or an invalid renderer host during a defensive 1 Hz health check. Recovery closes stale WebView2/controller/composition resources, waits for the replacement shell hierarchy, rediscovers every handle, recreates the host and WebView2 visual tree in-process, and restores pause/rate/cursor state.

Retry delay grows from 250 ms through 500 ms, 1 s, 2 s, and caps at 5 s. Attempts and HRESULTs are logged. There is no busy polling and no normal process restart recovery path.

## Experimental gates

1. Revalidate the native D3D baseline from `00e0b58`.
2. Prove local Canvas/WebGL content through CompositionController beneath real icons. Stop and report if it cannot compose.
3. Add locally bundled Three.js as a separate rendering delta.
4. Reproduce Explorer loss and prove three consecutive in-process recoveries.
5. Run the complete acceptance set, including ten minutes continuous operation and clean process teardown.

## Dependencies

- Existing Visual Studio Build Tools 2026 and Windows SDK.
- Installed Evergreen WebView2 Runtime 153.0.4234.48.
- Native `Microsoft.Web.WebView2` SDK 1.0.3405.78 from the official NuGet package: headers, x64 loader import library/DLL, license, and notice only. No .NET SDK.
- A pinned local Three.js distribution and its MIT license only after the composition gate succeeds.

