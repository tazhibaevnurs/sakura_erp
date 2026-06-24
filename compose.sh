#!/usr/bin/env bash
# Docker Compose из корня проекта (без cd deploy).
# Примеры:
#   ./compose.sh prod up -d --build
#   ./compose.sh prod ps
#   ./compose.sh prod logs -f web
#   ./compose.sh prod exec web python manage.py createsuperuser
#   ./compose.sh dev up --build
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"
FILES=(-f "$ROOT/deploy/docker-compose.yml")

if [ ! -f "$ENV_FILE" ]; then
  echo "Создайте .env: cp .env.prod.example .env"
  exit 1
fi

case "${1:-}" in
  prod)
    FILES+=(-f "$ROOT/deploy/docker-compose.prod.yml")
    shift
    ;;
  dev)
    FILES+=(-f "$ROOT/deploy/docker-compose.dev.yml")
    shift
    ;;
  "")
    echo "Укажите профиль: prod или dev"
    echo "  ./compose.sh prod up -d --build"
    exit 1
    ;;
  *)
    echo "Неизвестный профиль: $1 (используйте prod или dev)"
    exit 1
    ;;
esac

exec docker compose --env-file "$ENV_FILE" "${FILES[@]}" "$@"
