#!/usr/bin/env bash
# Production deploy: Docker Compose (без dev-override)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/deploy"

if [ ! -f "$ROOT/.env" ]; then
  echo "Создайте .env: cp .env.prod.example .env && отредактируйте секреты"
  exit 1
fi

echo "==> Сборка и запуск production-стека..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo "==> Ожидание healthcheck web..."
sleep 5

echo "==> Проверка настроек..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web python manage.py check_deploy || true
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web python manage.py check --deploy || true

echo ""
echo "Готово. Сайт: http://<server-ip>/"
echo "Админка: http://<server-ip>/admin/"
echo ""
echo "Следующие шаги:"
echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py createsuperuser"
echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py register_telegram_webhook"
echo "  После HTTPS: DJANGO_USE_HTTPS=True и CSRF_TRUSTED_ORIGINS в .env, затем docker compose ... up -d"
