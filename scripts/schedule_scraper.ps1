Param(
  [string]$ProjectRoot = "C:\Users\amrit\OneDrive\Documents\AI Data Science Project",
  [string]$TaskName = "ImperialCars-InventoryScrape-30min",
  [int]$IntervalMinutes = 30,
  [switch]$RunNow
)

$ErrorActionPreference = "Stop"

if ($IntervalMinutes -lt 15) {
  throw "IntervalMinutes must be at least 15."
}

$pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  throw "Python executable not found: $pythonExe"
}

$scriptPath = Join-Path $ProjectRoot "scripts\run_inventory_scrape_once.py"
if (-not (Test-Path $scriptPath)) {
  @'
#!/usr/bin/env python3
from backend.app.agents.inventory_scraper import run_inventory_scrape

if __name__ == "__main__":
    result = run_inventory_scrape()
    print(result)
'@ | Set-Content -Path $scriptPath -Encoding UTF8
}

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$scriptPath`"" -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration ([TimeSpan]::MaxValue)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType InteractiveToken -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
Write-Output "Scheduled task '$TaskName' created. Interval: every $IntervalMinutes minutes."

if ($RunNow) {
  Start-ScheduledTask -TaskName $TaskName
  Write-Output "Task '$TaskName' started manually."
}
