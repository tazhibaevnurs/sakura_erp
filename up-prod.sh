#!/usr/bin/env bash
# Production deploy из корня проекта.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Сборка и запуск production-стека..."
"$ROOT/compose.sh" prod build --no-cache web daphne celery celery-beat
if ! "$ROOT/compose.sh" prod up -d; then
  echo ""
  echo "ОШИБКА: стек не поднялся. Логи web:"
  "$ROOT/compose.sh" prod logs --tail=80 web || true
  exit 1
fi

echo "==> Ожидание запуска (миграции + static)..."
sleep 30

if ! "$ROOT/compose.sh" prod ps web 2>/dev/null | grep -q "Up"; then
  echo ""
  echo "ОШИБКА: web не запущен. Логи:"
  "$ROOT/compose.sh" prod logs --tail=80 web || true
  exit 1
fi

echo "==> Проверка настроек..."
"$ROOT/compose.sh" prod exec -T web python manage.py check_deploy || true
"$ROOT/compose.sh" prod exec -T web python manage.py check --deploy || true

echo ""
echo "Готово. Проверка:"
echo "  curl http://localhost/health/"
echo "  ./compose.sh prod ps"
echo ""
echo "Дальше:"
echo "  ./compose.sh prod exec web python manage.py createsuperuser"
echo "  ./compose.sh prod exec web python manage.py register_telegram_webhook"
