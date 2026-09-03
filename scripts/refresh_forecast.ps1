$ErrorActionPreference = "Stop"
Set-Location "C:\Users\adors\OneDrive\Documents\NBA Forecast"
$env:PYTHONPATH = "src"
$logDirectory = Join-Path (Get-Location) "data\logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logPath = Join-Path $logDirectory ("refresh_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

& ".venv\Scripts\python.exe" -m nba_forecast.cli `
  --input "nba_forecast_data_2025_26 (1).xlsx" `
  --output "data/processed" `
  --public-source "data/raw/llimllib_nba_data" `
  --refresh-live *>&1 | Tee-Object -FilePath $logPath
$exitCode = $LASTEXITCODE
Add-Content -Path $logPath -Value ("completed_at={0} exit_code={1}" -f (Get-Date -Format "o"), $exitCode)
exit $exitCode
