param(
    [switch]$IncludePomo100,
    [string]$RawDir = "src\log\week5\four-methods-vehicle-limit",
    [string]$ResultDir = "src\results\week5\four-methods-vehicle-limit"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Set-Location $RepoRoot
$env:PYTHONPATH = "src;src\experiments"

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found: $Python"
}

$ResolvedRawDir = Join-Path $RepoRoot $RawDir
$ResolvedResultDir = Join-Path $RepoRoot $ResultDir
$RunLogDir = Join-Path $ResolvedRawDir "_run_logs"
New-Item -ItemType Directory -Force -Path $ResolvedRawDir, $ResolvedResultDir, $RunLogDir | Out-Null

$Cases = @(
    @{ Name = "c101C5"; Clients = 5; Vehicles = 2 },
    @{ Name = "c101C10"; Clients = 10; Vehicles = 4 },
    @{ Name = "c103C15"; Clients = 15; Vehicles = 5 },
    @{ Name = "c101_21"; Clients = 100; Vehicles = 31 }
)

function Invoke-Experiment {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    $LogPath = Join-Path $RunLogDir "$Label.console.log"
    $Started = Get-Date
    Write-Host "[$($Started.ToString('s'))] $Label"
    & $Python @Arguments *> $LogPath
    $ExitCode = $LASTEXITCODE
    $Elapsed = ((Get-Date) - $Started).TotalSeconds
    $Record = "$(Get-Date -Format o)`t$Label`texit=$ExitCode`telapsed_s=$([math]::Round($Elapsed, 3))"
    Add-Content -LiteralPath (Join-Path $RunLogDir "runner.log") -Value $Record -Encoding UTF8
    if ($ExitCode -ne 0) {
        throw "$Label failed with exit code $ExitCode. See $LogPath"
    }
}

foreach ($Case in $Cases) {
    $Name = $Case.Name
    $Clients = [string]$Case.Clients
    $Vehicles = [string]$Case.Vehicles
    $Instance = "src\data\evrptw_instances\$Name.txt"

    Invoke-Experiment "pyvrp_$Name" @(
        "src\experiments\methods\pyvrp\solve_evrptw_pipeline.py",
        "--schneider", $Instance,
        "--vehicles", $Vehicles,
        "--runtime-seconds", "10",
        "--seed", "1",
        "--output", "$ResolvedRawDir\$Name`_pyvrp_repair.json"
    )

    if (($Name -ne "c101_21") -or $IncludePomo100) {
        Invoke-Experiment "pomo_$Name" @(
            "src\experiments\methods\pomo\pomo_evrptw_repair_pipeline.py",
            "--schneider", $Instance,
            "--vehicles", $Vehicles,
            "--seed", "1",
            "--device", "cuda",
            "--max-candidates", "4",
            "--output", "$ResolvedRawDir\$Name`_pomo_repair.json"
        )
    }

    Invoke-Experiment "vns_ts_$Name" @(
        "src\experiments\methods\vns_ts\vns_ts_evrptw_baseline.py",
        "--schneider", $Instance,
        "--vehicles", $Vehicles,
        "--seed", "1",
        "--iterations", "80",
        "--neighbors-per-iteration", "20",
        "--output", "$ResolvedRawDir\$Name`_vns_ts.json"
    )

    Invoke-Experiment "pyga_$Name" @(
        "src\experiments\methods\ga\run_py_ga_vrptw_checked.py",
        "--schneider", $Instance,
        "--instance", $Name,
        "--ind-size", $Clients,
        "--vehicles", $Vehicles,
        "--pop-size", "80",
        "--generations", "50",
        "--seed", "1",
        "--customize-data",
        "--output", "$ResolvedRawDir\$Name`_pyga_checked.json",
        "--output-csv", "$ResolvedRawDir\$Name`_pyga.csv",
        "--output-log", "$ResolvedRawDir\$Name`_pyga.log"
    )
}

Invoke-Experiment "collect_results" @(
    "src\experiments\tools\week4_collect_results.py",
    "--results-dir", $RawDir,
    "--output-csv", "$RawDir\four_methods_summary.csv",
    "--output-md", "$ResultDir\summary.md"
)

Invoke-Experiment "build_visualizations" @(
    "src\experiments\tools\build_weekly_visualizations.py"
)

Write-Host "Track B raw records: $ResolvedRawDir"
Write-Host "Track B results: $ResolvedResultDir"
