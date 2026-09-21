# Aquarium.exe Windows wallpaper feasibility spike

1. Record the live Explorer `Progman` / `WorkerW` / `SHELLDLL_DefView` hierarchy and the Windows build.
2. Build one dependency-free Win32 executable with a D3D11 swap chain, one procedural fish, global cursor polling, pause/resume, and diagnostic logging.
3. Attach only through the desktop hierarchy. Detect the Windows 11 raised-desktop layout, attempt its WorkerW path, and fail explicitly if no valid below-icons host exists; do not substitute an ordinary bottom window.
4. Execute the probe on this machine and manually verify visibility beneath icons, normal icon selection/click/drag, cursor reaction, and pause/resume. Capture process/window/render counters and lightweight CPU/GPU observations where Windows exposes them.
5. Document the reference architecture, tested results, inferred behavior, WorkerW risks, WebView2/Three.js follow-on design, and licensing/reuse.

The implementation is throwaway spike code, not an application framework. No installer, settings, network access, copied assets, or product features.

## Spike #2: isolate the Lively implementation gap

Known-good control: Lively 2.2.1.0 visibly runs a WebGL wallpaper beneath Explorer icons on Windows 11 Pro 25H2 build 26200.9457 using the same raised-desktop topology. Spike #1's architectural NO-GO is therefore withdrawn; the remaining question is which Aquarium HWND/render-initialization detail prevents composition.

1. Preserve the existing renderer, fish logic, controls, and desktop discovery as the baseline. Stop Lively before Aquarium trials so the two hosts do not compete for the same desktop layer.
2. Experiment A changes only lifecycle order: create the popup without desktop styles, initialize D3D11 and present visibly while top-level, then apply layered/non-activating styles, convert to a child, reparent to `Progman`, and establish `SHELLDLL_DefView > Aquarium > WorkerW`.
3. If and only if A fails, Experiment B adds a separate child renderer HWND. Initialize D3D11 on that child before attaching the outer host; keep desktop attachment and hit-test behavior on the host.
4. If and only if B fails, Experiment C changes remaining decoded style differences one at a time and records each outcome.
5. Stop architectural changes at the first visible configuration. Verify animation, cursor reaction, Explorer input ownership, pause/resume, Show Desktop, several minutes of runtime, and Explorer restart/recovery.
6. Update the feasibility report with the Lively control, every attempted delta, raw diagnostics, and an evidence-based recommendation.
