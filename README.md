# Aquarium.exe

A living aquarium for your Windows desktop.

**debother. — Small software for annoying problems.**

Aquarium.exe is under active development. The current repository contains the native Win32/WebView2 feasibility implementation; it is not yet a production release.

## Build and run

Requirements: Windows 11, Visual Studio C++ Build Tools, a Windows SDK, and the Evergreen WebView2 Runtime. The native WebView2 SDK and Three.js files needed to build/run the probe are already vendored with their licenses; no .NET SDK, npm install, CDN, or runtime network service is required.

```powershell
.\build.ps1
Start-Process .\bin\AquariumSpike.exe -WindowStyle Hidden
```

Control the running probe from PowerShell:

```powershell
.\bin\AquariumSpike.exe --probe
.\bin\AquariumSpike.exe --pause
.\bin\AquariumSpike.exe --resume
.\bin\AquariumSpike.exe --quit
```

Diagnostics are written to `bin/aquarium-spike.log`.

## Result on the tested machine

Spike #3 succeeded on Windows 11 Pro 25H2 build 26200.9457. A native DirectComposition host now displays a WebView2 CompositionController loading a local Three.js/WebGL2 habitat. Three primitive fish animate beneath Explorer icons, desktop input remains with Explorer, native cursor proximity affects the fish, and pause/resume stops and restarts WebGL rendering.

The same Aquarium process automatically recovered after three consecutive Explorer restarts by rebuilding its desktop-bound HWND, DirectComposition, and WebView2 resources. A normal `HWND_BOTTOM` or conventional interactive WebView fallback is intentionally absent.

See [the feasibility report](docs/feasibility-report.md) for exact evidence and the recommendation.
