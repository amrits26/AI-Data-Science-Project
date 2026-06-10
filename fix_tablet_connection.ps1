<#
Fix tablet connection timeout for local FastAPI service on port 8000.

What this script does:
1) Checks whether something is listening on TCP 8000.
2) Creates or updates a Windows Firewall inbound allow rule for TCP 8000 on all profiles.
3) Optionally restarts uvicorn (if -RestartBackend is provided).
4) Prints the local IP and tablet test URLs.

Manual fallback steps (if LAN access still fails):
- Use ngrok tunnel:
  1. Install ngrok and authenticate.
  2. Run: ngrok http 8000
  3. Use the generated https URL on your tablet.
- Test from tablet:
  - Browser test: http://<LAPTOP_IP>:8000/api/health
  - Curl test (Termux): curl -v http://<LAPTOP_IP>:8000/api/health
#>

[CmdletBinding()]
param(
    [switch]$RestartBackend,
    [string]$BackendCommand = "uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    try {
        $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        return $false
    }
}

function Write-Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Get-PrimaryIPv4 {
    try {
        $defaultRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" |
            Sort-Object RouteMetric, InterfaceMetric |
            Select-Object -First 1

        if ($null -ne $defaultRoute) {
            $ip = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $defaultRoute.InterfaceIndex |
                Where-Object { $_.IPAddress -notlike "169.254*" -and $_.IPAddress -ne "127.0.0.1" } |
                Select-Object -ExpandProperty IPAddress -First 1

            if ($ip) { return $ip }
        }
    }
    catch {
        # Continue to fallback methods.
    }

    try {
        $fallbackIp = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object {
                $_.IPAddress -notlike "169.254*" -and
                $_.IPAddress -ne "127.0.0.1" -and
                $_.PrefixOrigin -ne "WellKnown"
            } |
            Select-Object -ExpandProperty IPAddress -First 1

        if ($fallbackIp) { return $fallbackIp }
    }
    catch {
        # Continue to hostname fallback.
    }

    try {
        return ([System.Net.Dns]::GetHostAddresses($env:COMPUTERNAME) |
            Where-Object { $_.AddressFamily -eq 'InterNetwork' -and $_.IPAddressToString -ne '127.0.0.1' } |
            Select-Object -First 1).IPAddressToString
    }
    catch {
        return $null
    }
}

Write-Info "Checking backend listener on TCP 8000..."
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    Write-Ok "Backend appears to be listening on port 8000 (PID: $($listener.OwningProcess))."
}
else {
    Write-Warn "No process is currently listening on port 8000."
}

Write-Info "Testing localhost:8000 reachability..."
$tnc = Test-NetConnection -ComputerName "127.0.0.1" -Port 8000 -WarningAction SilentlyContinue
if ($tnc.TcpTestSucceeded) {
    Write-Ok "Local TCP test succeeded on 127.0.0.1:8000."
}
else {
    Write-Warn "Local TCP test failed on 127.0.0.1:8000 (service may be down)."
}

$ruleName = "ImperialAI-Allow-TCP-8000"
Write-Info "Ensuring Windows Firewall inbound rule exists for TCP 8000 on all profiles..."

$isAdmin = Test-IsAdministrator
if (-not $isAdmin) {
    Write-Warn "Not running as Administrator. Firewall changes require elevation."
    Write-Host "Open PowerShell as Administrator and run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\fix_tablet_connection.ps1" -ForegroundColor Yellow
}
else {
    try {
        $existingRules = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        if (-not $existingRules) {
            New-NetFirewallRule `
                -DisplayName $ruleName `
                -Direction Inbound `
                -Action Allow `
                -Enabled True `
                -Profile Any `
                -Protocol TCP `
                -LocalPort 8000 `
                | Out-Null

            Write-Ok "Firewall rule added successfully."
        }
        else {
            foreach ($rule in $existingRules) {
                Set-NetFirewallRule -Name $rule.Name -Direction Inbound -Action Allow -Enabled True -Profile Any | Out-Null

                $portFilter = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $rule
                $needsRecreate = $false

                if ($portFilter.Protocol -ne "TCP") {
                    $needsRecreate = $true
                }

                if ($portFilter.LocalPort -notmatch "(^|,|-)8000($|,|-)") {
                    $needsRecreate = $true
                }

                if ($needsRecreate) {
                    Remove-NetFirewallRule -Name $rule.Name | Out-Null
                    New-NetFirewallRule `
                        -DisplayName $ruleName `
                        -Direction Inbound `
                        -Action Allow `
                        -Enabled True `
                        -Profile Any `
                        -Protocol TCP `
                        -LocalPort 8000 `
                        | Out-Null
                }
            }

            Write-Ok "Firewall rule already existed and was updated/verified for all profiles."
        }
    }
    catch {
        Write-Warn "Firewall rule update failed: $($_.Exception.Message)"
    }
}

if ($RestartBackend) {
    Write-Info "RestartBackend switch detected. Restarting listener on port 8000 if present..."
    $listenNow = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listenNow) {
        try {
            Stop-Process -Id $listenNow.OwningProcess -Force
            Start-Sleep -Seconds 1
            Write-Ok "Stopped existing process on port 8000 (PID: $($listenNow.OwningProcess))."
        }
        catch {
            Write-Warn "Could not stop process on port 8000: $($_.Exception.Message)"
        }
    }

    Write-Info "Starting backend command in a new PowerShell window..."
    $startCmd = "Set-Location '$PWD'; .\\.venv\\Scripts\\Activate.ps1; $BackendCommand"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $startCmd | Out-Null
    Write-Ok "Backend start command launched."
}
else {
    Write-Warn "Backend was not restarted by this script."
    Write-Host "Restart your backend with:" -ForegroundColor Yellow
    Write-Host "  cd \"$PWD\"" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\activate" -ForegroundColor Yellow
    Write-Host "  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000" -ForegroundColor Yellow
}

$ip = Get-PrimaryIPv4
if (-not $ip) {
    Write-Warn "Could not auto-detect a LAN IPv4 address."
    Write-Host "Run 'ipconfig' and use your Wi-Fi IPv4 address in the URL below." -ForegroundColor Yellow
    $ip = "<YOUR_LAN_IP>"
}

$tabletApiUrl = "http://${ip}:8000/api/health"
$tabletAppUrl = "http://${ip}:3000"

Write-Host ""
Write-Ok "Setup complete."
Write-Host "Laptop LAN IP: $ip" -ForegroundColor Green
Write-Host "Tablet API test URL: $tabletApiUrl" -ForegroundColor Green
Write-Host "Tablet app URL:      $tabletAppUrl" -ForegroundColor Green
Write-Host ""
Write-Host "If tablet still times out, verify both devices are on the same Wi-Fi and try ngrok fallback in script comments." -ForegroundColor Yellow
