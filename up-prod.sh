#!/usr/bin/env bash
# Production deploy из корня проекта.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Сборка и запуск production-стека..."
"$ROOT/compose.sh" prod up -d --build

echo "==> Ожидание healthcheck web..."
sleep 5

echo "==> Проверка настроек..."
"$ROOT/compose.sh" prod exec -T web python manage.py check_deploy || true
"$ROOT/compose.sh" prod exec -T web python manage.py check --deploy || true

echo ""
echo "Готово. Сайт: http://<server-ip>/"
echo "Админка: http://<server-ip>/admin/"
echo ""
echo "Дальше:"
echo "  ./compose.sh prod exec web python manage.py createsuperuser"
echo "  ./compose.sh prod exec web python manage.py register_telegram_webhook"
