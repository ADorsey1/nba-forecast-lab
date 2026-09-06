$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $projectRoot ".venv\Scripts\python.exe") (Join-Path $PSScriptRoot "refresh_forecast.py") @args
exit $LASTEXITCODE
