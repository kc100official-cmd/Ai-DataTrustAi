# DataTrust AI - One-Command Local Development Startup Script (Windows PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DataTrust AI - Ask your data. Verify every answer." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Ensure sample SQLite databases & Knowledge Graph are initialized
$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python 3 was not found. Create a .venv and install backend requirements first."
    }
    $pythonPath = $pythonCommand.Source
}

& $pythonPath scripts/init_db.py

Write-Host "`n[1/2] Starting FastAPI Backend on http://127.0.0.1:8001 ..." -ForegroundColor Green
$backendProc = Start-Process -FilePath $pythonPath -ArgumentList "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001" -PassThru -NoNewWindow

Write-Host "[2/2] Starting Vite React Frontend on http://localhost:5173 ..." -ForegroundColor Green
try {
    Set-Location frontend
    pnpm run dev
} finally {
    Set-Location ..
    if ($backendProc -and !$backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
}
