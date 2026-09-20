# Aquarium.exe Windows wallpaper feasibility report

Date: 2026-09-20  
Test machine: Windows 11 Pro 10.0.26200, 1920×1080, Intel(R) UHD Graphics  
Reference repository revision inspected: `chaseleantj/desktop-habitats@e6ea239e92bb04dcd3953f80758aef61c72b2146`

## Decision

**NO-GO for a real Aquarium.exe MVP using the tested self-hosted WorkerW/Progman technique.**

The renderer and interaction model are viable. The essential host requirement is not: on this Windows 11 build, the shell accepted the expected raised-desktop HWND hierarchy but did not visibly composite either D3D11 or GDI content from that HWND. Shipping would therefore depend on undocumented shell behavior that failed on the target machine.

This is not a permanent rejection of the product concept. It is a stop condition for this hosting technique until a follow-up can demonstrate a supported or independently repeatable desktop-composition path across Windows 11 24H2/25H2 builds, Explorer restart, virtual desktops, and multiple monitors.

## Reference architecture inspected

`desktop-habitats` separates the aquarium from its macOS host cleanly:

- `scenes/riverscape/` is the platform-neutral Three.js/WebGL2 scene. `wallpaper.html` marks motion as host-controlled, and `src/main.js` exposes small host calls such as `habitatRate`, `habitatPower`, `habitatPointer`, and `habitatPointerOut`.
- `src/frame-loop.js` owns scheduling. A zero rate, pause, or hidden state cancels pending callbacks instead of continuing to render invisibly.
- `wallpaper/Wallpaper.swift` is a macOS adapter, not part of the scene. It creates one borderless `WKWebView` window per display at the AppKit desktop window level, sets `ignoresMouseEvents`, polls the global cursor, and injects synthetic pointer events into the page.
- The Swift controller owns display enumeration, power/session state, approximate coverage, pointer polling, menu commands, and the host-to-page bridge. Bundled content is served with a private URL scheme and a non-persistent data store.

That boundary is the useful reference: scene code owns rendering and simulation; the native host owns desktop placement, lifecycle, power, and global cursor data. No Swift code was ported.

## Exact spike architecture

The probe is one dependency-free Win32 process:

1. Discover `Progman`, its direct `SHELLDLL_DefView` child, and the full-screen `WorkerW` below it.
2. If needed, ask Explorer to create the raised-desktop WorkerW by sending undocumented message `0x052C` to `Progman` with `wParam=0xD`, `lParam=0x1`.
3. Create a borderless popup HWND, add `WS_CHILD`, `WS_EX_LAYERED`, `WS_EX_TRANSPARENT`, `WS_EX_NOACTIVATE`, and `WS_EX_TOOLWINDOW`, set constant alpha to 255, then call `SetParent`.
4. On the detected raised desktop, parent to `Progman` and place the HWND in child Z order `SHELLDLL_DefView > AquariumSpike > WorkerW`. A classic desktop path would parent to WorkerW.
5. Create a hardware-only D3D11 device and blt-model swap chain. Render a procedural fish over a solid background; no assets are loaded.
6. Poll `GetCursorPos` only on rendered frames. Convert screen coordinates to the render HWND and update the fish with proximity repulsion.
7. Accept `--pause`, `--resume`, `--probe`, and `--quit` through a registered window message. While paused, the loop blocks in `WaitMessage` and makes no present calls.

There is deliberately no ordinary `HWND_BOTTOM` fallback, installer, settings UI, WebView2 package, networking, telemetry, or persistence.

## Desktop diagnostics from build 26200

Initial raised-desktop structure:

```text
Progman hwnd=0x1010A style=0x96000000 ex=0x200080 rect=[0,0,1920,1080]
  SHELLDLL_DefView hwnd=0x1010E style=0x56010000 ex=0x80000
    SysListView32 hwnd=0x10110
```

`Progman` had `WS_EX_NOREDIRECTIONBITMAP`; `SHELLDLL_DefView` had `WS_EX_LAYERED`. The spawn request returned success and produced:

```text
SendMessageTimeout(0x052C, 0xD, 0x1): API return=1, message result=0, last error=0
WorkerW hwnd=0x160472 style=0x58000000 ex=0x0 rect=[0,0,1920,1080]
```

Final tested hierarchy, reported by `GetWindow(..., GW_CHILD/GW_HWNDNEXT)` in top-to-bottom order:

```text
z=0 SHELLDLL_DefView 0x1010E
z=1 AquariumSpike.RenderWindow.v1 0xF04FA
z=2 WorkerW 0x160472
```

The render HWND was visible, not DWM-cloaked, full-screen, constant-alpha 255, and parented to `Progman`. Its final styles were `style=0x56000000`, `ex=0x80800A0`. `WM_NCHITTEST` returned `HTTRANSPARENT`.

### Attachment variants actually attempted

- Direct `CreateWindowEx(WS_CHILD, WorkerW)` failed before D3D setup: null HWND with last error 0.
- Creating a popup first, converting it to a child, parenting it to `Progman`, and ordering it between DefView and WorkerW succeeded structurally.
- The D3D back buffer rendered correctly and could be captured directly from the render HWND, including the moving fish.
- A full desktop capture still showed the original static wallpaper. The D3D surface was not visible behind the icons.
- Pausing D3D and painting the attached HWND with GDI also remained invisible, isolating the failure to desktop composition rather than D3D rendering.
- Reparenting the live HWND from `Progman` to WorkerW did not make it visible.
- Removing `WS_EX_LAYERED` from the live WorkerW child did not make it visible.
- Removing `WS_EX_TRANSPARENT` in a separate run did not make it visible.

No attempt was reported as successful merely because `SetParent`, Z-order, or `Present` returned success.

## Behavior actually tested

### Worked

- Native x64 build with Visual Studio Build Tools; warning-as-error build completed.
- Hardware D3D11 device on `Intel(R) UHD Graphics`, vendor `0x8086`, device `0x46d1`, feature level 11.1.
- Procedural fish rendered in the swap-chain HWND capture.
- Global cursor reaction: with the cursor placed 45 pixels to the fish's right, reaction count increased and horizontal velocity changed from `+15.2` to `-480.0`, visibly representing flight away from the cursor.
- Pause: frame count stayed at `134` for 2.06 seconds across two probes.
- Resume: frame count then advanced from `134` to `217`.
- Desktop input routing: `WindowFromPoint` at the first icon and at both ends of a blank-area drag returned `SysListView32`, not the render HWND. A real single click changed the desktop ListView selected count from 0 to 1. A real blank-area drag gesture was delivered to the ListView. Icon repositioning was not attempted.
- `WM_NCHITTEST` on the render HWND returned `-1` (`HTTRANSPARENT`).
- No product runtime network calls, accounts, analytics, or cloud services exist.

### Failed

- Primary acceptance: the D3D fish was not visibly composited beneath the desktop icons.
- Therefore the complete combination “visible animation plus usable icons” was not achieved, even though icon interaction and rendering worked separately.
- A stable 60 FPS was not achieved in this off-screen/failed-composition state; five-second intervals were roughly 34–41 presented frames per second.

### Not tested

- Battery operation, display-off, lock/unlock, sleep/wake, substantial coverage, multiple monitors, mixed DPI, virtual desktops, Explorer restart/recovery, RDP, HDR, WebView2, or a real Three.js scene.
- Long-run stability and battery drain.

## CPU/GPU observations

These are lightweight samples, not benchmarks, and the rendered surface was not visible on the desktop:

- 5.02-second running sample: 0.312 process CPU seconds, 1.56% normalized CPU on four logical processors.
- Working set: approximately 48 MB.
- One Windows `GPU Engine` performance-counter sample for the process's 3D engine: 7.01%.
- Render log: approximately 34–41 presents per second in steady five-second intervals.
- Paused rendering produced no additional frames; the loop blocked pending a message.

## Windows APIs and techniques used

- Shell/window discovery: `FindWindow`, `FindWindowEx`, `EnumWindows`, `GetWindow`, `GetWindowLongPtr`, `GetWindowRect`.
- Undocumented shell request: `SendMessageTimeout(Progman, 0x052C, 0xD, 0x1)`.
- Attachment and ordering: `SetWindowLongPtr`, `SetParent`, `SetWindowPos`, `SetLayeredWindowAttributes`.
- Click-through/non-activation: `WS_EX_TRANSPARENT`, `WS_EX_NOACTIVATE`, `WM_NCHITTEST -> HTTRANSPARENT`, `WM_MOUSEACTIVATE -> MA_NOACTIVATE`.
- Cursor: `GetCursorPos`, `ScreenToClient`; no hooks or raw input.
- Rendering: `D3D11CreateDeviceAndSwapChain`, dynamic vertex buffer, runtime HLSL compilation, `IDXGISwapChain::Present`.
- Programmatic control: `RegisterWindowMessage`, `PostMessage`, `WaitMessage`.

## Risks and undocumented dependencies

- `0x052C`, its arguments, WorkerW creation, class names, and shell child order are not documented contracts. Explorer can change them in servicing updates.
- `SetParent` itself is documented, but reparenting an application HWND into Explorer's private desktop tree is not a supported wallpaper API. Cross-process DPI-awareness resets are explicitly documented behavior.
- A successful HWND relationship did not imply successful DWM composition on the tested build.
- Explorer or another desktop customization tool can destroy/recreate WorkerW or change Z-order.
- An always-on-bottom top-level popup can look convincing but is not equivalent: it can participate incorrectly in Show Desktop, virtual desktops, focus/Z-order, and shell transitions. It was intentionally not accepted or implemented as fallback.
- There is no documented Windows API for hosting an arbitrary live GPU surface as the system wallpaper. `IDesktopWallpaper` manages static wallpaper images, not application surfaces.

## Future WebView2 + Three.js architecture

WebView2 + Three.js remains the recommended **renderer architecture**, but it does not solve the failed outer desktop-host problem.

If a reliable host mechanism is first established:

- Keep a small native Win32 host responsible for display topology, desktop attachment, cursor polling, power/session notifications, coverage policy, and recovery after Explorer restart.
- Host one WebView2 controller per display. Map bundled scene files to a reserved HTTPS virtual host with `SetVirtualHostNameToFolderMapping`; no local HTTP server or network access is needed.
- Bundle Three.js and every scene asset. Reject or cancel navigation outside the virtual origin and expose only a tiny host bridge.
- Send cursor coordinates and state changes to JavaScript; do not make the WebView interactive or forward normal clicks.
- Preserve scene APIs equivalent to `setRate`, `setPower`, `pointerMove`, `pointerLeave`, and `pause`. The JavaScript frame loop must fully cancel scheduling at 0 FPS.
- A composition-controller experiment is worth evaluating because WebView2 can expose a DirectComposition visual, but it still needs a desktop composition target that Windows actually displays beneath DefView.

The installed WebView2 Runtime on this machine was `153.0.4234.48`. It was not used by this spike.

## Proposed power-management path

This section is architectural, not tested behavior:

- **Visible/on AC:** host rate 60 FPS.
- **On battery:** 30 FPS; optionally lower render scale/shadow frequency inside Three.js.
- **Partially covered:** estimate visible area at about 1 Hz from ordinary top-level window rectangles; use 20 FPS when materially exposed and 0 when almost entirely covered. Treat this as a heuristic and test transparent, cloaked, virtual-desktop, and full-screen windows.
- **Entirely occluded:** use DXGI occlusion status as an additional full-occlusion signal, not as a partial-coverage estimator.
- **Lock/display off:** register for `WM_WTSSESSION_CHANGE` lock/unlock and power-setting notifications such as `GUID_SESSION_DISPLAY_STATUS`; force 0 FPS while inactive.
- **AC/battery:** register for `GUID_ACDC_POWER_SOURCE`, avoiding frequent polling.
- **Cursor:** sample at `min(render FPS, 30 Hz)` and stop sampling at 0 FPS. Send only changed coordinates.

## Licensing and reuse

- `desktop-habitats` is MIT licensed; its bundled Three.js is also MIT, and its listed textures are CC0.
- No source code, shader, asset, texture, or fish model from `desktop-habitats` was copied into this repository.
- The spike uses only architectural ideas visible in the reference: renderer/host separation, global cursor injection, and explicit frame-rate control.
- The D3D fish, shaders, Win32 host, tests, and documentation here were written for this spike.
- Lively and AereReact were inspected only to understand contemporary Windows techniques and failures; no material was copied from either project.

