#!/bin/sh
set -e

if [ "${RUN_BOOTSTRAP:-0}" != "1" ]; then
  exec "$@"
fi

echo "Waiting for postgres..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
  sleep 1
done

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static..."
python manage.py collectstatic --noinput

echo "Creating groups and permissions..."
python manage.py create_groups

if [ "${CREATE_SUPERUSER:-0}" = "1" ]; then
  python manage.py shell -c "
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

exec "$@"
