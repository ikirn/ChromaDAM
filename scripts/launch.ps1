param([switch]$InstallAI)
$ErrorActionPreference = 'Stop'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $localPython)) {
    Write-Host 'Creating a local Python environment. Python 3.10+ must be installed.'
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
$requirementsFile = if ($InstallAI) { 'requirements-ai.txt' } else { 'requirements.txt' }
$requirementsHash = (Get-FileHash -LiteralPath $requirementsFile -Algorithm SHA256).Hash
$markerPath = Join-Path $projectRoot ".venv\$requirementsFile.sha256"
if (-not (Test-Path -LiteralPath $markerPath) -or (Get-Content -LiteralPath $markerPath -Raw).Trim() -ne $requirementsHash) {
    & $localPython -m pip install -r $requirementsFile
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the error above and internet connection.' }
    Set-Content -LiteralPath $markerPath -Value $requirementsHash
}
if ($InstallAI) {
    & $localPython scripts/setup_models.py
    if ($LASTEXITCODE -ne 0) { throw 'Model setup failed. Re-run install-ai.cmd to retry.' }
    Write-Host 'AI setup complete. Run start.cmd to open ChromaDAM.'
} else {
    Write-Host 'ChromaDAM: http://127.0.0.1:8000 - keep this window open. Press Ctrl+C to stop.'
    & $localPython -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
}
