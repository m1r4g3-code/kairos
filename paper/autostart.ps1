# KAIROS paper trading - start the loop when the owner logs in to Windows.
#
#   powershell -ExecutionPolicy Bypass -File paper\autostart.ps1            install
#   powershell -ExecutionPolicy Bypass -File paper\autostart.ps1 -Remove    remove
#
# Creates a Task Scheduler task "KairosPaper" for the current user that runs
# paper\main.py with pythonw (no console window) at logon. It keeps running on
# battery, has no time limit, and is not restarted twice: main.py refuses to
# start a second copy.

param([switch]$Remove)

$TaskName = "KairosPaper"
if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "KairosPaperWake" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "Removed task $TaskName (if it existed)."
    exit 0
}

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Here "main.py"
$Python = (Get-Command python -ErrorAction Stop).Source
$Pythonw = Join-Path (Split-Path -Parent $Python) "pythonw.exe"
if (-not (Test-Path $Pythonw)) { $Pythonw = $Python }

$Action = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$Script`"" -WorkingDirectory (Split-Path -Parent $Here)
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Principal $Principal -Description "Kairos paper trading loop (recommend-only, no money)" -Force | Out-Null
Write-Output "Installed task $TaskName : $Pythonw `"$Script`" at logon."
Write-Output "Start it now with:  Start-ScheduledTask -TaskName $TaskName"
