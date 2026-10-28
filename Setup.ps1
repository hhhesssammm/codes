param([ValidateSet('3.12','3.13')][string]$PythonVersion = '3.12')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& py "-$PythonVersion" -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Install the selected 64-bit Python version and the py launcher first.' }
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $Python -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. See WINDOWS_GUIDE.md.' }
& $Python -m pip install -e . --no-deps --no-build-isolation
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; do not start a scientific run.' }
& $Python -m brain_imager_phase3 doctor
