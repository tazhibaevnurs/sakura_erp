# Локальная разработка — только Django, без Redis и Celery.
# Задачи ИИ-ассистента выполняются синхронно (CELERY_TASK_ALWAYS_EAGER).
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

if (-not (Test-Path "$Root\.venv\Scripts\Activate.ps1")) {
    Write-Host "Создайте venv: py -3.12 -m venv .venv" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path "$Root\.env")) {
    Write-Host "Скопируйте .env: copy .env.local.example .env" -ForegroundColor Yellow
    exit 1
}

. "$Root\.venv\Scripts\Activate.ps1"
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
Set-Location $Root

Write-Host ""
Write-Host "=== ЛОКАЛЬНЫЙ РЕЖИМ ===" -ForegroundColor Cyan
Write-Host "  SQLite, без Redis, Celery worker не нужен" -ForegroundColor DarkGray
Write-Host "  Сайт: http://127.0.0.1:8888/" -ForegroundColor DarkGray
Write-Host "  Telegram webhook: ngrok http 8888  ->  ASSISTANT_PUBLIC_URL в .env" -ForegroundColor DarkGray
Write-Host "  Регистрация webhook: python manage.py register_telegram_webhook" -ForegroundColor DarkGray
Write-Host ""

python manage.py runserver 127.0.0.1:8888
