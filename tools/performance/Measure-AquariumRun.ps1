param(
  [string]$ExecutablePath,
  [string]$OutputPath,
  [ValidateRange(1, 300)]
  [int]$DurationSeconds = 15,
  [ValidateRange(0.25, 30)]
  [double]$SampleIntervalSeconds = 1,
  [ValidateSet('Running', 'Paused')]
  [string]$State = 'Running',
  [string]$ProfileName = 'product-default'
)

$ErrorActionPreference = 'Stop'

function Get-AquariumProcessRole {
  param([string]$Name, [string]$CommandLine)
  $lowerName = ($Name ?? '').ToLowerInvariant()
  $command = $CommandLine ?? ''
  if ($lowerName -eq 'aquariumspike.exe') { return 'native' }
  if ($lowerName -eq 'conhost.exe') { return 'console' }
  if ($command -match 'crashpad-handler') { return 'crashpad' }
  if ($command -match '--type=renderer(?:\s|$)') { return 'renderer' }
  if ($command -match '--type=gpu-process(?:\s|$)') { return 'gpu' }
  if ($command -match 'network\.mojom\.NetworkService') { return 'network' }
  if ($command -match 'storage\.mojom\.StorageService') { return 'storage' }
  if ($command -match '--type=utility(?:\s|$)') { return 'utility' }
  if ($lowerName -eq 'msedgewebview2.exe' -and $command -notmatch '--type=') {
    return 'browser'
  }
  return 'other'
}

function Get-AquariumDescendantIds {
  param([int]$RootPid, [object[]]$Processes)
  $found = [System.Collections.Generic.List[int]]::new()
  $queue = [System.Collections.Generic.Queue[int]]::new()
  $queue.Enqueue($RootPid)
  while ($queue.Count -gt 0) {
    $parent = $queue.Dequeue()
    if ($found.Contains($parent)) { continue }
    $found.Add($parent)
    foreach ($process in $Processes) {
      if ([int]$process.ParentProcessId -eq $parent -and
          -not $found.Contains([int]$process.ProcessId)) {
        $queue.Enqueue([int]$process.ProcessId)
      }
    }
  }
  return $found.ToArray()
}

function Test-GpuCounterBelongsToPid {
  param([string]$Path, [int]$ProcessId)
  return $Path -match "(?i)\bpid_$ProcessId(?:_|\))"
}

function Get-NormalizedCpuPercent {
  param([double]$CpuSeconds, [double]$ElapsedSeconds, [int]$LogicalProcessors)
  if ($ElapsedSeconds -le 0 -or $LogicalProcessors -le 0) { return 0 }
  return [Math]::Round($CpuSeconds * 100 / $ElapsedSeconds / $LogicalProcessors, 3)
}

function Get-MeasurementStatus {
  param(
    [int]$CpuSnapshots,
    [int]$GpuSamples,
    [bool]$GpuAvailable,
    [double]$OverrunSeconds
  )
  if ($CpuSnapshots -lt 2 -or $OverrunSeconds -gt 2) { return 'INCONCLUSIVE' }
  if (-not $GpuAvailable -or $GpuSamples -lt 2) { return 'INCONCLUSIVE' }
  return 'CONCLUSIVE'
}

function Get-AquariumRoots {
  return @(Get-CimInstance Win32_Process -Filter "Name='AquariumSpike.exe'" |
    Where-Object { $_.CommandLine -notmatch '\s--(?:pause|resume|toggle|probe|quit)(?:\s|$)' })
}

function Invoke-AquariumControl {
  param([string]$Executable, [string]$Argument)
  $control = Start-Process -FilePath $Executable -ArgumentList $Argument -PassThru -WindowStyle Hidden
  if (-not $control.WaitForExit(5000)) {
    try { $control.Kill() } catch {}
    throw "Aquarium control '$Argument' exceeded its 5-second timeout"
  }
  if ($control.ExitCode -ne 0) {
    throw "Aquarium control '$Argument' failed with exit code $($control.ExitCode)"
  }
}

function Wait-AquariumReady {
  param([System.Diagnostics.Process]$Process, [string]$LogPath)
  $deadline = [DateTime]::UtcNow.AddSeconds(35)
  while ([DateTime]::UtcNow -lt $deadline) {
    if ($Process.HasExited) { throw "Aquarium exited during startup with code $($Process.ExitCode)" }
    if (Test-Path -LiteralPath $LogPath) {
      $log = Get-Content -LiteralPath $LogPath -Raw
      if ($log -match 'ATTACH FAILURE:') { throw 'Aquarium reported a desktop attachment failure' }
      if ($log -match 'SESSION RUNNING generation=') { return }
    }
    Start-Sleep -Milliseconds 250
  }
  throw 'Aquarium did not report SESSION RUNNING within 35 seconds'
}

function New-AquariumGpuCounters {
  param([int[]]$ProcessIds)
  $category = [Diagnostics.PerformanceCounterCategory]::new('GPU Engine')
  $counters = [System.Collections.Generic.List[object]]::new()
  foreach ($instance in $category.GetInstanceNames()) {
    foreach ($id in $ProcessIds) {
      if (Test-GpuCounterBelongsToPid $instance $id) {
        $counter = [Diagnostics.PerformanceCounter]::new(
          'GPU Engine', 'Utilization Percentage', $instance, $true)
        [void]$counter.NextValue()
        $counters.Add([pscustomobject]@{ processId = $id; counter = $counter })
        break
      }
    }
  }
  return $counters.ToArray()
}

function Read-AquariumGpuCounters {
  param([object[]]$Counters, [int[]]$ProcessIds)
  $byPid = @{}
  foreach ($id in $ProcessIds) { $byPid[[string]$id] = 0.0 }
  try {
    foreach ($entry in $Counters) {
      $byPid[[string]$entry.processId] += [double]$entry.counter.NextValue()
    }
    [pscustomobject]@{
      available = $Counters.Count -gt 0
      timestamp = [DateTime]::UtcNow.ToString('o')
      treePercentSummedEngines = [Math]::Round(
        [double](($byPid.Values | Measure-Object -Sum).Sum), 3)
      byPidPercentSummedEngines = $byPid
      error = if ($Counters.Count -gt 0) { $null } else { 'No PID-matching GPU counters' }
    }
  } catch {
    [pscustomobject]@{
      available = $false
      timestamp = [DateTime]::UtcNow.ToString('o')
      treePercentSummedEngines = $null
      byPidPercentSummedEngines = $byPid
      error = $_.Exception.Message
    }
  }
}

function Invoke-AquariumMeasurement {
  param(
    [Parameter(Mandatory)][string]$Executable,
    [Parameter(Mandatory)][string]$Destination,
    [int]$Seconds,
    [double]$IntervalSeconds,
    [string]$RequestedState,
    [string]$ProfileLabel
  )
  $resolvedExecutable = (Resolve-Path -LiteralPath $Executable).Path
  $existing = @(Get-AquariumRoots)
  if ($existing.Count -ne 0) {
    throw "Expected no existing Aquarium host before launch; found $($existing.Count)"
  }

  $executableDirectory = Split-Path -Parent $resolvedExecutable
  $logPath = Join-Path $executableDirectory 'aquarium-spike.log'
  $process = Start-Process -FilePath $resolvedExecutable -WorkingDirectory $executableDirectory `
    -PassThru -WindowStyle Hidden
  $startedAt = [DateTime]::UtcNow
  $cpuStart = @{}
  $cpuEnd = @{}
  $processMetadata = @{}
  $memorySamples = [System.Collections.Generic.List[object]]::new()
  $gpuSamples = [System.Collections.Generic.List[object]]::new()
  $tcpEndpoints = [System.Collections.Generic.HashSet[string]]::new()
  $sampleErrors = [System.Collections.Generic.List[string]]::new()
  $liveGpuCounters = @()
  try {
    Wait-AquariumReady -Process $process -LogPath $logPath
    Start-Sleep -Seconds 3
    if ($RequestedState -eq 'Paused') {
      Invoke-AquariumControl -Executable $resolvedExecutable -Argument '--pause'
      Start-Sleep -Seconds 2
    }
    Invoke-AquariumControl -Executable $resolvedExecutable -Argument '--probe'

    $roots = @(Get-AquariumRoots)
    if ($roots.Count -ne 1 -or [int]$roots[0].ProcessId -ne $process.Id) {
      throw "Expected exactly one launched Aquarium root; found $($roots.Count)"
    }

    $initialProcesses = @(Get-CimInstance Win32_Process)
    $initialIds = @(Get-AquariumDescendantIds -RootPid $process.Id -Processes $initialProcesses)
    $liveGpuCounters = @(New-AquariumGpuCounters -ProcessIds $initialIds)
    $initialById = @{}
    foreach ($item in $initialProcesses) { $initialById[[int]$item.ProcessId] = $item }
    foreach ($id in $initialIds) {
      $runtimeProcess = Get-Process -Id $id -ErrorAction SilentlyContinue
      $cim = $initialById[$id]
      if (-not $runtimeProcess -or -not $cim) { continue }
      $cpuStart[$id] = $runtimeProcess.TotalProcessorTime.TotalSeconds
      $cpuEnd[$id] = $cpuStart[$id]
      $processMetadata[$id] = [ordered]@{
        pid = $id
        parentPid = [int]$cim.ParentProcessId
        name = $cim.Name
        role = Get-AquariumProcessRole $cim.Name $cim.CommandLine
        commandLine = $cim.CommandLine
      }
    }

    $initialMemoryRow = [ordered]@{
      timestampUtc = [DateTime]::UtcNow.ToString('o')
      processes = @()
    }
    foreach ($id in $initialIds) {
      $runtimeProcess = Get-Process -Id $id -ErrorAction SilentlyContinue
      if (-not $runtimeProcess -or -not $processMetadata.ContainsKey($id)) { continue }
      $initialMemoryRow.processes += [ordered]@{
        pid = $id
        role = $processMetadata[$id].role
        workingSetBytes = [long]$runtimeProcess.WorkingSet64
        privateBytes = [long]$runtimeProcess.PrivateMemorySize64
      }
    }
    $memorySamples.Add([pscustomobject]$initialMemoryRow)

    $sampleStart = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sampleStart.Elapsed.TotalSeconds -lt $Seconds) {
      $remainingSeconds = $Seconds - $sampleStart.Elapsed.TotalSeconds
      Start-Sleep -Milliseconds ([Math]::Max(
        1, [int]([Math]::Min($IntervalSeconds, $remainingSeconds) * 1000)))
      $gpuSamples.Add((Read-AquariumGpuCounters `
        -Counters $liveGpuCounters -ProcessIds $initialIds))
    }
    $sampleStart.Stop()
    if ($process.HasExited) { throw 'Aquarium exited during measurement' }

    $finalProcesses = @(Get-CimInstance Win32_Process)
    $finalIds = @(Get-AquariumDescendantIds -RootPid $process.Id -Processes $finalProcesses)
    foreach ($id in $finalIds) {
      $runtimeProcess = Get-Process -Id $id -ErrorAction SilentlyContinue
      if ($runtimeProcess) { $cpuEnd[$id] = $runtimeProcess.TotalProcessorTime.TotalSeconds }
    }
    $finalMemoryRow = [ordered]@{
      timestampUtc = [DateTime]::UtcNow.ToString('o')
      processes = @()
    }
    foreach ($id in $finalIds) {
      $runtimeProcess = Get-Process -Id $id -ErrorAction SilentlyContinue
      if (-not $runtimeProcess -or -not $processMetadata.ContainsKey($id)) { continue }
      $finalMemoryRow.processes += [ordered]@{
        pid = $id
        role = $processMetadata[$id].role
        workingSetBytes = [long]$runtimeProcess.WorkingSet64
        privateBytes = [long]$runtimeProcess.PrivateMemorySize64
      }
    }
    $memorySamples.Add([pscustomobject]$finalMemoryRow)
    try {
      foreach ($connection in Get-NetTCPConnection -ErrorAction Stop |
        Where-Object { $finalIds -contains $_.OwningProcess }) {
        [void]$tcpEndpoints.Add("$($connection.OwningProcess):$($connection.LocalAddress):$($connection.LocalPort)->$($connection.RemoteAddress):$($connection.RemotePort):$($connection.State)")
      }
    } catch {
      $sampleErrors.Add("TCP: $($_.Exception.Message)")
    }
    Invoke-AquariumControl -Executable $resolvedExecutable -Argument '--probe'

    $logicalProcessors = [Environment]::ProcessorCount
    $elapsed = $sampleStart.Elapsed.TotalSeconds
    $processSummary = foreach ($entry in $processMetadata.GetEnumerator() | Sort-Object Name) {
      $id = [int]$entry.Name
      $cpuDelta = if ($cpuStart.ContainsKey($id) -and $cpuEnd.ContainsKey($id)) {
        [Math]::Max(0, [double]$cpuEnd[$id] - [double]$cpuStart[$id])
      } else { 0 }
      $rows = @($memorySamples | ForEach-Object { $_.processes } | Where-Object pid -eq $id)
      $working = @($rows | ForEach-Object workingSetBytes)
      $private = @($rows | ForEach-Object privateBytes)
      [pscustomobject]@{
        pid = $id
        parentPid = $entry.Value.parentPid
        name = $entry.Value.name
        role = $entry.Value.role
        commandLine = $entry.Value.commandLine
        cpuSeconds = [Math]::Round($cpuDelta, 4)
        cpuPercentNormalized = Get-NormalizedCpuPercent $cpuDelta $elapsed $logicalProcessors
        workingSetBytesMean = if ($working.Count) { [long](($working | Measure-Object -Average).Average) } else { 0 }
        workingSetBytesMax = if ($working.Count) { [long](($working | Measure-Object -Maximum).Maximum) } else { 0 }
        privateBytesMean = if ($private.Count) { [long](($private | Measure-Object -Average).Average) } else { 0 }
      }
    }

    $log = Get-Content -LiteralPath $logPath -Raw
    $perfLines = @([regex]::Matches($log, '(?m)^.*(?:PERF |habitat-metrics:|audit-performance:|PROBE ).*$') |
      ForEach-Object Value)
    $gpuAvailable = @($gpuSamples | Where-Object available)
    $treeCpuSeconds = ($processSummary.cpuSeconds | Measure-Object -Sum).Sum
    $memoryLast = @($memorySamples[-1].processes)
    $operatingSystem = Get-CimInstance Win32_OperatingSystem
    $video = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion,
      CurrentHorizontalResolution, CurrentVerticalResolution)
    $measurementStatus = Get-MeasurementStatus -CpuSnapshots 2 `
      -GpuSamples $gpuAvailable.Count -GpuAvailable ($gpuAvailable.Count -gt 0) `
      -OverrunSeconds ([Math]::Max(0, $elapsed - $Seconds))
    $result = [ordered]@{
      schemaVersion = 1
      status = $measurementStatus
      profile = $ProfileLabel
      requestedState = $RequestedState.ToLowerInvariant()
      startedAtUtc = $startedAt.ToString('o')
      completedAtUtc = [DateTime]::UtcNow.ToString('o')
      durationSeconds = [Math]::Round($elapsed, 3)
      sampleIntervalSeconds = $IntervalSeconds
      environment = [ordered]@{
        osCaption = $operatingSystem.Caption
        osVersion = $operatingSystem.Version
        osBuild = $operatingSystem.BuildNumber
        logicalProcessors = $logicalProcessors
        videoControllers = $video
      }
      validity = [ordered]@{
        exactlyOneAquariumRoot = $true
        sessionRunning = $log -match 'SESSION RUNNING generation='
        noAttachmentFailure = $log -notmatch 'ATTACH FAILURE:'
        rootAliveThroughSample = -not $process.HasExited
      }
      processSummary = @($processSummary)
      totals = [ordered]@{
        cpuSeconds = [Math]::Round([double]$treeCpuSeconds, 4)
        cpuPercentNormalized = Get-NormalizedCpuPercent $treeCpuSeconds $elapsed $logicalProcessors
        workingSetBytesLast = [long](($memoryLast.workingSetBytes | Measure-Object -Sum).Sum)
        privateBytesLast = [long](($memoryLast.privateBytes | Measure-Object -Sum).Sum)
        gpuPercentSummedEnginesMean = if ($gpuAvailable.Count) {
          [Math]::Round([double](($gpuAvailable.treePercentSummedEngines | Measure-Object -Average).Average), 3)
        } else { $null }
        gpuPercentSummedEnginesMin = if ($gpuAvailable.Count) {
          [Math]::Round([double](($gpuAvailable.treePercentSummedEngines | Measure-Object -Minimum).Minimum), 3)
        } else { $null }
        gpuPercentSummedEnginesMax = if ($gpuAvailable.Count) {
          [Math]::Round([double](($gpuAvailable.treePercentSummedEngines | Measure-Object -Maximum).Maximum), 3)
        } else { $null }
        tcpConnectionCount = $tcpEndpoints.Count
      }
      gpuMethod = 'Windows GPU Engine utilization counters, summed only for exact current descendant PID tokens; simultaneous engines can sum above one engine and counters exclude compositor work in dwm.exe.'
      gpuSamples = @($gpuSamples)
      memorySamples = @($memorySamples)
      tcpEndpoints = @($tcpEndpoints)
      diagnosticLines = $perfLines
      sampleErrors = @($sampleErrors)
    }

    $parent = Split-Path -Parent $Destination
    if ($parent) { New-Item -ItemType Directory -Force $parent | Out-Null }
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Destination -Encoding utf8
    return [pscustomobject]$result
  } finally {
    foreach ($entry in $liveGpuCounters) { $entry.counter.Dispose() }
    if (-not $process.HasExited) {
      try { Invoke-AquariumControl -Executable $resolvedExecutable -Argument '--quit' } catch {}
      if (-not $process.WaitForExit(10000)) {
        throw 'Aquarium did not exit within 10 seconds after --quit'
      }
    }
  }
}

if ($MyInvocation.InvocationName -ne '.') {
  if (-not $ExecutablePath -or -not $OutputPath) {
    throw 'ExecutablePath and OutputPath are required.'
  }
  Invoke-AquariumMeasurement -Executable $ExecutablePath -Destination $OutputPath `
    -Seconds $DurationSeconds -IntervalSeconds $SampleIntervalSeconds `
    -RequestedState $State -ProfileLabel $ProfileName | Out-Null
}
