# Aquarium.exe

A living aquarium for your Windows desktop.

**debother. — Small software for annoying problems.**

Aquarium.exe is under active development. The current repository contains the proven native Win32/WebView2 wallpaper host and the first procedural habitat foundation; it is not yet a production release.

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

## Optional browser preview

The Planted Tank can be previewed in an ordinary browser with the already-installed Python 3 static server:

```powershell
cd habitat
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/`. Move the pointer to exercise fish proximity response, press Space to pause/resume, and press `D` to toggle local diagnostics. Python is an optional development-only static file server: it is not a production or Habitat Runtime dependency, no Python packages are used, and production continues to load these same habitat files through the local `https://aquarium.local/` WebView2 mapping.

## Result on the tested machine

Spike #3 succeeded on Windows 11 Pro 25H2 build 26200.9457. A native DirectComposition host displays a WebView2 CompositionController loading a local Three.js/WebGL2 habitat beneath interactive Explorer icons. Sprint 1 replaces the three-fish feasibility scene with a deterministic 10-fish Planted Tank whose authoritative simulation is independent of its instanced Three.js projection.

The same Aquarium process automatically recovered after three consecutive Explorer restarts by rebuilding its desktop-bound HWND, DirectComposition, and WebView2 resources. A normal `HWND_BOTTOM` or conventional interactive WebView fallback is intentionally absent.

See [the feasibility report](docs/feasibility-report.md) for exact evidence and the recommendation.
