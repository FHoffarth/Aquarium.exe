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

The host creates a D3D11 BGRA device only to establish the proven DirectComposition device. It creates an `IDCompositionTarget` for the Aquarium renderer child, a root visual, and a WebView visual. `ICoreWebView2Environment3::CreateCoreWebView2CompositionController` creates the visual-hosting WebView2 controller; `ICoreWebView2CompositionController::put_RootVisualTarget` connects WebView2 to the WebView visual. The host commits the composition tree after binding.

The first Windows run exposed one important input-host detail. Passing the full-screen renderer child as `CreateCoreWebView2CompositionController`'s parent made WebView2's internal `Chrome_RenderWidgetHostHWND` win hit-testing and blocked Explorer. Passing Aquarium's hidden, offscreen owner HWND as the controller parent while keeping the DirectComposition target on the renderer child preserved the rendered visual and made `WindowFromPoint` return Explorer's `SysListView32` on both icons and blank desktop. A real click selected an icon. No mouse input is forwarded to WebView2.

This split is the smallest observed working configuration, but it is a stability risk: Microsoft documents the parent HWND as the window in which the app connects the visual tree and says it receives pointer input. The spike deliberately uses a different visible DirectComposition target and input parent to keep WebView2 out of desktop hit-testing. Production work must validate this across supported WebView2 Runtime/Windows versions or replace it with a better-supported isolation mechanism.

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

### Canvas gate result (2026-09-21)

- **Tested:** local `habitat/index.html` and `habitat/habitat.js` loaded through `https://aquarium.local/`; the habitat reported `habitat-ready:canvas` before desktop attachment.
- **Tested:** animated Canvas content remained visibly composed under real Explorer icons after attachment in `SHELLDLL_DefView > Aquarium > WorkerW` order.
- **Tested:** with the offscreen controller parent, icon and blank-desktop hit tests returned Explorer `SysListView32`; a synthetic single click visibly selected the Git Bash icon.
- **Failed control:** with the renderer child as controller parent, hit tests returned Aquarium's `msedgewebview2.exe` `Chrome_RenderWidgetHostHWND` and Explorer did not receive the click.
- **Evidence:** `spike3-webview2-canvas-desktop.png`, `spike3-webview2-atomic-icon-click.png`, and `bin/aquarium-spike.log` (runtime log is generated, not committed).

## Dependencies

- Existing Visual Studio Build Tools 2026 and Windows SDK.
- Installed Evergreen WebView2 Runtime 153.0.4234.48.
- Native `Microsoft.Web.WebView2` SDK 1.0.3405.78 from the official NuGet package: headers, x64 loader import library/DLL, license, and notice only. No .NET SDK.
- A pinned local Three.js distribution and its MIT license only after the composition gate succeeds.
