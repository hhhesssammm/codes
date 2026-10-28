$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$Steps = @(@('init'), @('fetch','--what','all'), @('index'), @('make-pre','--rater','R1'), @('validate'))
foreach ($Step in $Steps) {
    & $Python -m brain_imager_phase3 @Step
    if ($LASTEXITCODE -ne 0) { throw "Data preparation stopped at: $Step" }
}
Write-Host 'Data ready. Complete human annotations before planning or generation. No API model was called.'
