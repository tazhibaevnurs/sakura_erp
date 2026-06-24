# Docker Compose из корня проекта (без cd deploy).
# Примеры:
#   .\compose.ps1 prod up -d --build
#   .\compose.ps1 prod ps
#   .\compose.ps1 prod logs -f web
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("prod", "dev")]
    [string]$Profile,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$EnvFile = Join-Path $Root ".env"
$BaseFile = Join-Path $Root "deploy\docker-compose.yml"

if (-not (Test-Path $EnvFile)) {
    Write-Host "Создайте .env: copy .env.prod.example .env" -ForegroundColor Yellow
    exit 1
}

$OverrideFile = if ($Profile -eq "prod") {
    Join-Path $Root "deploy\docker-compose.prod.yml"
} else {
    Join-Path $Root "deploy\docker-compose.dev.yml"
}

docker compose --env-file $EnvFile -f $BaseFile -f $OverrideFile @ComposeArgs
