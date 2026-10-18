[CmdletBinding()]
param(
    [switch]$Remove,
    [string]$DataDir = 'D:\KynlyData\queue'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$taskName = 'Kynly-Background-' + $identity.User.Value
if ($Remove) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    Write-Output 'Kynly sign-in task removed. An already running host is unchanged.'
    return
}
$pythonExe = (& py -3 -c 'import sys; print(sys.executable)').Trim()
if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $pythonExe)) {
    throw 'Python 3 could not be located.'
}
if (!(Test-Path -LiteralPath (Join-Path $repo '.kynly\api-token.txt'))) {
    throw 'Missing .kynly/api-token.txt. Complete the API setup first.'
}
$startup = Join-Path $PSScriptRoot 'startup_host.py'
$dataPath = [System.IO.Path]::GetFullPath($DataDir)
if ($startup.Contains('"') -or $dataPath.Contains('"')) { throw 'Paths cannot contain quotes.' }
$arguments = '"' + $startup + '" --data-dir "' + $dataPath + '"'
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $arguments -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$trigger.Delay = 'PT30S'
$principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Start Kynly local API and worker after sign-in and Docker readiness.'
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Output ('Installed task: ' + $taskName)
Write-Output 'Manual test:'
Write-Output ('Start-ScheduledTask -TaskName "' + $taskName + '"')
Write-Output 'Enable Docker Desktop startup at sign-in in its settings. No reboot is required for the manual test.'
