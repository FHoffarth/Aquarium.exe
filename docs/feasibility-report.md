# Aquarium.exe Windows wallpaper feasibility report

- Date: 2026-09-21
- Test machine: Windows 11 Pro 25H2, build **26200.9457**, 1920×1080, Intel(R) UHD Graphics
- Reference inspected: `chaseleantj/desktop-habitats@e6ea239e92bb04dcd3953f80758aef61c72b2146`
- Known-good control: Lively 2.2.1.0 x64 desktop-native (`6860a4093fc50058c4815908658a4391c4449935`)

## Spike #3 superseding result

**GO WITH CONDITIONS for a real Aquarium.exe MVP.** The requested production-shaped chain is now demonstrated on the test machine:

```text
native Win32 host
  -> DirectComposition target/visual on Aquarium renderer child HWND
  -> WebView2 CompositionController
  -> local https://aquarium.local/ habitat
  -> locally bundled Three.js 0.186.0 / WebGL2
```

All Sprint #3 gates A–H passed in the final configuration: the local habitat is visible and animated below Explorer icons; three primitive fish move and react to the native global cursor bridge; icon and blank-desktop hit-testing remains with Explorer; pause/resume stops and restarts WebGL rendering; runtime content has no network dependency; three consecutive Explorer restarts recovered in-process; and clean exit left no Aquarium-owned WebView2 processes. This result supersedes Spike #2's Explorer-recovery blocker while preserving the older evidence below.

The recommendation remains conditional because the working input isolation uses a split not explicitly promised by WebView2's contract: the CompositionController parent is Aquarium's hidden offscreen owner, while its `RootVisualTarget` is in the DirectComposition tree attached to the full-screen renderer child. Using the renderer child as controller parent visibly rendered but caused WebView2's internal `Chrome_RenderWidgetHostHWND` to win desktop hit-testing. The split configuration rendered correctly and returned Explorer `SysListView32` for both icons and blank desktop, but it needs cross-version validation. Short diagnostic sampling also showed a high WebView2 footprint and approximately 26–44% GPU-engine utilization while rendering this unoptimized full-screen probe.

### Exact Spike #3 architecture

1. A stable hidden Aquarium-owned top-level HWND remains alive independently of Explorer. It receives the registered control message and `TaskbarCreated` broadcast and is also the CompositionController parent/input reference.
2. Each render session rediscovers `Progman`, direct-child `SHELLDLL_DefView`, its `SysListView32`, and the full-screen `WorkerW` below DefView. The known-good raised-desktop attachment is unchanged: `SHELLDLL_DefView > Aquarium host > WorkerW`.
3. A transient Aquarium host and renderer child are created and shown as ordinary Aquarium-owned windows first. The host creates a hardware D3D11 BGRA device only for DirectComposition, then creates a target on the renderer child plus root and WebView visuals.
4. `ICoreWebView2Environment3::CreateCoreWebView2CompositionController` creates the visual-hosting controller. `ICoreWebView2CompositionController::put_RootVisualTarget` connects it to the WebView visual; `IDCompositionDevice::Commit` publishes the tree.
5. Only after `habitat-ready:three-webgl2` is received is the outer host made layered/nonactivating, converted to a child, parented to Progman, and ordered below DefView and above WorkerW. There is no conventional HWND WebView2, top-level-bottom, or overlay fallback.
6. `SetVirtualHostNameToFolderMapping` exposes only the bundled `habitat/` directory at `https://aquarium.local/`. External top-level navigation is cancelled. WebView2 starts with background networking, component updates, and proxy use disabled.
7. Native code polls `GetCursorPos` at roughly 18–25 Hz, converts to normalized renderer coordinates, and sends JSON with `PostWebMessageAsJson`. It also sends pause/resume, FPS/rate, and probe messages. JavaScript returns readiness and small diagnostics only. No mouse/keyboard hook, capture, or input forwarding exists.
8. The habitat owns all fish state and rendering. It explicitly requests WebGL2, constructs three original fish from sphere/cone primitives, animates them autonomously, and accelerates them away from the native cursor.

### Explorer recovery

Recovery uses both the `TaskbarCreated` broadcast and a defensive 1 Hz validation of all relevant handles, parent relationships, renderer ownership, and raised-desktop Z-order. On loss, the host closes the WebView2 controller, releases its DComp/D3D resources, destroys stale render HWNDs, and retains only the stable hidden owner. It retries shell discovery with 250 ms, 500 ms, 1 s, 2 s, then capped 5 s delays. Every successful attempt creates a new generation; stale async callbacks are ignored. The Aquarium process is never relaunched as the normal recovery path.

On the final recovery run, Aquarium remained PID **7580** while Explorer changed **23848 → 5840 → 1320 → 14788** across three forced restarts. Each cycle rediscovered new shell handles, received a fresh `habitat-ready:three-webgl2`, restored `DefView > Aquarium > WorkerW`, and logged `RECOVERY SUCCESS`. Late `TaskbarCreated` delivery caused two deliberately discarded/rebuilt sessions, so the final healthy lifecycle generation was 15; the generation guards handled this without changing the process. The third recovered desktop is shown in [`spike3-recovery-3.png`](../spike3-recovery-3.png), and the complete run is retained in [`docs/evidence/spike3-final-run.log`](evidence/spike3-final-run.log) (SHA-256 `15B55F575659EF4056EFE073B6A8F9297F2D2B1F3E420AB2751131FAF651E96D`).

### Windows APIs/techniques added in Spike #3

- WebView2 environment/controller: `CreateCoreWebView2EnvironmentWithOptions`, `ICoreWebView2Environment3::CreateCoreWebView2CompositionController`, `ICoreWebView2Controller`, and `ICoreWebView2CompositionController::put_RootVisualTarget`.
- Local content/bridge: `ICoreWebView2_3::SetVirtualHostNameToFolderMapping`, `Navigate`, `PostWebMessageAsJson`, `WebMessageReceived`, `NavigationStarting`, and `ProcessFailed`.
- DirectComposition ownership remains native: `D3D11CreateDevice` with BGRA support, `DCompositionCreateDevice`, `CreateTargetForHwnd`, `CreateVisual`, `AddVisual`, `SetRoot`, and `Commit`.
- Recovery: registered `TaskbarCreated`, `IsWindow`, parent/Z-order validation, `MsgWaitForMultipleObjectsEx`, lifecycle generations, and capped retry backoff.
- Desktop input proof: `WindowFromPoint`, Explorer `SysListView32`, host `WM_NCHITTEST -> HTTRANSPARENT`, `WM_MOUSEACTIVATE -> MA_NOACTIVATE`; no WebView2 `SendMouseInput`, hook, or capture.

### Spike #3 tests actually executed

- Built native x64 with `/W4 /WX`; fish logic, host lifecycle/backoff/bridge policy, and installed WebView2 runtime probes passed.
- Confirmed Evergreen WebView2 Runtime **153.0.4234.48** and native SDK **1.0.3405.78** on Windows 11 Pro 25H2 build **26200.9457**.
- Revalidated the exact Spike #2 D3D baseline before replacing the content layer.
- Proved a local Canvas CompositionController gate before adding Three.js. The first Canvas desktop capture is [`spike3-webview2-canvas-desktop.png`](../spike3-webview2-canvas-desktop.png).
- Proved local Three.js/WebGL2 with three animated primitive fish beneath real icons: [`spike3-threejs-desktop.png`](../spike3-threejs-desktop.png).
- At icon and blank coordinates, `WindowFromPoint` returned Explorer `SysListView32`; real single clicks visibly selected icons. Aquarium host and renderer returned `HTTRANSPARENT` and did not become the active desktop surface.
- Native cursor proximity increased JavaScript reaction counts from 0 into the hundreds during the extended run.
- `--pause` produced `paused=true`, stopped habitat FPS messages, and measured 0.00% Aquarium WebView2 GPU-engine utilization during a two-sample pause; `--resume` restored rendering.
- Win+D after the third recovery left the habitat visible under icons. At `(180,130)` and `(1500,500)`, `WindowFromPoint` returned Explorer `SysListView32` PID **14788**. Clicking the icon changed `LVM_GETSELECTEDCOUNT` to 1; clicking blank desktop changed it to 0; foreground remained Explorer `Progman`.
- Three consecutive forced Explorer restarts recovered without changing Aquarium PID **7580**. Explorer changed **23848 → 5840 → 1320 → 14788**; final-run timestamps and handle diagnostics are in the committed log.
- The final process ran from **14:30:55 to 14:49:32** (18 minutes 37 seconds). After the post-change resume at 14:31:49, it rendered continuously for **14 minutes 45 seconds** before the deliberate final pause test, spanning all three Explorer restarts; this exceeds the ten-minute gate.
- The post-recovery pause from 14:46:34 produced no habitat FPS messages and two GPU samples of 0.00%; resume at 14:47:18 restored about 42–43 FPS.
- Clean `--quit` tracked PIDs `5820, 7580, 12364, 18712, 21824, 25364, 27348, 28484`; ten seconds later none remained.

The Codex native-computer-control surface was unavailable, so narrowly scoped Win32 input and `CopyFromScreen` were used for the actual Windows visibility/input checks. This limitation does not convert screenshots or observed Explorer hit-testing into assumptions; they were executed on the stated machine.

### Spike #3 diagnostic performance

- Habitat diagnostics generally reported about **38–43 rendered FPS** and **9 draw calls** at 1920×1080, target 60 FPS.
- Native cursor bridge diagnostics generally reported **18–25 Hz**.
- Native-host normalized CPU samples were usually **0.0–0.5%** outside initialization/recovery.
- A final five-second whole Aquarium/WebView2 process-tree sample consumed **1.109 CPU-seconds**, or about **5.53% normalized across four logical processors**. An earlier sample measured 5.94%.
- After three recoveries, the active process tree contained Aquarium, one WebView2 browser group (browser, GPU, renderer, network, storage, crash handler), and the console host: **504.2 MB aggregate working set** and **311 MB aggregate private bytes**. This includes shared WebView2 pages and is not a production benchmark, but is heavy for a lightweight utility.
- One final three-sample GPU Engine pass attributed to the WebView2 GPU process reported **26.03–27.27%** summed engine utilization while rendering; an earlier pass on the same build reported **40.09–44.05%**. A paused two-sample check reported **0.00%**. These counters are variable diagnostic observations, but the cost is an obvious optimization/hardening concern.
- `Get-NetTCPConnection` found **zero TCP connections** owned by the eight-process Aquarium/WebView2 tree during the final run.

### Spike #3 dependencies and reuse

- Microsoft WebView2 SDK 1.0.3405.78: native headers and x64 loader only, from the official NuGet package, with license/notice and hashes recorded in `THIRD_PARTY_NOTICES.md`.
- Three.js 0.186.0: `three.module.js`, required `three.core.js`, and MIT license only, from the official npm package, with integrity/hashes recorded locally.
- No code, shaders, fish, models, textures, or assets were copied from `desktop-habitats` or Lively. Both remain architectural/behavioral references only.
- No .NET SDK, account, analytics, telemetry, cloud service, CDN, or runtime network server was introduced.

### Remaining conditions

- Validate the offscreen CompositionController-parent split across supported Evergreen WebView2 and retail Windows 11 versions; it is the largest architectural risk.
- Reduce GPU and memory cost before calling the product lightweight; test frame-rate caps, render scale, WebView2 process options, and real habitat workloads.
- Test multiple monitors/mixed DPI, virtual desktops, lock/display-off, sleep/wake, RDP, HDR, display reconfiguration, and competing wallpaper tools.
- Treat WorkerW/Progman classes, message `0x052C`, and shell Z-order as undocumented compatibility behavior with diagnostics and clean failure.
- Add the proposed power/session policy only after this runtime boundary is retained: 60 FPS on AC, lower FPS on battery, reduce/stop when materially covered, stop on lock/display-off, and sample cursor no faster than useful.

## Spike #2 historical decision (superseded by Spike #3)

**GO WITH CONDITIONS for an Aquarium.exe MVP.**

Spike #2 achieved the primary acceptance test on this exact Windows build: a native D3D11 fish was visibly animated beneath Explorer's desktop icons; Explorer retained icon and blank-desktop input; the fish reacted to global cursor proximity; and pause/resume stopped and restarted presentation.

The first successful delta was replacing the legacy DXGI HWND swap chain with a composition swap chain (`CreateSwapChainForComposition`) displayed through DirectComposition. The renderer, fish simulation, desktop topology, and input model did not otherwise change between the final failed trial and the first successful trial.

This supersedes, but does not erase, Spike #1's original NO-GO. Spike #1 correctly recorded that a classic `D3D11CreateDeviceAndSwapChain` HWND surface was not composed in the raised desktop on this machine. The Lively control proved the shell topology itself viable; Spike #2 then isolated the Aquarium gap to its presentation path.

Conditions before an MVP commitment:

- implement automatic Explorer-restart detection and recreation of all desktop-bound HWND/DirectComposition resources;
- test multiple monitors, mixed DPI, virtual desktops, lock/display-off, sleep/wake, RDP, HDR, and current retail Windows 11 builds;
- treat Progman/WorkerW attachment as an undocumented compatibility layer with diagnostics and clean failure, not a Windows contract;
- retain a compositor-backed renderer path. Do not regress to the failed legacy HWND swap chain.

## Reference architecture

`desktop-habitats` separates scene and platform host cleanly:

- `scenes/riverscape/` is a platform-neutral Three.js/WebGL2 aquarium. Its JavaScript exposes a small host-facing control surface and owns simulation/rendering.
- `src/frame-loop.js` owns frame scheduling and cancels callbacks when paused, hidden, or configured for zero rate.
- `wallpaper/Wallpaper.swift` is only the macOS host adapter. It owns desktop placement, one `WKWebView` per display, global cursor sampling, power/session policy, and native-to-page messages.
- Bundled content is local. The architecture does not require an account, analytics, cloud service, or runtime network server.

That separation is the reusable idea. No Swift code was ported, and no substantial source or assets were copied.

## Lively control and implementation-gap evidence

Lively 2.2.1.0 was run on the same machine before Aquarium testing. Its WebGL wallpaper was visibly animated beneath Explorer icons and the icons remained interactive. Its raised-desktop hierarchy was:

```text
Progman
  SHELLDLL_DefView
  Lively host                style=0x56010000 ex=0x8090080
    Lively renderer child    style=0x56010000 ex=0x20
      Chrome/WebView2 children
  WorkerW
```

The Lively host also had `CS_DBLCLKS`, a hidden WinForms owner, `WS_EX_LAYERED` with alpha 255, and the exact child Z-order above. Inspection of the tagged Lively source showed the same raised-desktop sequence: initialize/show the wallpaper, add child/layered styles, set alpha 255, parent to Progman, order below `SHELLDLL_DefView`, and retain WorkerW beneath it. No Lively source was copied.

## Experiments and first successful delta

Each trial changed one architectural variable relative to the preceding trial. A top-level screenshot/capture confirmed the fish rendered before every desktop attachment attempt.

| Experiment | Isolated delta | Result beneath icons |
|---|---|---|
| Spike #1 baseline | Legacy HWND swap chain attached directly to the raised desktop | Not visible |
| A | Initialize/present while an ordinary top-level popup; only then apply desktop styles, layer alpha, child conversion, parenting, and Z-order | Not visible |
| B | Separate Aquarium host HWND and D3D11 renderer child HWND | Not visible |
| C1 | Remove `WS_EX_TRANSPARENT` from outer host | Not visible |
| C2 | Add `WS_EX_TRANSPARENT` to renderer child | Not visible |
| C3 | Add decoded `WS_EX_CONTROLPARENT` to host | Not visible |
| C4 | Add `WS_TABSTOP` to host | Not visible |
| C5 | Add `WS_TABSTOP` to renderer child; host/child standard and extended styles now matched Lively | Not visible |
| C6 | Add Lively-matching `CS_DBLCLKS` class styles | Not visible |
| C7 | Add a hidden owner matching Lively's ownership shape (`style=0x4C00000`, `ex=0x180`) | Not visible |
| **D** | Keep C7's HWND topology and D3D11 drawing, but use `CreateSwapChainForComposition` + DirectComposition instead of a legacy HWND swap chain | **Visible; first success** |

Two additional isolation checks strengthened the negative result before D:

- GDI `FillRect` calls against both the host and child returned success but remained invisible in the desktop capture.
- C5's host/child window styles were bit-for-bit equal to Lively's relevant pair, yet Aquarium remained invisible.

This makes style cloning an implausible explanation. The observed implementation gap was the presentation/composition path.

## Exact successful architecture

The final spike is a single dependency-free native Win32 process:

1. Discover `Progman`, its direct `SHELLDLL_DefView` child, and a full-screen `WorkerW` below it.
2. On the detected raised desktop, request WorkerW only if missing by sending Explorer's undocumented `0x052C` message with `wParam=0xD`, `lParam=0x1`.
3. Create a hidden owner, a borderless top-level Aquarium host, and a renderer child. Initialize D3D11 and present once while the host is still an ordinary Aquarium-owned top-level window.
4. Apply `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_CONTROLPARENT | WS_EX_LAYERED` and constant alpha 255 to the host. Convert it to a child and parent it to Progman.
5. Establish direct-child Z-order `SHELLDLL_DefView > Aquarium host > WorkerW`. No ordinary `HWND_BOTTOM` fallback exists.
6. Create a hardware D3D11 device with BGRA support. Create an `IDXGISwapChain1` using `CreateSwapChainForComposition`, flip sequential presentation, BGRA8, premultiplied alpha, and two buffers.
7. Bind that swap chain to the renderer child with `DCompositionCreateDevice`, `CreateTargetForHwnd`, an `IDCompositionVisual`, and `Commit`.
8. Render the same procedural fish and solid aquarium background through the existing shaders and dynamic vertex buffer.
9. Poll `GetCursorPos` on render frames, convert with `ScreenToClient`, and update fish proximity response. Normal mouse input is never forwarded to Aquarium.
10. Handle `--pause`, `--resume`, `--probe`, and `--quit` through a registered window message. Paused rendering blocks in `WaitMessage` and issues no presents.

Final pre-restart hierarchy:

```text
Progman 0x1010A
  z=0 SHELLDLL_DefView 0x1010E
  z=1 AquariumSpike.RenderWindow.v1 0x190712 style=0x56010000 ex=0x8090080
        AquariumSpike.RendererChild.v1 0x10062E style=0x56010000 ex=0x20
  z=2 WorkerW 0x160472
```

After Explorer was restarted and Aquarium was relaunched, the new handles and the same order were discovered correctly:

```text
Progman 0x202A8
  z=0 SHELLDLL_DefView 0x202B4
  z=1 AquariumSpike.RenderWindow.v1 0x70644
  z=2 WorkerW 0x80246
```

## Actually tested on Windows

### Passed

- Native x64 warning-as-error build and fish-logic unit test.
- Hardware D3D11 initialization on Intel UHD Graphics, vendor `0x8086`, device `0x46d1`, feature level 11.1.
- Actual screen capture after other top-level windows were minimized showed the D3D11 fish and aquarium background beneath normal Explorer desktop icons: [`spike2-experiment-d-screen.png`](../spike2-experiment-d-screen.png).
- Animation continued for 273.6 seconds before the Explorer restart test; frame and fish-position logs continued changing.
- Cursor response: immediately before positioning the global cursor at the fish, `reactions=0`; afterward `reactions=1` and horizontal velocity changed from `-85.0` to `-467.8`.
- Pause/resume: the paused frame count remained exactly `3356` across 3.05 seconds, then advanced to `3469` after resume.
- Explorer icon input: an actual single click hit `SysListView32`, changed Explorer's selected count to 1, and left `Progman` (Explorer PID 6344) foreground.
- Blank desktop input: an actual blank-area click also hit `SysListView32`, cleared the selection to 0, and left Progman foreground.
- Both Aquarium HWNDs returned `HTTRANSPARENT`; Aquarium never became the active desktop surface.
- Show Desktop via the shell command left rendering alive: frames advanced `8295 -> 8384 -> 8427` before/during/after the transition.
- Manual recovery after Explorer restart: terminating the stale Aquarium process and relaunching the unchanged executable rediscovered the new Progman/WorkerW topology and visibly rendered again: [`spike2-experiment-d-after-explorer-relaunch.png`](../spike2-experiment-d-after-explorer-relaunch.png).
- No application network, account, analytics, telemetry, cloud, installer, settings, WebView2, or Three.js dependency was added.

### Failed or incomplete

- **Automatic Explorer restart recovery failed.** Explorer destroyed the old desktop-bound Aquarium host. The Aquarium process continued presenting to stale composition resources, its control window was no longer discoverable, and it did not bind to the new Progman automatically.
- A stable 60 FPS was not observed. Five-second log intervals during the visible run were usually about 35-43 presents/second on this machine.
- The native Computer Use surface was unavailable in this Codex session. Visibility was therefore verified by both direct Progman capture and an actual `CopyFromScreen` capture after programmatically minimizing other top-level windows; input was exercised with narrowly scoped Win32 clicks and verified through Explorer's ListView state.

### Not tested

- Multiple monitors, mixed DPI, virtual desktops, battery policy, lock/display-off, sleep/wake, RDP, HDR, display reconfiguration, full-screen games, and long-duration/battery drain.
- WebView2 or Three.js integration.
- Automatic Explorer recovery, because no recovery code exists in this minimal spike.

## CPU/GPU observations

These are lightweight observations, not benchmarks:

- Running process CPU logs were typically about 0.5-1.9% normalized across the machine's logical processors.
- The successful visible configuration presented roughly 35-43 FPS in most five-second intervals, below the intended future 60 FPS target.
- A five-sample Windows GPU Engine counter pass for the Aquarium PID reported approximately 1.32% mean and 1.49% peak summed utilization across active engines. Several unrelated/invalid counter instances produced warnings and were excluded.
- While paused, the frame count did not advance and the loop blocked for messages.

## Windows APIs and techniques used

- Desktop discovery: `EnumWindows`, `FindWindow`, `FindWindowEx`, `GetWindow`, `GetWindowLongPtr`, `GetWindowRect`.
- Undocumented shell request: `SendMessageTimeout(Progman, 0x052C, 0xD, 0x1)`.
- Attachment/Z-order: `SetWindowLongPtr`, `SetLayeredWindowAttributes`, `SetParent`, `SetWindowPos`.
- Input pass-through: `WS_EX_NOACTIVATE`, `WS_EX_TRANSPARENT` on the renderer child, `WM_NCHITTEST -> HTTRANSPARENT`, `WM_MOUSEACTIVATE -> MA_NOACTIVATE`.
- Cursor: `GetCursorPos`, `ScreenToClient`; no hook, capture, or raw-input ownership.
- Rendering: `D3D11CreateDevice`, `IDXGIFactory2::CreateSwapChainForComposition`, `DCompositionCreateDevice`, `IDCompositionDevice::CreateTargetForHwnd`, `IDCompositionVisual::SetContent`, `Commit`, `IDXGISwapChain1::Present`.
- Control/scheduling: `RegisterWindowMessage`, `PostMessage`, `WaitMessage`, `MsgWaitForMultipleObjectsEx`.

Relevant platform references: [IDXGIFactory2::CreateSwapChainForComposition](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_2/nf-dxgi1_2-idxgifactory2-createswapchainforcomposition), [DirectComposition bitmap surfaces](https://learn.microsoft.com/en-us/windows/win32/directcomp/bitmap-surfaces), [DXGI swap effects](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ne-dxgi-dxgi_swap_effect), and [SetParent](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setparent).

## Risks and undocumented behavior

- `0x052C`, its arguments, WorkerW creation, shell class names, and the Progman child order are undocumented implementation details.
- `SetParent` is documented, but inserting an application HWND into Explorer's private desktop tree is not a supported live-wallpaper API.
- The raised-desktop mode depends on `Progman` having `WS_EX_NOREDIRECTIONBITMAP` and `SHELLDLL_DefView` being layered. Servicing updates may alter this behavior.
- Explorer destroys the bound HWND hierarchy on restart. Production code must detect this and recreate the host, renderer child, composition target, and swap chain.
- Another wallpaper/customization product can compete for WorkerW/Z-order or alter the same shell tree.
- There is no documented Windows API equivalent to AppKit's desktop window level for arbitrary live GPU content. `IDesktopWallpaper` manages static images only.
- DirectComposition solved this machine's composition gap, but cross-build reliability remains to be established.

## Future WebView2 + Three.js architecture

**Yes: WebView2 + Three.js remains the recommended production renderer architecture**, now with stronger evidence than after Spike #1.

The successful native DirectComposition experiment validates the class of compositor-backed presentation used by modern embedded web content. It does not prove WebView2 itself on the desktop layer, because WebView2 was not integrated in this spike.

Recommended future boundary:

- native Win32 host: desktop discovery/attachment, one host per display, Explorer recovery, cursor sampling, power/session/display notifications, and frame-rate policy;
- WebView2 composition controller per display, kept non-interactive for ordinary desktop input;
- bundled Three.js and assets mapped to a private virtual HTTPS host, with external navigation and network requests denied;
- a minimal host bridge for cursor coordinates, pause/resume, rate, power, visibility, and resize;
- JavaScript scheduling that fully cancels animation callbacks at 0 FPS.

## Proposed power-management path (not tested)

- Visible/on AC: target 60 FPS.
- Battery: reduce to about 30 FPS and optionally lower render scale/expensive effects.
- Materially covered: estimate coverage at low frequency and reduce to 20 FPS or stop when nearly fully covered; corroborate with DXGI occlusion signals where applicable.
- Lock/display off: listen for session and display-status notifications and force 0 FPS.
- AC/battery: use power-setting notifications rather than frequent polling.
- Cursor: sample no faster than `min(render FPS, 30 Hz)` and stop entirely at 0 FPS.

## Files changed or created in Spike #2

- `src/main.cpp`: initialization-order experiment, nested renderer HWND, decoded style/owner diagnostics, DirectComposition presentation, and detailed topology logging.
- `build.ps1`: link `dcomp.lib`.
- `docs/implementation-plan.md`: Spike #2 experimental plan.
- `docs/feasibility-report.md`: this superseding report.
- `README.md`: updated observed result and controls.
- Evidence images retained: `lively-desktop-observation.png`, `spike2-experiment-a-top-level.png`, `spike2-experiment-c7-progman.png`, `spike2-experiment-d-screen.png`, and `spike2-experiment-d-after-explorer-relaunch.png`.

## Licensing and reuse

- `desktop-habitats` is MIT licensed; its bundled Three.js is MIT and its listed textures are CC0.
- No source, shader, asset, texture, or fish model from `desktop-habitats` was copied.
- Lively is used only as an installed behavioral control and source-inspection reference. No Lively source or assets were copied.
- The Win32 host, D3D11 fish/shaders, tests, DirectComposition integration, and documentation in this repository were written for this spike.

## Spike #2 historical final recommendation (superseded)

**GO WITH CONDITIONS.** The core Windows 11 experience is demonstrably feasible on build 26200.9457 when Aquarium uses compositor-backed D3D11 presentation. The MVP should proceed only if a short hardening phase first proves automatic Explorer recovery and acceptable behavior across representative Windows 11 builds and display configurations.
