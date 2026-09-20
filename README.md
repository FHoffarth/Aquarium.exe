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

The D3D11 renderer, fish reaction, input pass-through, and pause/resume controls worked. Explorer accepted the expected raised-desktop HWND hierarchy, but Windows 11 build 26200 did **not** visibly composite the attached surface behind the icons. A normal `HWND_BOTTOM` fallback is intentionally absent.

See [the feasibility report](docs/feasibility-report.md) for exact evidence and the recommendation.

