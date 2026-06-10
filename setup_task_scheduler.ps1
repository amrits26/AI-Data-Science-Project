param(
    [string]$TaskName = "ImperialCars-InventoryImport",
    [string]$ProjectRoot = (Resolve-Path ".").Path,
    [string]$PythonPath = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "== Imperial Cars Inventory Scheduler Setup =="

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$resolvedPythonPath = if ([System.IO.Path]::IsPathRooted($PythonPath)) {
    $PythonPath
} else {
    Join-Path $resolvedProjectRoot $PythonPath
}

if (-not (Test-Path $resolvedPythonPath)) {
    throw "Python executable not found: $resolvedPythonPath"
}

$scriptPath = Join-Path $resolvedProjectRoot "scripts\import_imperial_inventory.py"
if (-not (Test-Path $scriptPath)) {
    throw "Missing inventory import script: $scriptPath"
}

$command = "Set-Location -LiteralPath '$resolvedProjectRoot'; & '$resolvedPythonPath' '$scriptPath'"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command \"$command\""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 2:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Task registered: $TaskName"
Write-Host "Schedule: Every Monday at 02:00"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State, Author | Format-Table -AutoSize
Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object LastRunTime, NextRunTime, LastTaskResult | Format-Table -AutoSize
