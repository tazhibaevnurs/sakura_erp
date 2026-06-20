# Production deploy (Windows / PowerShell)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "deploy")

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "Создайте .env: copy .env.prod.example .env" -ForegroundColor Yellow
    exit 1
}

Write-Host "==> Сборка и запуск production-стека..." -ForegroundColor Cyan
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

Start-Sleep -Seconds 5

Write-Host "==> Проверка настроек..." -ForegroundColor Cyan
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web python manage.py check_deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web python manage.py check --deploy

Write-Host ""
Write-Host "Готово. Сайт: http://<server-ip>/" -ForegroundColor Green
Write-Host "  createsuperuser: docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py createsuperuser"
Write-Host "  Telegram webhook: docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py register_telegram_webhook"
