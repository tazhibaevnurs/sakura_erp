# Локально: Telegram polling — python manage.py run_telegram_bot (отдельный терминал)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

if (-not (Test-Path "$Root\.venv\Scripts\Activate.ps1")) {
    Write-Host "Создайте venv: py -3.12 -m venv .venv" -ForegroundColor Yellow
    exit 1
}

. "$Root\.venv\Scripts\Activate.ps1"
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
Set-Location $Root

python manage.py runserver 127.0.0.1:8888
