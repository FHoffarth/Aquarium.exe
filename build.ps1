param(
  [ValidateSet('All', 'Tests')]
  [string]$Target = 'All'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$out = Join-Path $root 'bin'
New-Item -ItemType Directory -Force $out | Out-Null

$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path $vswhere)) { throw 'Visual Studio Build Tools were not found.' }
$vs = & $vswhere -latest -products * -property installationPath
$devShell = Join-Path $vs 'Common7\Tools\Launch-VsDevShell.ps1'
. $devShell -Arch amd64 -HostArch amd64 -SkipAutomaticLocation

$common = @('/nologo', '/std:c++20', '/EHsc', '/W4', '/WX', '/DUNICODE', '/D_UNICODE')
& cl.exe @common (Join-Path $root 'tests\fish_logic_tests.cpp') "/Fe:$out\fish_logic_tests.exe"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$out\fish_logic_tests.exe"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Target -eq 'All') {
  & cl.exe @common '/O2' (Join-Path $root 'src\main.cpp') "/Fe:$out\AquariumSpike.exe" '/link' 'd3d11.lib' 'dxgi.lib' 'd3dcompiler.lib' 'dcomp.lib' 'user32.lib' 'gdi32.lib' 'shell32.lib'
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
