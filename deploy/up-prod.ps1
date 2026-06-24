# Обёртка: запускайте .\up-prod.ps1 из корня проекта.
$Root = Split-Path -Parent $PSScriptRoot
& (Join-Path $Root "up-prod.ps1") @args
