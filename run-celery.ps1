# Celery worker — только для СЕРВЕРА (нужен запущенный Redis).
# Локально используйте run-local.ps1 без этого скрипта.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

if (-not (Test-Path "$Root\.venv\Scripts\Activate.ps1")) {
    Write-Host "Создайте venv: py -3.12 -m venv .venv" -ForegroundColor Yellow
    exit 1
}

. "$Root\.venv\Scripts\Activate.ps1"
Set-Location $Root

if (-not $env:DJANGO_SETTINGS_MODULE) {
    $env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
}

Write-Host ""
Write-Host "=== CELERY WORKER (серверный режим) ===" -ForegroundColor Cyan
Write-Host "  Settings: $env:DJANGO_SETTINGS_MODULE" -ForegroundColor DarkGray
Write-Host "  Требуется Redis: $env:CELERY_BROKER_URL" -ForegroundColor DarkGray
Write-Host "  Windows: используется --pool=solo" -ForegroundColor DarkGray
Write-Host ""

celery -A config worker -l info --pool=solo
