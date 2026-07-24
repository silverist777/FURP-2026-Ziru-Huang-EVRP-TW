param(
    [string]$Cases = "c101C5,c101C10,c103C15,c101_21",
    [ValidateSet("cuda", "cpu")]
    [string]$Device = "cuda",
    [ValidateSet(1, 8)]
    [int]$NumAugment = 8,
    [ValidateRange(1, 2147483647)]
    [int]$Seed = 1,
    [int]$MaxCandidates = 4,
    [int]$GreedyPackMaxClients = 50,
    [string]$RawDir = "src\log\week5\routefinder-vehicle-limit",
    [string]$ResultDir = "src\results\week5\five-methods-vehicle-limit",
    [string]$TrackBRawDir = "src\log\week5\four-methods-vehicle-limit"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Set-Location $RepoRoot
$env:PYTHONPATH = "src;src\experiments"
$env:PYTHONUTF8 = "1"
$env:TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD = "1"
$env:MPLCONFIGDIR = Join-Path $RepoRoot ".cache\matplotlib-routefinder"

$Python = Join-Path $RepoRoot "src\routefinder\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "RouteFinder Python environment not found: $Python"
}

$ResolvedRawDir = Join-Path $RepoRoot $RawDir
$ResolvedResultDir = Join-Path $RepoRoot $ResultDir
$RunLogDir = Join-Path $ResolvedRawDir "_run_logs"
New-Item -ItemType Directory -Force -Path $ResolvedRawDir, $ResolvedResultDir, $RunLogDir | Out-Null

$BenchmarkCases = @(
    @{ Name = "c101C5"; Clients = 5; Vehicles = 2; CheckpointSize = 50 },
    @{ Name = "c101C10"; Clients = 10; Vehicles = 4; CheckpointSize = 50 },
    @{ Name = "c103C15"; Clients = 15; Vehicles = 5; CheckpointSize = 50 },
    @{ Name = "c101_21"; Clients = 100; Vehicles = 31; CheckpointSize = 100 }
)

$RequestedCases = @(
    $Cases.Split(",") |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
)
$KnownCases = $BenchmarkCases.Name
foreach ($RequestedCase in $RequestedCases) {
    if ($KnownCases -notcontains $RequestedCase) {
        throw "Unknown benchmark case '$RequestedCase'. Valid cases: $($KnownCases -join ', ')"
    }
}

function Invoke-Experiment {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    $LogPath = Join-Path $RunLogDir "$Label.console.log"
    $Started = Get-Date
    Write-Host "[$($Started.ToString('s'))] $Label"
    $ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ProcessInfo.FileName = $Python
    $ProcessInfo.Arguments = $Arguments -join " "
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
    $Process.WaitForExit()
    $ExitCode = $Process.ExitCode
    $ConsoleOutput = @($StdoutTask.Result, $StderrTask.Result) |
        Where-Object { $_ }
    $ConsoleOutput | Set-Content -LiteralPath $LogPath -Encoding UTF8
    $ConsoleOutput
    $Elapsed = ((Get-Date) - $Started).TotalSeconds
    $Record = "$(Get-Date -Format o)`t$Label`texit=$ExitCode`telapsed_s=$([math]::Round($Elapsed, 3))"
    Add-Content -LiteralPath (Join-Path $RunLogDir "runner.log") -Value $Record -Encoding UTF8
    if ($ExitCode -ne 0) {
        throw "$Label failed with exit code $ExitCode. See $LogPath"
    }
}

function Assert-RouteFinderSolution {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][hashtable]$Case,
        [Parameter(Mandatory)][int]$ExpectedSeed
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing RouteFinder solution JSON: $Path"
    }
    $Result = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    $Failures = @()
    if ($Result.status -ne "solved") { $Failures += "status=$($Result.status)" }
    if (-not [bool]$Result.metrics.feasible) { $Failures += "metrics.feasible=false" }
    if (-not [bool]$Result.repair.feasible) { $Failures += "repair.feasible=false" }
    if (-not [bool]$Result.report.feasible) { $Failures += "report.feasible=false" }
    if ($Result.metrics.served_customers -ne $Case.Clients) {
        $Failures += "served=$($Result.metrics.served_customers)/$($Case.Clients)"
    }
    foreach ($Field in @(
        "missing_customers",
        "duplicate_customers",
        "time_window_violations",
        "capacity_violations",
        "energy_violations",
        "vehicle_limit_violations"
    )) {
        if ($Result.metrics.$Field -ne 0) {
            $Failures += "$Field=$($Result.metrics.$Field)"
        }
    }
    if (@($Result.violations).Count -ne 0) {
        $Failures += "violations=$(@($Result.violations).Count)"
    }
    if ($Result.metrics.max_vehicles -ne $Case.Vehicles) {
        $Failures += "max_vehicles=$($Result.metrics.max_vehicles)/$($Case.Vehicles)"
    }
    if ($Result.metrics.vehicle_count -gt $Case.Vehicles) {
        $Failures += "vehicles=$($Result.metrics.vehicle_count)/$($Case.Vehicles)"
    }
    if ($Result.metrics.vehicle_count -ne @($Result.routes).Count) {
        $Failures += "vehicle_count_routes_mismatch"
    }
    if ($Result.metrics.vehicle_count -ne $Result.experiment_record.vehicles_used) {
        $Failures += "vehicle_count_record_mismatch"
    }
    if ($Result.solver.seed -ne $ExpectedSeed) {
        $Failures += "seed=$($Result.solver.seed)/$ExpectedSeed"
    }
    if ($Failures.Count -ne 0) {
        throw "$($Case.Name) JSON contract failed: $($Failures -join '; ')"
    }
    Write-Host "PASS $($Case.Name): checker-feasible, vehicles=$($Result.metrics.vehicle_count)/$($Case.Vehicles)"
}

$RouteFinderJson = @()
foreach ($Case in $BenchmarkCases) {
    if ($RequestedCases -notcontains $Case.Name) {
        continue
    }

    $Name = $Case.Name
    $Instance = "src\data\evrptw_instances\$Name.txt"
    $Checkpoint = "src\routefinder\checkpoints\$($Case.CheckpointSize)\rf-transformer.ckpt"
    $Output = Join-Path $ResolvedRawDir "$Name`_routefinder_repair.json"
    $RouteFinderJson += $Output

    Invoke-Experiment "routefinder_$Name" @(
        "src\experiments\methods\routefinder\routefinder_evrptw_repair_pipeline.py",
        "--schneider", $Instance,
        "--vehicles", [string]$Case.Vehicles,
        "--seed", [string]$Seed,
        "--device", $Device,
        "--checkpoint", $Checkpoint,
        "--num-augment", [string]$NumAugment,
        "--max-candidates", [string]$MaxCandidates,
        "--greedy-pack-max-clients", [string]$GreedyPackMaxClients,
        "--output", $Output,
        "--fail-on-unsolved"
    )
    Assert-RouteFinderSolution -Path $Output -Case $Case -ExpectedSeed $Seed
}

$CollectArguments = @(
    "src\experiments\tools\week4_collect_results.py",
    "--results-dir", $TrackBRawDir,
    "--output-csv", (Join-Path $ResolvedResultDir "five_methods_summary.csv"),
    "--output-md", (Join-Path $ResolvedResultDir "summary.md"),
    "--title", '"Week 5 EVRPTW Five-Method Vehicle-Limit Benchmark"'
)
foreach ($JsonPath in $RouteFinderJson) {
    $CollectArguments += @("--additional-json", $JsonPath)
}
Invoke-Experiment "collect_five_method_results" $CollectArguments

Write-Host "RouteFinder raw records: $ResolvedRawDir"
Write-Host "Five-method summary: $ResolvedResultDir"
