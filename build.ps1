param(
  [ValidateSet('All', 'Tests')]
  [string]$Target = 'All'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$out = Join-Path $root 'bin'
$webViewRoot = Join-Path $root 'third_party\webview2'
$webViewInclude = Join-Path $webViewRoot 'include'
$webViewX64 = Join-Path $webViewRoot 'x64'
$webViewLoader = Join-Path $webViewX64 'WebView2Loader.dll'
New-Item -ItemType Directory -Force $out | Out-Null

if (-not (Test-Path (Join-Path $webViewInclude 'WebView2.h')) -or
    -not (Test-Path (Join-Path $webViewX64 'WebView2Loader.dll.lib')) -or
    -not (Test-Path $webViewLoader)) {
  throw 'Native WebView2 SDK 1.0.3405.78 is missing from third_party\webview2.'
}

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

& cl.exe @common (Join-Path $root 'tests\host_policy_tests.cpp') "/Fe:$out\host_policy_tests.exe"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$out\host_policy_tests.exe"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& cl.exe @common "/I$webViewInclude" (Join-Path $root 'tests\webview2_sdk_probe.cpp') "/Fe:$out\webview2_sdk_probe.exe" "/link" "/LIBPATH:$webViewX64" 'WebView2Loader.dll.lib' 'ole32.lib'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Copy-Item -LiteralPath $webViewLoader -Destination (Join-Path $out 'WebView2Loader.dll') -Force
& "$out\webview2_sdk_probe.exe"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Target -eq 'All') {
  & cl.exe @common "/I$webViewInclude" '/O2' (Join-Path $root 'src\main.cpp') (Join-Path $root 'src\webview_runtime.cpp') "/Fe:$out\AquariumSpike.exe" '/link' "/LIBPATH:$webViewX64" 'WebView2Loader.dll.lib' 'd3d11.lib' 'dxgi.lib' 'dcomp.lib' 'user32.lib' 'gdi32.lib' 'shell32.lib' 'ole32.lib'
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Copy-Item -LiteralPath (Join-Path $root 'habitat') -Destination $out -Recurse -Force
}
