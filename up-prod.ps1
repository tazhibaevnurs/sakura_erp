# Production deploy из корня проекта.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

Write-Host "==> Сборка и запуск production-стека..." -ForegroundColor Cyan
& (Join-Path $Root "compose.ps1") prod up -d --build

Start-Sleep -Seconds 5

Write-Host "==> Проверка настроек..." -ForegroundColor Cyan
& (Join-Path $Root "compose.ps1") prod exec -T web python manage.py check_deploy
& (Join-Path $Root "compose.ps1") prod exec -T web python manage.py check --deploy

Write-Host ""
Write-Host "Готово. Сайт: http://<server-ip>/" -ForegroundColor Green
Write-Host "  .\compose.ps1 prod exec web python manage.py createsuperuser"
Write-Host "  .\compose.ps1 prod exec web python manage.py register_telegram_webhook"
