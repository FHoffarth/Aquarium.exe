$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $PSScriptRoot '..\..\tools\performance\Measure-AquariumRun.ps1'
. $scriptPath

function Assert-Equal($Actual, $Expected, [string]$Message) {
  if ($Actual -ne $Expected) {
    throw "$Message (expected '$Expected', got '$Actual')"
  }
}

Assert-Equal (Get-AquariumProcessRole 'AquariumSpike.exe' '') 'native' 'native role'
Assert-Equal (Get-AquariumProcessRole 'msedgewebview2.exe' '--type=renderer') 'renderer' 'renderer role'
Assert-Equal (Get-AquariumProcessRole 'msedgewebview2.exe' '--type=gpu-process') 'gpu' 'GPU role'
Assert-Equal (Get-AquariumProcessRole 'msedgewebview2.exe' '--type=utility --utility-sub-type=network.mojom.NetworkService') 'network' 'network role'
Assert-Equal (Get-AquariumProcessRole 'msedgewebview2.exe' '--type=utility --utility-sub-type=storage.mojom.StorageService') 'storage' 'storage role'
Assert-Equal (Get-AquariumProcessRole 'msedgewebview2.exe' '') 'browser' 'browser role'

$processes = @(
  [pscustomobject]@{ ProcessId = 10; ParentProcessId = 1 },
  [pscustomobject]@{ ProcessId = 11; ParentProcessId = 10 },
  [pscustomobject]@{ ProcessId = 12; ParentProcessId = 11 },
  [pscustomobject]@{ ProcessId = 99; ParentProcessId = 1 }
)
$ids = @(Get-AquariumDescendantIds -RootPid 10 -Processes $processes)
Assert-Equal (($ids -join ',')) '10,11,12' 'recursive descendant discovery'

if (-not (Test-GpuCounterBelongsToPid '\GPU Engine(pid_12_luid_0x0_phys_0_eng_3_engtype_3D)\Utilization Percentage' 12)) {
  throw 'exact GPU PID token should match'
}
if (Test-GpuCounterBelongsToPid '\GPU Engine(pid_123_luid_0x0_phys_0_eng_3_engtype_3D)\Utilization Percentage' 12) {
  throw 'GPU PID token must not use substring matching'
}

Assert-Equal (Get-NormalizedCpuPercent -CpuSeconds 2 -ElapsedSeconds 10 -LogicalProcessors 4) 5 'normalized CPU formula'

Assert-Equal (Get-MeasurementStatus -CpuSnapshots 2 -GpuSamples 3 -GpuAvailable $true -OverrunSeconds 0.4) 'CONCLUSIVE' 'complete bounded sample'
Assert-Equal (Get-MeasurementStatus -CpuSnapshots 1 -GpuSamples 3 -GpuAvailable $true -OverrunSeconds 0.4) 'INCONCLUSIVE' 'missing CPU delta'
Assert-Equal (Get-MeasurementStatus -CpuSnapshots 2 -GpuSamples 1 -GpuAvailable $true -OverrunSeconds 0.4) 'INCONCLUSIVE' 'single GPU point'
Assert-Equal (Get-MeasurementStatus -CpuSnapshots 2 -GpuSamples 3 -GpuAvailable $true -OverrunSeconds 4) 'INCONCLUSIVE' 'unbounded overrun'

Write-Output 'PASS: Aquarium performance sampler helpers'
