param(
  [string]$HabitatDirectory = (Join-Path $PSScriptRoot '..\..\bin\habitat'),
  [ValidateSet('full', 'fish-only', 'environment-only', 'minimal-render', 'no-render')]
  [string]$Mode = 'full',
  [ValidateRange(0, 50)]
  [int]$FishCount = 10,
  [ValidateRange(0.01, 1)]
  [double]$RenderScale = 1,
  [ValidateRange(0, 60)]
  [int]$TargetFps = 60,
  [ValidateSet('normal', 'stationary', 'ignore')]
  [string]$PointerMode = 'normal',
  [switch]$Reset
)

$ErrorActionPreference = 'Stop'
$path = Join-Path $HabitatDirectory 'audit-config.js'
if (-not (Test-Path -LiteralPath $path)) {
  throw "Generated audit configuration was not found: $path"
}

$replacement = if ($Reset) {
  'const NATIVE_AUDIT_OVERRIDE = null;'
} else {
  $profile = [ordered]@{
    enabled = $true
    mode = $Mode
    fishCount = $FishCount
    renderScale = $RenderScale
    targetFps = $TargetFps
    pointerMode = $PointerMode
  }
  'const NATIVE_AUDIT_OVERRIDE = ' + ($profile | ConvertTo-Json -Compress) + ';'
}

$source = Get-Content -LiteralPath $path -Raw
$updated = $source -replace '(?m)^const NATIVE_AUDIT_OVERRIDE = .*;$', $replacement
if ($updated -eq $source -and $source -notmatch [regex]::Escape($replacement)) {
  throw 'Generated audit override marker was not found.'
}
$updated | Set-Content -LiteralPath $path -Encoding utf8 -NoNewline
Write-Output $replacement
