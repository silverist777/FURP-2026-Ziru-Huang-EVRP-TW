param(
    [string]$Python = "python",
    [switch]$SkipPipUpgrade,
    [switch]$SkipTorchInstall,
    [switch]$SkipToolInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPath = Join-Path $RepoRoot ".venv_pomo_cuda"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating .venv_pomo_cuda with $Python"
    & $Python -m venv $VenvPath
}

Write-Host "Using $VenvPython"
& $VenvPython --version

if (-not $SkipPipUpgrade) {
    Write-Host "Upgrading pip"
    & $VenvPython -m pip install --upgrade pip
}

if (-not $SkipTorchInstall) {
    Write-Host "Installing CUDA-enabled PyTorch"
    & $VenvPython -m pip install -r (Join-Path $RepoRoot "src\requirements-pomo-cuda.txt")
}

if (-not $SkipToolInstall) {
    Write-Host "Installing yd-kwon/POMO utility packages"
    & $VenvPython -m pip install -r (Join-Path $RepoRoot "src\requirements-pomo-tools.txt")
}

Write-Host "Running CUDA/PyTorch preflight"
& $VenvPython -c "import torch; print('torch=' + torch.__version__); print('cuda_available=' + str(torch.cuda.is_available())); print('cuda_device=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'))"
