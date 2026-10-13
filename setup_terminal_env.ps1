$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venv = Join-Path $root ".venv313"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    $python313 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"

    if ($pythonLauncher) {
        & $pythonLauncher.Source -3.13 -m venv $venv
    } elseif (Test-Path $python313) {
        & $python313 -m venv $venv
    } else {
        throw "Python 3.13 was not found. Install Python 3.13, then rerun this script."
    }

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $python)) {
        throw "Could not create the Python 3.13 environment. Check the Python installation and rerun this script."
    }
}

& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $root "requirements-dev.txt")
& $python -m pip check

Write-Host ""
Write-Host "Environment is ready."
Write-Host "Run this to activate in your terminal:"
Write-Host "  .\.venv313\Scripts\Activate.ps1"
Write-Host ""
