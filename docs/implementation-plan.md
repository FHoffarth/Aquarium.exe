# Aquarium.exe Windows wallpaper feasibility spike

1. Record the live Explorer `Progman` / `WorkerW` / `SHELLDLL_DefView` hierarchy and the Windows build.
2. Build one dependency-free Win32 executable with a D3D11 swap chain, one procedural fish, global cursor polling, pause/resume, and diagnostic logging.
3. Attach only through the desktop hierarchy. Detect the Windows 11 raised-desktop layout, attempt its WorkerW path, and fail explicitly if no valid below-icons host exists; do not substitute an ordinary bottom window.
4. Execute the probe on this machine and manually verify visibility beneath icons, normal icon selection/click/drag, cursor reaction, and pause/resume. Capture process/window/render counters and lightweight CPU/GPU observations where Windows exposes them.
5. Document the reference architecture, tested results, inferred behavior, WorkerW risks, WebView2/Three.js follow-on design, and licensing/reuse.

The implementation is throwaway spike code, not an application framework. No installer, settings, network access, copied assets, or product features.
