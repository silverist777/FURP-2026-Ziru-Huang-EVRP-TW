$ErrorActionPreference = "Stop"

$routefinderRoot = Join-Path $PSScriptRoot "routefinder"
$python = Join-Path $routefinderRoot ".venv\Scripts\python.exe"
$checkpoint = Join-Path $routefinderRoot "checkpoints\50\rf-transformer.ckpt"
$dataset = Join-Path $routefinderRoot "data\vrptw\test\50.npz"
$matplotlibCache = Join-Path (Split-Path $PSScriptRoot -Parent) ".cache\matplotlib-routefinder"

if (-not (Test-Path -LiteralPath $python)) {
    throw "RouteFinder virtual environment not found: $python"
}
if (-not (Test-Path -LiteralPath $checkpoint)) {
    throw "RouteFinder checkpoint not found: $checkpoint"
}
if (-not (Test-Path -LiteralPath $dataset)) {
    throw "RouteFinder test dataset not found: $dataset"
}

$env:TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD = "1"
$env:MPLCONFIGDIR = $matplotlibCache

Push-Location $routefinderRoot
try {
    & $python test.py `
        --checkpoint "checkpoints/50/rf-transformer.ckpt" `
        --problem vrptw `
        --size 50 `
        --datasets "data/vrptw/test/50.npz" `
        --batch_size 100 `
        --device cuda `
        --no-save-results
}
finally {
    Pop-Location
}
