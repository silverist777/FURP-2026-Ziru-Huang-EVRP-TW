param(
    [string]$Manifest = "src\experiments\configs\week5_three_group_stability.json",
    [Nullable[int]]$Seed = $null,
    [string]$Groups = "C,R,RC",
    [string]$Sizes = "5,10,15,100",
    [string]$Methods = "pyvrp_repair,vns_ts,pomo_repair,pyga_checked,routefinder_repair",
    [ValidateRange(1, 2147483)]
    [int]$JobTimeoutSeconds = 7200,
    [switch]$Force,
    [string]$RawDir = "src\log\week5\stability-three-groups",
    [string]$ResultDir = "src\results\week5\stability-three-groups",
    [ValidateSet("cuda", "cpu")]
    [string]$Device = "cuda"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $RepoRoot
$env:PYTHONPATH = "$(Join-Path $RepoRoot 'src');$(Join-Path $RepoRoot 'src\experiments')"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD = "1"
$env:MPLCONFIGDIR = Join-Path $RepoRoot ".cache\matplotlib-stability"

$ProjectPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RouteFinderPython = Join-Path $RepoRoot "src\routefinder\.venv\Scripts\python.exe"
$ValidatorScript = Join-Path $RepoRoot "src\experiments\tools\validate_stability_result.py"
$SummarizerScript = Join-Path $RepoRoot "src\experiments\tools\summarize_three_group_stability.py"
$FeasibilityCheckerScript = Join-Path $RepoRoot "src\experiments\checkers\feasibility_checker.py"
$FleetPolicyScript = Join-Path $RepoRoot "src\experiments\core\evrptw_fleet_policy.py"
$ConverterScript = Join-Path $RepoRoot "src\experiments\methods\pyvrp\parse_schneider_instance.py"
$RepairScript = Join-Path $RepoRoot "src\experiments\methods\pyvrp\evrptw_v3_repair.py"
$RouteFinderCompactionScript = Join-Path $RepoRoot "src\experiments\methods\routefinder\fleet_compaction.py"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$FileHashCache = @{}

function Get-AbsolutePath {
    param([Parameter(Mandatory)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function Get-StringSelection {
    param([Parameter(Mandatory)][string]$Value)

    return @(
        $Value.Split(",") |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
}

function ConvertTo-NativeArgument {
    param([AllowEmptyString()][string]$Value)

    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }
    $Escaped = [System.Text.RegularExpressions.Regex]::Replace(
        $Value,
        '(\\*)"',
        '$1$1\"'
    )
    $Escaped = [System.Text.RegularExpressions.Regex]::Replace(
        $Escaped,
        '(\\+)$',
        '$1$1'
    )
    return '"' + $Escaped + '"'
}

function Format-CommandLine {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    $Parts = @((ConvertTo-NativeArgument $FilePath))
    $Parts += @($Arguments | ForEach-Object { ConvertTo-NativeArgument ([string]$_) })
    return $Parts -join " "
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory)]$Value,
        [Parameter(Mandatory)][string]$Path,
        [int]$Depth = 20
    )

    $Parent = Split-Path -Parent $Path
    if ($Parent) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }
    [string]$Json = $Value | ConvertTo-Json -Depth $Depth
    [System.IO.File]::WriteAllText(
        $Path,
        $Json + [System.Environment]::NewLine,
        $Utf8NoBom
    )
}

function Get-FileSha256 {
    param([Parameter(Mandatory)][string]$Path)

    $FullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
        throw "Protocol input file not found: $FullPath"
    }
    if (-not $FileHashCache.ContainsKey($FullPath)) {
        $FileHashCache[$FullPath] = (
            Get-FileHash -LiteralPath $FullPath -Algorithm SHA256
        ).Hash.ToLowerInvariant()
    }
    return [string]$FileHashCache[$FullPath]
}

function Get-StringSha256 {
    param([Parameter(Mandatory)][string]$Value)

    $Algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        $Digest = $Algorithm.ComputeHash($Bytes)
        return (($Digest | ForEach-Object { $_.ToString("x2") }) -join "")
    }
    finally {
        $Algorithm.Dispose()
    }
}

function Invoke-CapturedProcess {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][int]$TimeoutSeconds
    )

    $StartedAt = [DateTimeOffset]::Now
    $Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $TimedOut = $false
    $ExitCode = $null
    $Stdout = ""
    $Stderr = ""
    $LaunchError = $null
    $Process = $null

    try {
        $ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
        $ProcessInfo.FileName = $FilePath
        $ProcessInfo.Arguments = @(
            $Arguments | ForEach-Object { ConvertTo-NativeArgument ([string]$_) }
        ) -join " "
        $ProcessInfo.WorkingDirectory = $RepoRoot
        $ProcessInfo.UseShellExecute = $false
        $ProcessInfo.CreateNoWindow = $true
        $ProcessInfo.RedirectStandardOutput = $true
        $ProcessInfo.RedirectStandardError = $true
        $ProcessInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $ProcessInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

        $Process = New-Object System.Diagnostics.Process
        $Process.StartInfo = $ProcessInfo
        [void]$Process.Start()
        $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
        $StderrTask = $Process.StandardError.ReadToEndAsync()
        $Finished = $Process.WaitForExit($TimeoutSeconds * 1000)
        if (-not $Finished) {
            $TimedOut = $true
            try {
                # Kill only the exact solver process. Child-tree termination is
                # deliberately not used because jobs are isolated sequentially.
                $Process.Kill()
            }
            catch {
                $Stderr += "Process termination failed: $($_.Exception.Message)`r`n"
            }
        }
        try {
            $Process.WaitForExit()
        }
        catch {
            $Stderr += "Process wait failed: $($_.Exception.Message)`r`n"
        }
        $Stdout += [string]$StdoutTask.Result
        $Stderr += [string]$StderrTask.Result
        if ($Process.HasExited) {
            $ExitCode = [int]$Process.ExitCode
        }
    }
    catch {
        $LaunchError = "$(($_.Exception.GetType().FullName)): $($_.Exception.Message)"
        $Stderr += "$LaunchError`r`n"
    }
    finally {
        $Stopwatch.Stop()
        if ($null -ne $Process) {
            $Process.Dispose()
        }
    }

    return [pscustomobject][ordered]@{
        started_at = $StartedAt.ToString("o")
        ended_at = [DateTimeOffset]::Now.ToString("o")
        wall_runtime_seconds = [math]::Round($Stopwatch.Elapsed.TotalSeconds, 6)
        exit_code = $ExitCode
        timed_out = [bool]$TimedOut
        launch_error = $LaunchError
        stdout = $Stdout
        stderr = $Stderr
    }
}

function Assert-SafePathComponent {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Value
    )

    if ($Value -notmatch '^[A-Za-z0-9_.-]+$') {
        throw "Unsafe $Name path component '$Value' in stability manifest."
    }
}

$ResolvedManifest = Get-AbsolutePath $Manifest
if (-not (Test-Path -LiteralPath $ResolvedManifest -PathType Leaf)) {
    throw "Stability manifest not found: $ResolvedManifest"
}
if (-not (Test-Path -LiteralPath $ValidatorScript -PathType Leaf)) {
    throw "Fresh-checker validator not found: $ValidatorScript"
}

$ManifestData = Get-Content -LiteralPath $ResolvedManifest -Raw -Encoding UTF8 |
    ConvertFrom-Json
$EffectiveSeed = if ($null -eq $Seed) { [int]$ManifestData.seed } else { [int]$Seed }
if ($EffectiveSeed -lt 0) {
    throw "Seed must be non-negative. Received: $EffectiveSeed"
}

$RequestedGroups = @(Get-StringSelection $Groups)
$RequestedMethods = @(Get-StringSelection $Methods)
$RequestedSizes = @()
foreach ($SizeToken in @(Get-StringSelection $Sizes)) {
    $ParsedSize = 0
    if (-not [int]::TryParse($SizeToken, [ref]$ParsedSize) -or $ParsedSize -le 0) {
        throw "Invalid client size '$SizeToken'."
    }
    $RequestedSizes += $ParsedSize
}
$RequestedSizes = @($RequestedSizes | Sort-Object -Unique)

$KnownGroups = @($ManifestData.groups | ForEach-Object { [string]$_.id })
$KnownMethods = @($ManifestData.methods | ForEach-Object { [string]$_.id })
$KnownSizes = @(
    $ManifestData.groups.cases |
        ForEach-Object { [int]$_.clients } |
        Sort-Object -Unique
)
foreach ($RequestedGroup in $RequestedGroups) {
    if ($KnownGroups -notcontains $RequestedGroup) {
        throw "Unknown group '$RequestedGroup'. Valid groups: $($KnownGroups -join ', ')"
    }
}
foreach ($RequestedMethod in $RequestedMethods) {
    if ($KnownMethods -notcontains $RequestedMethod) {
        throw "Unknown method '$RequestedMethod'. Valid methods: $($KnownMethods -join ', ')"
    }
}
foreach ($RequestedSize in $RequestedSizes) {
    if ($KnownSizes -notcontains $RequestedSize) {
        throw "Unknown client size '$RequestedSize'. Valid sizes: $($KnownSizes -join ', ')"
    }
}

$ResolvedRawDir = Get-AbsolutePath $RawDir
$ResolvedResultDir = Get-AbsolutePath $ResultDir
$RunsDir = Join-Path $ResolvedRawDir "runs"
$BatchEventsPath = Join-Path $ResolvedRawDir "batch_events.jsonl"
$BatchIndexPath = Join-Path $ResolvedRawDir "batch_index.json"

$Jobs = @()
foreach ($RequestedSize in $RequestedSizes) {
    foreach ($ManifestGroup in @($ManifestData.groups)) {
        $GroupId = [string]$ManifestGroup.id
        if ($RequestedGroups -notcontains $GroupId) {
            continue
        }
        Assert-SafePathComponent "group" $GroupId
        foreach ($Case in @($ManifestGroup.cases | Where-Object { [int]$_.clients -eq $RequestedSize })) {
            $InstanceName = [string]$Case.instance
            Assert-SafePathComponent "instance" $InstanceName
            foreach ($ManifestMethod in @($ManifestData.methods)) {
                $MethodId = [string]$ManifestMethod.id
                if ($RequestedMethods -notcontains $MethodId) {
                    continue
                }
                Assert-SafePathComponent "method" $MethodId
                $SeedDirectory = "seed-{0:D4}" -f $EffectiveSeed
                $JobId = "$GroupId-$InstanceName-$MethodId-$SeedDirectory"
                $JobDir = Join-Path $RunsDir "$GroupId\$RequestedSize\$InstanceName\$MethodId\$SeedDirectory"
                $Jobs += [pscustomobject][ordered]@{
                    job_id = $JobId
                    group = $GroupId
                    size = [int]$RequestedSize
                    instance = $InstanceName
                    instance_path = Get-AbsolutePath ([string]$Case.path)
                    clients = [int]$Case.clients
                    stations = [int]$Case.stations
                    max_vehicles = [int]$Case.max_vehicles
                    method = $MethodId
                    seed = [int]$EffectiveSeed
                    job_dir = $JobDir
                }
            }
        }
    }
}
if ($Jobs.Count -eq 0) {
    throw "The selected groups, sizes, and methods produced no stability jobs."
}

$BatchId = "{0}-{1}" -f ([DateTimeOffset]::Now.ToString("yyyyMMddTHHmmssfff")), ([Guid]::NewGuid().ToString("N").Substring(0, 8))

function Add-BatchEvent {
    param(
        [Parameter(Mandatory)][string]$Event,
        $Job = $null,
        [hashtable]$Details = @{}
    )

    $Payload = [ordered]@{
        timestamp = [DateTimeOffset]::Now.ToString("o")
        batch_id = $BatchId
        event = $Event
    }
    if ($null -ne $Job) {
        $Payload.job_id = $Job.job_id
        $Payload.group = $Job.group
        $Payload.size = $Job.size
        $Payload.instance = $Job.instance
        $Payload.method = $Job.method
        $Payload.seed = $Job.seed
    }
    foreach ($Key in $Details.Keys) {
        $Payload[$Key] = $Details[$Key]
    }
    $Line = $Payload | ConvertTo-Json -Depth 10 -Compress
    [System.IO.File]::AppendAllText(
        $BatchEventsPath,
        $Line + [System.Environment]::NewLine,
        $Utf8NoBom
    )
}

function Get-JobPaths {
    param([Parameter(Mandatory)]$Job)

    return [pscustomobject][ordered]@{
        result = Join-Path $Job.job_dir "result.json"
        runner = Join-Path $Job.job_dir "runner.json"
        checker = Join-Path $Job.job_dir "checker.json"
        stdout = Join-Path $Job.job_dir "stdout.log"
        stderr = Join-Path $Job.job_dir "stderr.log"
        pyga_csv = Join-Path $Job.job_dir "pyga.csv"
        pyga_log = Join-Path $Job.job_dir "pyga.log"
    }
}

function Test-JobComplete {
    param([Parameter(Mandatory)]$Job)

    $Paths = Get-JobPaths $Job
    if (-not (Test-Path -LiteralPath $Paths.runner -PathType Leaf)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $Paths.checker -PathType Leaf)) {
        return $false
    }
    try {
        # Rebuild the current protocol on every resume decision. File digests
        # are cached, but the canonical command and all bindings are rebuilt.
        $ExpectedProtocol = Get-ProtocolDescriptor -Job $Job -Paths $Paths
        $Runner = Get-Content -LiteralPath $Paths.runner -Raw -Encoding UTF8 |
            ConvertFrom-Json
        return (
            [bool]$Runner.completed -and
            ([string]$Runner.protocol_fingerprint -ceq $ExpectedProtocol.fingerprint)
        )
    }
    catch {
        return $false
    }
}

function Write-BatchIndex {
    $JobStates = @()
    $CompletedCount = 0
    $FeasibleCount = 0
    $TimedOutCount = 0
    foreach ($Job in $Jobs) {
        $Paths = Get-JobPaths $Job
        $Completed = Test-JobComplete $Job
        $StrictFeasible = $false
        $TimedOut = $false
        if ($Completed) {
            $CompletedCount += 1
            try {
                $Checker = Get-Content -LiteralPath $Paths.checker -Raw -Encoding UTF8 |
                    ConvertFrom-Json
                $StrictFeasible = [bool]$Checker.strict_feasible
            }
            catch {
                $StrictFeasible = $false
            }
            try {
                $Runner = Get-Content -LiteralPath $Paths.runner -Raw -Encoding UTF8 |
                    ConvertFrom-Json
                $TimedOut = [bool]$Runner.timed_out
            }
            catch {
                $TimedOut = $false
            }
        }
        if ($StrictFeasible) { $FeasibleCount += 1 }
        if ($TimedOut) { $TimedOutCount += 1 }
        $JobStates += [pscustomobject][ordered]@{
            job_id = $Job.job_id
            completed = [bool]$Completed
            strict_feasible = [bool]$StrictFeasible
            timed_out = [bool]$TimedOut
            runner_path = $Paths.runner
            checker_path = $Paths.checker
        }
    }

    $Index = [ordered]@{
        schema_version = 1
        batch_id = $BatchId
        updated_at = [DateTimeOffset]::Now.ToString("o")
        manifest = $ResolvedManifest
        raw_dir = $ResolvedRawDir
        result_dir = $ResolvedResultDir
        seed = $EffectiveSeed
        selections = [ordered]@{
            groups = $RequestedGroups
            sizes = $RequestedSizes
            methods = $RequestedMethods
        }
        counts = [ordered]@{
            requested = $Jobs.Count
            completed = $CompletedCount
            pending = $Jobs.Count - $CompletedCount
            strict_feasible = $FeasibleCount
            timed_out = $TimedOutCount
        }
        jobs = $JobStates
    }
    Write-JsonFile -Value $Index -Path $BatchIndexPath -Depth 20
}

function Get-MethodCommand {
    param(
        [Parameter(Mandatory)]$Job,
        [Parameter(Mandatory)]$Paths
    )

    $Vehicles = [string]$Job.max_vehicles
    $Clients = [string]$Job.clients
    $JobSeed = [string]$Job.seed
    switch ($Job.method) {
        "pyvrp_repair" {
            return [pscustomobject]@{
                FilePath = $ProjectPython
                PipelinePath = Join-Path $RepoRoot "src\experiments\methods\pyvrp\solve_evrptw_pipeline.py"
                CheckpointPath = $null
                Arguments = @(
                    "src\experiments\methods\pyvrp\solve_evrptw_pipeline.py",
                    "--schneider", $Job.instance_path,
                    "--vehicles", $Vehicles,
                    "--runtime-seconds", "10",
                    "--seed", $JobSeed,
                    "--output", $Paths.result
                )
            }
        }
        "pomo_repair" {
            return [pscustomobject]@{
                FilePath = $ProjectPython
                PipelinePath = Join-Path $RepoRoot "src\experiments\methods\pomo\pomo_evrptw_repair_pipeline.py"
                CheckpointPath = $null
                Arguments = @(
                    "src\experiments\methods\pomo\pomo_evrptw_repair_pipeline.py",
                    "--schneider", $Job.instance_path,
                    "--vehicles", $Vehicles,
                    "--seed", $JobSeed,
                    "--device", $Device,
                    "--max-candidates", "4",
                    "--output", $Paths.result
                )
            }
        }
        "vns_ts" {
            return [pscustomobject]@{
                FilePath = $ProjectPython
                PipelinePath = Join-Path $RepoRoot "src\experiments\methods\vns_ts\vns_ts_evrptw_baseline.py"
                CheckpointPath = $null
                Arguments = @(
                    "src\experiments\methods\vns_ts\vns_ts_evrptw_baseline.py",
                    "--schneider", $Job.instance_path,
                    "--vehicles", $Vehicles,
                    "--seed", $JobSeed,
                    "--iterations", "80",
                    "--neighbors-per-iteration", "20",
                    "--output", $Paths.result
                )
            }
        }
        "pyga_checked" {
            return [pscustomobject]@{
                FilePath = $ProjectPython
                PipelinePath = Join-Path $RepoRoot "src\experiments\methods\ga\run_py_ga_vrptw_checked.py"
                CheckpointPath = $null
                Arguments = @(
                    "src\experiments\methods\ga\run_py_ga_vrptw_checked.py",
                    "--schneider", $Job.instance_path,
                    "--instance", $Job.instance,
                    "--ind-size", $Clients,
                    "--vehicles", $Vehicles,
                    "--pop-size", "80",
                    "--generations", "50",
                    "--seed", $JobSeed,
                    "--customize-data",
                    "--output", $Paths.result,
                    "--output-csv", $Paths.pyga_csv,
                    "--output-log", $Paths.pyga_log
                )
            }
        }
        "routefinder_repair" {
            $CheckpointSize = if ($Job.clients -le 50) { 50 } else { 100 }
            $Checkpoint = Join-Path $RepoRoot "src\routefinder\checkpoints\$CheckpointSize\rf-transformer.ckpt"
            return [pscustomobject]@{
                FilePath = $RouteFinderPython
                PipelinePath = Join-Path $RepoRoot "src\experiments\methods\routefinder\routefinder_evrptw_repair_pipeline.py"
                CheckpointPath = $Checkpoint
                Arguments = @(
                    "src\experiments\methods\routefinder\routefinder_evrptw_repair_pipeline.py",
                    "--schneider", $Job.instance_path,
                    "--vehicles", $Vehicles,
                    "--seed", $JobSeed,
                    "--device", $Device,
                    "--checkpoint", $Checkpoint,
                    "--num-augment", "8",
                    "--max-candidates", "4",
                    "--greedy-pack-max-clients", "50",
                    "--output", $Paths.result
                )
            }
        }
        default {
            throw "No command template exists for method '$($Job.method)'."
        }
    }
}

function Get-ProtocolDescriptor {
    param(
        [Parameter(Mandatory)]$Job,
        [Parameter(Mandatory)]$Paths,
        $Command = $null
    )

    if ($null -eq $Command) {
        $Command = Get-MethodCommand -Job $Job -Paths $Paths
    }
    $CommandLine = Format-CommandLine `
        -FilePath $Command.FilePath `
        -Arguments $Command.Arguments
    $Components = [ordered]@{
        protocol_schema = "week5-three-group-stability-v1"
        job_id = [string]$Job.job_id
        group = [string]$Job.group
        size = [string]$Job.size
        instance = [string]$Job.instance
        method = [string]$Job.method
        seed = [string]$Job.seed
        max_vehicles = [string]$Job.max_vehicles
        manifest_sha256 = Get-FileSha256 $ResolvedManifest
        instance_sha256 = Get-FileSha256 $Job.instance_path
        validator_sha256 = Get-FileSha256 $ValidatorScript
        feasibility_checker_sha256 = Get-FileSha256 $FeasibilityCheckerScript
        fleet_policy_sha256 = Get-FileSha256 $FleetPolicyScript
        converter_sha256 = Get-FileSha256 $ConverterScript
        repair_sha256 = Get-FileSha256 $RepairScript
        method_pipeline_sha256 = Get-FileSha256 $Command.PipelinePath
        python_executable_path = [System.IO.Path]::GetFullPath($Command.FilePath)
        command_line = $CommandLine
        job_timeout_seconds = [string]$JobTimeoutSeconds
    }
    if ($Job.method -eq "routefinder_repair") {
        $Components.routefinder_fleet_compaction_sha256 = Get-FileSha256 $RouteFinderCompactionScript
    }
    $CanonicalLines = @(
        foreach ($Key in $Components.Keys) {
            "$Key=$($Components[$Key])"
        }
    )
    $CanonicalText = ($CanonicalLines -join "`n") + "`n"
    return [pscustomobject][ordered]@{
        fingerprint = Get-StringSha256 $CanonicalText
        components = $Components
        canonical_text = $CanonicalText
        command_line = $CommandLine
    }
}

# Preflight every selected protocol before creating batch output or launching a
# solver. Checkpoints are existence-checked but intentionally not hashed.
foreach ($FixedProtocolFile in @(
    $ResolvedManifest,
    $ValidatorScript,
    $FeasibilityCheckerScript,
    $FleetPolicyScript,
    $ConverterScript,
    $RepairScript
)) {
    [void](Get-FileSha256 $FixedProtocolFile)
}
foreach ($Job in $Jobs) {
    $Paths = Get-JobPaths $Job
    $Command = Get-MethodCommand -Job $Job -Paths $Paths
    foreach ($RequiredFile in @(
        $Job.instance_path,
        $Command.FilePath,
        $Command.PipelinePath
    )) {
        if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
            throw "Required stability-run file not found: $RequiredFile"
        }
    }
    if ($null -ne $Command.CheckpointPath -and -not (
        Test-Path -LiteralPath $Command.CheckpointPath -PathType Leaf
    )) {
        throw "RouteFinder checkpoint not found: $($Command.CheckpointPath)"
    }
    [void](Get-ProtocolDescriptor -Job $Job -Paths $Paths -Command $Command)
}

New-Item -ItemType Directory -Force -Path $RunsDir, $ResolvedResultDir | Out-Null

Add-BatchEvent -Event "batch_started" -Details @{
    requested_jobs = $Jobs.Count
    force = [bool]$Force
    job_timeout_seconds = $JobTimeoutSeconds
}
Write-BatchIndex

$Position = 0
foreach ($Job in $Jobs) {
    $Position += 1
    $Paths = Get-JobPaths $Job
    $JobDirFull = [System.IO.Path]::GetFullPath($Job.job_dir)
    $RawPrefix = $ResolvedRawDir.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not $JobDirFull.StartsWith($RawPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to use job directory outside raw directory: $JobDirFull"
    }
    New-Item -ItemType Directory -Force -Path $JobDirFull | Out-Null

    if (-not $Force -and (Test-JobComplete $Job)) {
        Write-Host "[$Position/$($Jobs.Count)] SKIP $($Job.job_id) (complete)"
        Add-BatchEvent -Event "job_skipped_complete" -Job $Job
        continue
    }

    # Delete only known artifacts for this exact job. This also prevents an
    # interrupted prior run from being mistaken for the current solver output.
    foreach ($Artifact in @(
        $Paths.result,
        $Paths.runner,
        $Paths.checker,
        $Paths.stdout,
        $Paths.stderr,
        $Paths.pyga_csv,
        $Paths.pyga_log
    )) {
        if (Test-Path -LiteralPath $Artifact) {
            Remove-Item -LiteralPath $Artifact -Force
        }
    }

    $Command = Get-MethodCommand -Job $Job -Paths $Paths
    $Protocol = Get-ProtocolDescriptor -Job $Job -Paths $Paths -Command $Command
    $CommandLine = $Protocol.command_line
    Write-Host "[$Position/$($Jobs.Count)] RUN  $($Job.job_id)"
    Add-BatchEvent -Event "job_started" -Job $Job -Details @{
        command = $CommandLine
        protocol_fingerprint = $Protocol.fingerprint
    }

    $Solver = Invoke-CapturedProcess `
        -FilePath $Command.FilePath `
        -Arguments $Command.Arguments `
        -TimeoutSeconds $JobTimeoutSeconds
    [string]$Solver.stdout | Set-Content -LiteralPath $Paths.stdout -Encoding UTF8
    [string]$Solver.stderr | Set-Content -LiteralPath $Paths.stderr -Encoding UTF8

    $RunnerRecord = [ordered]@{
        schema_version = 1
        completed = $false
        job_id = $Job.job_id
        group = $Job.group
        size = $Job.size
        instance = $Job.instance
        method = $Job.method
        seed = $Job.seed
        started_at = $Solver.started_at
        ended_at = $Solver.ended_at
        wall_runtime_seconds = $Solver.wall_runtime_seconds
        exit_code = $Solver.exit_code
        timed_out = $Solver.timed_out
        command = $CommandLine
        protocol_fingerprint = $Protocol.fingerprint
        protocol_components = $Protocol.components
        result_path = $Paths.result
        stdout_path = $Paths.stdout
        stderr_path = $Paths.stderr
        launch_error = $Solver.launch_error
    }
    Write-JsonFile -Value $RunnerRecord -Path $Paths.runner

    $ValidatorArguments = @(
        $ValidatorScript,
        "--schneider", $Job.instance_path,
        "--result", $Paths.result,
        "--output", $Paths.checker,
        "--expected-instance", $Job.instance,
        "--expected-clients", [string]$Job.clients,
        "--expected-stations", [string]$Job.stations,
        "--expected-vehicles", [string]$Job.max_vehicles,
        "--expected-seed", [string]$Job.seed,
        "--group", $Job.group,
        "--method", $Job.method,
        "--job-id", $Job.job_id
    )
    $Validator = Invoke-CapturedProcess `
        -FilePath $ProjectPython `
        -Arguments $ValidatorArguments `
        -TimeoutSeconds ([math]::Min(600, $JobTimeoutSeconds))
    Add-Content -LiteralPath $Paths.stdout -Value "`r`n[validator]`r`n$($Validator.stdout)" -Encoding UTF8
    Add-Content -LiteralPath $Paths.stderr -Value "`r`n[validator]`r`n$($Validator.stderr)" -Encoding UTF8

    $RunnerRecord.completed = $true
    $RunnerRecord.validator_exit_code = $Validator.exit_code
    $RunnerRecord.validator_timed_out = $Validator.timed_out
    $RunnerRecord.validator_launch_error = $Validator.launch_error
    $RunnerRecord.checker_path = $Paths.checker
    $RunnerRecord.checker_exists = Test-Path -LiteralPath $Paths.checker -PathType Leaf
    $RunnerRecord.completed_at = [DateTimeOffset]::Now.ToString("o")
    Write-JsonFile -Value $RunnerRecord -Path $Paths.runner

    $StrictFeasible = $false
    $FailureClass = "checker_missing"
    if ($RunnerRecord.checker_exists) {
        try {
            $CheckerRecord = Get-Content -LiteralPath $Paths.checker -Raw -Encoding UTF8 |
                ConvertFrom-Json
            $StrictFeasible = [bool]$CheckerRecord.strict_feasible
            $FailureClass = [string]$CheckerRecord.failure_class
        }
        catch {
            $FailureClass = "checker_invalid_json"
        }
    }
    Add-BatchEvent -Event "job_completed" -Job $Job -Details @{
        exit_code = $Solver.exit_code
        timed_out = [bool]$Solver.timed_out
        wall_runtime_seconds = $Solver.wall_runtime_seconds
        checker_exists = [bool]$RunnerRecord.checker_exists
        strict_feasible = [bool]$StrictFeasible
        failure_class = $FailureClass
    }
    Write-BatchIndex
    Write-Host (
        "[$Position/$($Jobs.Count)] DONE $($Job.job_id) " +
        "exit=$($Solver.exit_code) timeout=$($Solver.timed_out) " +
        "strict_feasible=$StrictFeasible failure=$FailureClass"
    )
}

Write-BatchIndex
if (Test-Path -LiteralPath $SummarizerScript -PathType Leaf) {
    Write-Host "Running three-group stability summarizer..."
    $SummaryArguments = @(
        $SummarizerScript,
        "--manifest", $ResolvedManifest,
        "--raw-dir", $ResolvedRawDir,
        "--output-dir", $ResolvedResultDir
    )
    $Summary = Invoke-CapturedProcess `
        -FilePath $ProjectPython `
        -Arguments $SummaryArguments `
        -TimeoutSeconds $JobTimeoutSeconds
    [string]$Summary.stdout |
        Set-Content -LiteralPath (Join-Path $ResolvedResultDir "summarizer.stdout.log") -Encoding UTF8
    [string]$Summary.stderr |
        Set-Content -LiteralPath (Join-Path $ResolvedResultDir "summarizer.stderr.log") -Encoding UTF8
    Add-BatchEvent -Event "summary_completed" -Details @{
        exit_code = $Summary.exit_code
        timed_out = [bool]$Summary.timed_out
        wall_runtime_seconds = $Summary.wall_runtime_seconds
    }
    if ($Summary.exit_code -ne 0 -or $Summary.timed_out) {
        Write-Warning "Stability summarizer did not complete successfully. See $ResolvedResultDir."
    }
}
else {
    Add-BatchEvent -Event "summary_skipped_missing_script" -Details @{
        script = $SummarizerScript
    }
    Write-Warning "Stability summarizer is not present yet; job records are complete: $SummarizerScript"
}

Add-BatchEvent -Event "batch_completed" -Details @{ requested_jobs = $Jobs.Count }
Write-BatchIndex
Write-Host "Stability raw records: $ResolvedRawDir"
Write-Host "Stability results: $ResolvedResultDir"
