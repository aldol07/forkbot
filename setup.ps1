# One-time setup: creates .venv (Python 3.11), installs backend + frontend deps, copies env files.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -q
& .\.venv\Scripts\python.exe -c "import fastapi, fastembed, pgvector, openai, pypdf; print('backend deps ok')"
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Output "created .env (add GROQ_API_KEY)" }
Push-Location frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.local.example .env.local }
npm install --no-audit --no-fund
Pop-Location
Write-Output "SETUP-DONE"
