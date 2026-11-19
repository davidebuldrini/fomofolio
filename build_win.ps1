# Build dist\FOMOfolio\FOMOfolio.exe and dist\FOMOfolio-windows-x64.zip.
# Uses the active Python if one is set up (CI), otherwise .\venv.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $env:VIRTUAL_ENV -and -not $env:CI) {
    if (-not (Test-Path venv)) { python -m venv venv }
    . .\venv\Scripts\Activate.ps1
}

python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
python -m PyInstaller --noconfirm FOMOfolio.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Compress-Archive -Path dist\FOMOfolio -DestinationPath dist\FOMOfolio-windows-x64.zip -Force
Write-Host "Built dist\FOMOfolio\FOMOfolio.exe and dist\FOMOfolio-windows-x64.zip"
