# Registers/removes the single Windows scheduled task that starts the
# dashboard at logon. All actual job-search scheduling (which days, what
# time) lives inside the app itself (automation/scheduler.py) and is edited
# from /schedules - this script only needs to run once (or whenever the
# dashboard's install/uninstall button is used).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_task.ps1 -Action Install
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_task.ps1 -Action Uninstall

param(
    [ValidateSet("Install", "Uninstall")]
    [string]$Action = "Install"
)

$ErrorActionPreference = "Stop"

$TaskName = "JobHunter Dashboard"
$LegacyTaskName = "JobHunter Daily Search"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ScriptDir "run_dashboard.bat"

# The legacy task pointed at a stale path (missing the PROYECTOS folder) and
# had been failing silently since June - always remove it if present.
$legacy = Get-ScheduledTask -TaskName $LegacyTaskName -ErrorAction SilentlyContinue
if ($legacy) {
    Unregister-ScheduledTask -TaskName $LegacyTaskName -Confirm:$false
    Write-Output "Tarea obsoleta '$LegacyTaskName' eliminada."
}

if ($Action -eq "Uninstall") {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output "Tarea '$TaskName' eliminada."
    } else {
        Write-Output "Tarea '$TaskName' no estaba instalada."
    }
    exit 0
}

$action = New-ScheduledTaskAction -Execute $BatPath
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Output "Tarea '$TaskName' instalada (At Logon -> $BatPath)."
