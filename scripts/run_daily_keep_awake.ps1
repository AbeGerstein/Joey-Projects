# PnF Bot daily-run launcher used by Windows Task Scheduler.
#
# - Calls SetThreadExecutionState to prevent the system from sleeping during
#   the run (Modern Standby on this laptop can suspend processes after a few
#   minutes of "idle" even with standby-timeout=0).
# - Captures stdout/stderr to a timestamped log file under logs/.
# - Activates the project venv so pnf-bot.exe resolves correctly.
#
# Returns the bot's exit code so Task Scheduler's Last Result reflects the
# actual outcome (0 = success, non-zero = failure).

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

# Ensure logs directory exists
$logsDir = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile = Join-Path $logsDir "daily_run_$stamp.log"

# Tell Windows: keep system + display in working state until we release.
# Flags (from winbase.h):
#   ES_CONTINUOUS        = 0x80000000   — apply until reset
#   ES_SYSTEM_REQUIRED   = 0x00000001   — keep system awake
#   ES_AWAYMODE_REQUIRED = 0x00000040   — keep awake but allow display off
$signature = @'
using System;
using System.Runtime.InteropServices;
public static class PowerKeeper {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
Add-Type -TypeDefinition $signature -Language CSharp
$ES_CONTINUOUS        = [uint32]'0x80000000'
$ES_SYSTEM_REQUIRED   = [uint32]'0x00000001'
$ES_AWAYMODE_REQUIRED = [uint32]'0x00000040'
$keepAwake = $ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_AWAYMODE_REQUIRED
[void][PowerKeeper]::SetThreadExecutionState($keepAwake)

"[$($stamp)] launcher: starting daily-run, log -> $logFile" | Out-File -FilePath $logFile -Encoding utf8

try {
    $exe = Join-Path $projectRoot '.venv\Scripts\pnf-bot.exe'
    if (-not (Test-Path $exe)) { throw "pnf-bot.exe not found at $exe" }

    # Run the bot, append all output to the log file.
    & $exe daily-run *>> $logFile
    $exit = $LASTEXITCODE
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] launcher: pnf-bot exit code $exit" | Out-File -FilePath $logFile -Encoding utf8 -Append
    exit $exit
}
catch {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] launcher EXCEPTION: $($_.Exception.Message)" | Out-File -FilePath $logFile -Encoding utf8 -Append
    exit 99
}
finally {
    # Release the keep-awake request so the OS can manage power normally again.
    [void][PowerKeeper]::SetThreadExecutionState($ES_CONTINUOUS)
}
