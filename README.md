# Aquarium.exe Windows feasibility spike

This repository contains a deliberately minimal Win32/D3D11 experiment. It is not a product implementation.

## Build and run

Requirements: Windows 11, Visual Studio C++ Build Tools, and a Windows SDK.

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

Spike #2 succeeded on Windows 11 Pro 25H2 build 26200.9457. The decisive change was replacing the legacy DXGI HWND swap chain with a D3D11 composition swap chain presented through DirectComposition. The fish is visibly animated beneath Explorer icons, desktop input remains with Explorer, global cursor proximity affects the fish, and pause/resume works.

Automatic recovery after Explorer restart is not implemented; relaunching the probe recovers correctly. A normal `HWND_BOTTOM` fallback is intentionally absent. WebView2 and Three.js are not part of this spike.

See [the feasibility report](docs/feasibility-report.md) for exact evidence and the recommendation.
