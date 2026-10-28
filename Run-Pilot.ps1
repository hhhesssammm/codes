param([switch]$Execute, [int]$MaxCalls = 0, [switch]$RetryFailed)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$RunArgs = @('-m','brain_imager_phase3','run')
if ($Execute) { $RunArgs += '--execute' }
if ($MaxCalls -gt 0) { $RunArgs += @('--max-calls', "$MaxCalls") }
if ($RetryFailed) { $RunArgs += '--retry-failed' }
& $Python @RunArgs
if ($LASTEXITCODE -ne 0) { throw 'Pilot stopped. Inspect the message and execution receipt before retrying.' }
