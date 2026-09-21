# One-shot local run without Docker for backend + frontend (PowerShell version).
# Mongo still runs in a container (see docs/RUNNING_WITHOUT_DOCKER.md for why).
# Envoy is deliberately NOT started here -- see section 4/6 of that doc.
#
# Assumes: native Postgres already running + `createdb taskflow` done, and
# backend/.env + frontend/.env already filled in with your own values (this
# script only copies .env.example when the file is missing).

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

function Find-GitBash {
    $candidates = @(
        "$env:ProgramFiles\Git\bin\bash.exe",
        "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
        "$env:LocalAppData\Programs\Git\bin\bash.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

$backendProc = $null
$frontendProc = $null

try {
    Write-Host "==> Mongo (container only)"
    docker compose up -d mongo

    Write-Host "==> Backend"
    Set-Location "$RootDir\backend"

    if (-not (Test-Path ".venv")) {
        Write-Host "  (creating .venv)"
        python -m venv .venv
    }

    $venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"

    & $venvPython -m pip install -e ".[dev]" --quiet

    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
    }

    # generate_proto.sh uses sed, so it runs through Git Bash rather than
    # being reimplemented here -- avoids the two ever drifting apart.
    $gitBash = Find-GitBash
    if (-not $gitBash) {
        throw "Git Bash not found (checked common install paths). Install Git for Windows, or run scripts/generate_proto.sh manually another way."
    }
    & $gitBash -lc "./scripts/generate_proto.sh"

    & $venvPython -m alembic upgrade head

    $backendProc = Start-Process -FilePath $venvPython -ArgumentList "-m", "app.main" `
        -WorkingDirectory "$RootDir\backend" -NoNewWindow -PassThru

    Write-Host "==> Frontend"
    Set-Location "$RootDir\frontend"

    if (-not (Test-Path "node_modules")) {
        & cmd.exe /c "npm install"
    }
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
    }

    $frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory "$RootDir\frontend" -NoNewWindow -PassThru

    Set-Location $RootDir

    Write-Host ""
    Write-Host "Backend REST : http://localhost:8000"
    Write-Host "Backend gRPC : localhost:50051 (StreamBoardUpdates won't be reachable from the browser without Envoy)"
    Write-Host "Frontend     : http://localhost:5173"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop backend + frontend."

    Wait-Process -Id $backendProc.Id, $frontendProc.Id
}
finally {
    Write-Host ""
    Write-Host "Stopping backend/frontend (Mongo container keeps running -- 'docker compose stop mongo' if you want it down too)..."
    if ($backendProc) { Stop-Process -Id $backendProc.Id -ErrorAction SilentlyContinue }
    if ($frontendProc) { Stop-Process -Id $frontendProc.Id -ErrorAction SilentlyContinue }
}
