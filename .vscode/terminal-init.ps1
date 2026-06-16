# Надёжная активация .venv для Windows PowerShell / Cursor
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$VenvRoot = Join-Path $ProjectRoot ".venv"
$Activate = Join-Path $VenvRoot "Scripts\Activate.ps1"

if (-not (Test-Path $Activate)) {
    Write-Host "venv не найден: $Activate" -ForegroundColor Yellow
    return
}

# Dot-source — переменные остаются в текущей сессии
. $Activate

# Явно фиксируем PATH и VIRTUAL_ENV (на случай если activate «отпустит»)
$Scripts = Join-Path $VenvRoot "Scripts"
$env:VIRTUAL_ENV = $VenvRoot
if ($env:PATH -notlike "*$Scripts*") {
    $env:PATH = "$Scripts;$env:PATH"
}

# Свой prompt: префикс (.venv) не пропадёт после Enter
function global:prompt {
    $loc = $executionContext.SessionState.Path.CurrentLocation
    if ($env:VIRTUAL_ENV) {
        Write-Host "(.venv) " -NoNewline -ForegroundColor DarkGreen
    }
    return "PS $loc> "
}

# Сразу показать строку с префиксом
prompt
