# Чайхана — CRM/POS/HR

Django-приложение для чайханы: заказы, кухня, касса, зарплата, отчёты.

## Структура проекта

```
sakur_erp/
├── manage.py              # точка входа Django
├── config/                # настройки, urls, asgi/wsgi
├── apps/                  # приложения
├── templates/
├── static/
├── requirements.txt       # зависимости (dev)
├── requirements/          # base, dev, prod
├── .env                   # переменные окружения (локально)
├── db.sqlite3             # БД в dev (создаётся после migrate)
├── run.ps1                # быстрый запуск на Windows
└── deploy/                # Docker (опционально, для production)
```

## Локальный запуск (без Docker)

### 1. Виртуальное окружение

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. База и данные

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
python manage.py migrate
python manage.py create_groups
python manage.py seed_demo
python manage.py seed_menu
python manage.py seed_tables
python manage.py createsuperuser
```

### 3. Сервер

```powershell
python manage.py runserver
# или
.\run.ps1
```

Сайт: http://127.0.0.1:8000/

Локальный dev использует **SQLite** и in-memory Channels/Celery (Redis не нужен).

## Production (Docker)

См. `deploy/README.md`
