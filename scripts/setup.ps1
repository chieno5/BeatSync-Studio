param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
    $PythonArgs = @("-3.12")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
    $PythonArgs = @()
} else {
    throw "Python 3.10-3.12 was not found. Install Python 3.12 and retry."
}

& $PythonCommand @PythonArgs -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 13) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "BeatSync Studio currently requires Python 3.10-3.12. Python 3.14 is not yet supported by the AI dependencies."
}

Write-Host "[1/3] Creating virtual environment..."
& $PythonCommand @PythonArgs -m venv $VenvPath
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

Write-Host "[2/3] Installing BeatSync Studio..."
& $VenvPython -m pip install --upgrade pip
if ($Dev) {
    & $VenvPython -m pip install -e "$ProjectRoot[anime,online,dev]"
} else {
    & $VenvPython -m pip install -e "$ProjectRoot[anime,online]"
}

Write-Host "[3/3] Installation finished."
$BeatSync = Join-Path $VenvPath "Scripts\beatsync.exe"
Write-Host ""
Write-Host "Setup complete. Checking the installation:"
& $BeatSync doctor
