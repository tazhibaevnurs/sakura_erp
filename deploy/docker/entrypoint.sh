#!/bin/sh
set -e

run_as_app() {
  if [ "$(id -u)" = "0" ]; then
    gosu chaihana "$@"
  else
    "$@"
  fi
}

fix_volume_permissions() {
  if [ "$(id -u)" = "0" ]; then
    chown -R chaihana:chaihana /app/staticfiles /app/media /app/celerybeat 2>/dev/null || true
  fi
}

if [ "${RUN_BOOTSTRAP:-0}" != "1" ]; then
  fix_volume_permissions
  if [ "$(id -u)" = "0" ]; then
    exec gosu chaihana "$@"
  fi
  exec "$@"
fi

fix_volume_permissions

echo "Waiting for postgres..."
until run_as_app pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
  sleep 1
done

echo "Running migrations..."
run_as_app python manage.py migrate --noinput

echo "Collecting static..."
run_as_app python manage.py collectstatic --noinput

echo "Creating groups and permissions..."
run_as_app python manage.py create_groups

if [ "${CREATE_SUPERUSER:-0}" = "1" ]; then
  run_as_app python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
username = '${SUPERUSER_USERNAME:-admin}'
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username,
        '${SUPERUSER_EMAIL:-admin@example.com}',
        '${SUPERUSER_PASSWORD:-changeme123}'
    )
    print(f'Superuser created: {username}')
else:
    print(f'Superuser already exists: {username}')
"
fi

if [ "$(id -u)" = "0" ]; then
  exec gosu chaihana "$@"
fi
exec "$@"
